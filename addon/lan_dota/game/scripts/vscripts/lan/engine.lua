local Room=require('lan.room')
local JSON=require('lan.json')
local Identity=require('lan.identity')
local Engine={}; Engine.__index=Engine
local function method(obj,key) return obj~=nil and type(obj[key])=='function' end
local function bool(v) return v==true or v==1 end
local function numeric(v)
    if type(v)~='number' and type(v)~='string' then return nil end
    local n=tonumber(v); if n and n==n and n~=math.huge and n~=-math.huge and n==math.floor(n) then return n end
    return nil
end
function Engine.new(config)
    local self=setmetatable({config=config,listeners={},last_heartbeat=-100,last_reject=-100,
        filled=false,rate={},bot_fill_deadline=nil},Engine)
    self.room=Room.new(function() return Time() end,config.client_revision)
    return self
end
function Engine:emit(kind,detail)
    local line=type(detail)=='table' and JSON.encode(detail) or tostring(detail)
    line=line:gsub('[\r\n]',' ')
    print('LANLAB|'..self.config.session..'|'..kind..'|'..line)
end
function Engine:error(message)
    self.room:fail(message); self:emit('ERROR',message)
    -- Best effort only: report the failure even if pausing is not supported.
    if self.mode and method(self.mode,'SetBotThinkingEnabled') then pcall(function() self.mode:SetBotThinkingEnabled(false) end) end
    if type(PauseGame)=='function' then pcall(function() PauseGame(true) end) end
    pcall(function() self:publish() end)
end
function Engine:publish()
    local state=self.room:snapshot()
    state.source_sha256=self.config.source_sha256
    state.bot_version=self.config.bot and self.config.bot.version or ''
    -- NetTable values use 0/1 for booleans at protocol boundaries.
    for k,v in pairs(state.options) do if type(v)=='boolean' then state.options[k]=v and 1 or 0 end end
    for k,v in pairs(state.capabilities) do if type(v)=='boolean' then state.capabilities[k]=v and 1 or 0 end end
    local stored=CustomNetTables:SetTableValue('lan_room','state',state)
    if stored==false then error('lan_room_nettable_rejected; verify scripts/custom_net_tables.txt') end
    return state
end
function Engine:refresh_players()
    local rows={}
    for pid=0,63 do
        if PlayerResource:IsValidPlayerID(pid) then
            local c=PlayerResource:GetConnectionState(pid)
            local isbot=DOTA_CONNECTION_STATE_BOT~=nil and c==DOTA_CONNECTION_STATE_BOT
            if method(PlayerResource,'IsFakeClient') then isbot=isbot or PlayerResource:IsFakeClient(pid) end
            if not isbot then
                local player=PlayerResource:GetPlayer(pid)
                local connected=c==DOTA_CONNECTION_STATE_CONNECTED and player~=nil
                local team=PlayerResource:GetCustomTeamAssignment(pid)
                rows[#rows+1]={pid=pid,identity=tostring(PlayerResource:GetSteamAccountID(pid)),
                    connected=connected,team=team,name=string.sub(PlayerResource:GetPlayerName(pid) or ('Player '..pid),1,96)}
            end
        end
    end
    self.room:sync(rows)
end
function Engine:reply(pid,ok,message)
    local player=PlayerResource:GetPlayer(pid)
    if player then CustomGameEventManager:Send_ServerToPlayer(player,'lan_reply',{ok=ok and 1 or 0,message=message or 'ok'}) end
    self:publish()
end
function Engine:dispatch(source,keys)
    if type(keys)~='table' then return end
    local pid=Identity.resolve(source,PlayerResource,EntIndexToHScript)
    if pid==nil then
        if Time()-self.last_reject>10 then self.last_reject=Time(); self:emit('ERROR','event_identity_unresolved; source='..tostring(source)) end
        return
    end
    local t=Time(); local rate=self.rate[pid]
    if not rate or t-rate.time>=1 then rate={time=t,count=0}; self.rate[pid]=rate end
    rate.count=rate.count+1; if rate.count>12 then return end
    self:refresh_players()
    local action=keys.action; local rev=numeric(keys.revision); local ok,err=false,'unknown_action'
    if action=='hello' then
        local before=self.room.players[pid] and self.room.players[pid].hello
        ok,err=self.room:hello(pid,keys.client_revision)
        if ok and not before then self:emit('UI_HELLO',tostring(pid)) end
    elseif action=='match_tool' then
        ok,err=require('lan.cheats').button(self,pid,keys.tool)
    elseif action=='solo_start' then
        ok,err=self.room:authorize(pid,rev,true)
        if ok then
            local count=0
            for _,p in pairs(self.room.players) do if p.connected then count=count+1 end end
            if count~=1 then ok=false;err='solo_requires_one_player' end
        end
        if ok then
            local raw=keys.options
            local value={bot_mode='tiandixing_native_lab',fill_bots=true,ack_unverified=true}
            local allowed={radiant_gold_multiplier=true,radiant_xp_multiplier=true,radiant_gold_start=true,radiant_player_number=true,dire_gold_multiplier=true,dire_xp_multiplier=true,dire_gold_start=true,dire_player_number=true,respawn_time_percentage=true,buyback_cooldown=true,tower_power=true,tower_endure=true,max_level=true,radiant_difficulty=true,dire_difficulty=true,gold_percent=true,selection_seconds=true,pregame_seconds=true}
            if type(raw)~='table' then ok=false else
                for k,v in pairs(raw) do
                    if not allowed[k] then ok=false
                    else value[k]=numeric(v);if (k=='radiant_gold_multiplier' or k=='dire_gold_multiplier' or k=='radiant_xp_multiplier' or k=='dire_xp_multiplier') and (type(v)=='number' or type(v)=='string') then value[k]=tonumber(v) end;if value[k]==nil then ok=false end end
                end
            end
            if not ok then err='invalid_options'
            else ok,err=self.room:set_options(pid,rev,value) end
        end
        if ok then
            self.room.cheats=(method(Convars,'GetBool') and Convars:GetBool('sv_cheats')) or GameRules:IsCheatMode()
            if not self.room.cheats and not self.room.caps.tutorial_bots then ok=false;err='bot_populate_requires_explicit_cheats' end
        end
        if ok then
            PlayerResource:SetCustomTeamAssignment(pid,2)
            if PlayerResource:GetCustomTeamAssignment(pid)~=2 then ok=false;err='engine_team_assignment_failed'
            else
                self.room:assign(pid,2,1)
                ok,err=self.room:set_ready(pid,self.room.revision,true)
                if ok then ok,err=self.room:can_start(pid,self.room.revision) end
                if ok then self:start_match() end
            end
        end
    elseif action=='team' then
        local team,role=numeric(keys.team),numeric(keys.role)
        ok,err=self.room:check_team(pid,rev,team,role)
        if ok then
            PlayerResource:SetCustomTeamAssignment(pid,team)
            if PlayerResource:GetCustomTeamAssignment(pid)~=team then ok=false; err='engine_team_assignment_failed'
            else self.room:assign(pid,team,role) end
        end
    elseif action=='options' then
        local raw=keys.options
        if type(raw)=='table' then
            local allowed={bot_mode=true,fill_bots=true,ack_unverified=true,radiant_difficulty=true,dire_difficulty=true,
                selection_seconds=true,pregame_seconds=true,gold_percent=true}
            local value={}; local unknown=false
            for k,v in pairs(raw) do
                if not allowed[k] then unknown=true
                elseif k=='fill_bots' or k=='ack_unverified' then
                    if v~=0 and v~=1 and type(v)~='boolean' then unknown=true else value[k]=bool(v) end
                elseif k=='bot_mode' then
                    if type(v)~='string' then unknown=true else value[k]=v end
                else
                    local number=numeric(v)
                    if number==nil then unknown=true else value[k]=number end
                end
            end
            if unknown then ok=false;err='invalid_options' else ok,err=self.room:set_options(pid,rev,value) end
        else err='invalid_options' end
    elseif action=='ready' then
        if keys.ready==0 or keys.ready==1 or type(keys.ready)=='boolean' then
            ok,err=self.room:set_ready(pid,rev,bool(keys.ready))
        else err='invalid_boolean' end
    elseif action=='transfer' then ok,err=self.room:transfer(pid,rev,numeric(keys.target))
    elseif action=='start' then
        self.room.cheats=(method(Convars,'GetBool') and Convars:GetBool('sv_cheats')) or GameRules:IsCheatMode()
        ok,err=self.room:can_start(pid,rev)
        if ok then self:start_match() end
    end
    if action~='hello' then self:emit('ACTION',{pid=pid,action=tostring(action),ok=ok and 1 or 0,message=err or 'ok'}) end
    self:reply(pid,ok,err)
end
function Engine:start_match()
    local r=self.room; local o=r.options
    if o.gold_percent~=100 and not method(self.mode,'SetModifyGoldFilter') then
        self:error('gold_filter_unavailable'); return
    end
    if method(self.mode,'SetModifyGoldFilter') then
        if method(self.mode,'SetFilterMoreGold') then self.mode:SetFilterMoreGold(true) end
        self.mode:SetModifyGoldFilter(function(_,event)
            if type(event.gold)=='number' and event.gold>0 then
                local side=method(PlayerResource,'GetTeam') and PlayerResource:GetTeam(event.player_id_const)==3 and 'dire' or 'radiant'
                event.gold=math.floor(event.gold*o.gold_percent/100*o[side..'_gold_multiplier'])
            end
            return true
        end,self)
        self:emit('GOLD_RULE',{percent=o.gold_percent,scope='positive_gold_filter_events'})
    end
    require('lan.rules').start(self)
    r:begin() -- latch before any engine side effect / duplicate event
    GameRules:SetHeroSelectionTime(o.selection_seconds)
    GameRules:SetPreGameTime(o.pregame_seconds)
    self.mode:SetPauseEnabled(true)
    if o.bot_mode=='tiandixing_native_lab' then
        self.mode:SetBotThinkingEnabled(true)
        -- Difficulty is assigned to each spawned bot by lan.rules, per team.
    end
    GameRules:LockCustomGameSetupTeamAssignment(true)
    self:emit('START',{mode=o.bot_mode,fill=o.fill_bots,roles='preferences_not_mapped_to_tiandixing_slots'})
    GameRules:FinishCustomGameSetup()
    self.transition_deadline=Time()+20
end
function Engine:bot_count()
    local n=0
    for pid=0,63 do
        if PlayerResource:IsValidPlayerID(pid) then
            local c=PlayerResource:GetConnectionState(pid)
            local isbot=DOTA_CONNECTION_STATE_BOT~=nil and c==DOTA_CONNECTION_STATE_BOT
            if method(PlayerResource,'IsFakeClient') then isbot=isbot or PlayerResource:IsFakeClient(pid) end
            if isbot then n=n+1 end
        end
    end
    return n
end
function Engine:tick()
    if self.room.phase=='error' then
        if Time()-self.last_heartbeat>=2 then self.last_heartbeat=Time(); self:emit('STATE',self:publish()) end
        return 2
    end
    if not self.cheats_initialized and method(Convars,'SetBool') then Convars:SetBool('sv_cheats',true);self.cheats_initialized=true end
    self.room.cheats=(method(Convars,'GetBool') and Convars:GetBool('sv_cheats')) or GameRules:IsCheatMode()
    self:refresh_players()
    local state=GameRules:State_Get(); local phase
    if state==DOTA_GAMERULES_STATE_INIT and not self.init_setup_requested then
        for _,player in pairs(self.room.players) do
            if player.connected and method(GameRules,'ResetToCustomGameSetup') then
                self.init_setup_requested=true
                self:emit('INIT_SETUP','ResetToCustomGameSetup_requested')
                GameRules:ResetToCustomGameSetup()
                state=GameRules:State_Get()
                break
            end
        end
    end
    if state==DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP then phase=self.room.started and 'starting' or 'setup'
    elseif state==DOTA_GAMERULES_STATE_HERO_SELECTION or state==DOTA_GAMERULES_STATE_STRATEGY_TIME or state==DOTA_GAMERULES_STATE_WAIT_FOR_MAP_TO_LOAD then phase='hero_selection'
    elseif state==DOTA_GAMERULES_STATE_PRE_GAME then phase='pregame'
    elseif state==DOTA_GAMERULES_STATE_GAME_IN_PROGRESS then phase='playing'
    elseif state==DOTA_GAMERULES_STATE_POST_GAME or state==DOTA_GAMERULES_STATE_DISCONNECT then phase='postgame'
    else phase='waiting_engine' end
    if not self.room.started and (phase=='hero_selection' or phase=='pregame' or phase=='playing') then
        self:error('engine_advanced_before_host_start'); return 2
    end
    if self.room.phase~=phase then self.room.phase=phase; self.room:changed(false) end
    if self.transition_deadline and phase~='starting' then self.transition_deadline=nil end
    if self.transition_deadline and Time()>self.transition_deadline then self:error('setup_finish_did_not_advance');return 2 end
    if self.room.started and self.room.options.fill_bots and not self.filled and ((self.room.caps.tutorial_bots and state==DOTA_GAMERULES_STATE_STRATEGY_TIME) or (not self.room.caps.tutorial_bots and phase=='hero_selection')) then
        self.filled=true -- one-shot; retries must never create duplicate players
        self.bot_count_before=self:bot_count()
        local humans=0
        for _,p in pairs(self.room.players) do if p.team==2 or p.team==3 then humans=humans+1 end end
        self.bot_count_expected=math.max(self.bot_count_before,self.room.options.radiant_player_number+self.room.options.dire_player_number-humans)
        if self.bot_count_before>=self.bot_count_expected then
            self:emit('FILL','no_empty_slots')
        else
            if self.room.caps.tutorial_bots then

                local used={}
                if method(PlayerResource,'GetSelectedHeroName') then
                    for id=0,63 do if PlayerResource:IsValidPlayerID(id) then used[PlayerResource:GetSelectedHeroName(id) or '']=true end end
                end
                local pool=require('lan.bot_selection').draft(self.config.bot and self.config.bot.hero_pool,used,RandomInt)
                if #pool<self.bot_count_expected-self.bot_count_before then error('bot_hero_pool_exhausted') end
                local nextHero=1
                for team=2,3 do
                    local desired=team==2 and self.room.options.radiant_player_number or self.room.options.dire_player_number
                    local count=PlayerResource:GetPlayerCountForTeam(team)
                    for i=1,math.max(0,desired-count) do
                        if not pool[nextHero] then error('bot_hero_pool_exhausted') end
                        local hero='npc_dota_hero_'..pool[nextHero];used[hero]=true;nextHero=nextHero+1
                        Tutorial:AddBot(hero,'','',team==2)
                        self:emit('BOT_DRAFT',{team=team,hero=hero,selection='random_without_replacement'})
                    end
                end
            else GameRules:BotPopulate() end
            self.mode:SetBotThinkingEnabled(true)
            self.bot_fill_deadline=Time()+15
            self:emit('FILL',{method=self.room.caps.tutorial_bots and 'Tutorial:AddBot' or 'BotPopulate',expected=self.bot_count_expected,observed=self:bot_count()})
        end
    end
    if self.room.started and self.room.options.fill_bots and (phase=='pregame' or phase=='playing') and not self.tutorial_started then
        self.tutorial_started=true
        if self.room.caps.tutorial_bots and method(Tutorial,'StartTutorialMode') then Tutorial:StartTutorialMode() end
        self.mode:SetBotThinkingEnabled(true)
        self:emit('AI_ACTIVATE',{tutorial=self.room.caps.tutorial_bots,phase=phase})
    end
    if self.room.started then require('lan.rules').tick(self,phase) end
    if self.bot_hero_deadline and (phase=='pregame' or phase=='playing') and method(PlayerResource,'GetSelectedHeroEntity') then
        local heroes=0
        for id=0,63 do if PlayerResource:IsValidPlayerID(id) and method(PlayerResource,'IsFakeClient') and PlayerResource:IsFakeClient(id) and PlayerResource:GetSelectedHeroEntity(id) then heroes=heroes+1 end end
        if heroes>=self.bot_count_expected then self.bot_hero_deadline=nil;self:emit('BOT_HEROES',{expected=self.bot_count_expected,observed=heroes})
        elseif Time()>self.bot_hero_deadline then self.bot_hero_deadline=nil;self:emit('BOT_HERO_WARNING',{expected=self.bot_count_expected,observed=heroes}) end
    end
    if phase=='playing' and (not self.last_bot_sample or Time()-self.last_bot_sample>=10) then
        self.last_bot_sample=Time()
        if method(PlayerResource,'GetSelectedHeroEntity') then
            local samples={}
            for pid=0,63 do
                if PlayerResource:IsValidPlayerID(pid) and method(PlayerResource,'IsFakeClient') and PlayerResource:IsFakeClient(pid) then
                    local h=PlayerResource:GetSelectedHeroEntity(pid)
                    if h then local v=h:GetAbsOrigin();samples[#samples+1]={pid=pid,hero=h:GetUnitName(),x=math.floor(v.x),y=math.floor(v.y),alive=h:IsAlive()} end
                end
            end
            self:emit('AI_POSITIONS',samples)
        end
    end
    if self.bot_fill_deadline then
        local after=self:bot_count()
        if after>=self.bot_count_expected then
            self.bot_fill_deadline=nil; self.bot_hero_deadline=Time()+45; self:emit('FILL','bot_players_observed:'..after)
        elseif Time()>self.bot_fill_deadline then
            self.bot_fill_deadline=nil; self:error('bot_fill_incomplete; expected='..self.bot_count_expected..'; observed='..after);return 2
        end
    end
    if Time()-self.last_heartbeat>=2 then
        self.last_heartbeat=Time(); self:emit('STATE',self:publish())
    end
    return 0.5
end
function Engine:init()
    if method(Convars,'SetBool') then Convars:SetBool('sv_cheats',true) end
    self.mode=GameRules:GetGameModeEntity()
    if method(self.mode,'SetFreeCourierModeEnabled') then self.mode:SetFreeCourierModeEnabled(true) end
    require('lan.cheats').init(self)
    require('lan.runes').init(self)
    for _,name in ipairs({'EnableCustomGameSetupAutoLaunch','SetCustomGameSetupTimeout','FinishCustomGameSetup',
        'SetCustomGameTeamMaxPlayers','LockCustomGameSetupTeamAssignment','SetHeroSelectionTime','SetPreGameTime'}) do
        if not method(GameRules,name) then error('required GameRules API missing: '..name) end
    end
    if not method(self.mode,'SetPauseEnabled') then error('SetPauseEnabled missing') end
    self.room.caps={bot_thinking=method(self.mode,'SetBotThinkingEnabled'),bot_populate=method(GameRules,'BotPopulate') or method(Tutorial,'AddBot'),tutorial_bots=method(Tutorial,'AddBot')}
    self.room.bot_available=self.config.bot_available==true
    self.room.cheats=(method(Convars,'GetBool') and Convars:GetBool('sv_cheats')) or GameRules:IsCheatMode()
    GameRules:EnableCustomGameSetupAutoLaunch(false)
    GameRules:SetCustomGameSetupTimeout(-1)
    GameRules:SetCustomGameTeamMaxPlayers(DOTA_TEAM_GOODGUYS,5)
    GameRules:SetCustomGameTeamMaxPlayers(DOTA_TEAM_BADGUYS,5)
    GameRules:LockCustomGameSetupTeamAssignment(false)
    if self.room.caps.bot_thinking then self.mode:SetBotThinkingEnabled(false) end
    local missing={}
    for _,name in ipairs(self.config.bot_globals or {}) do
        if type(_G[name])~='function' then missing[#missing+1]=name end
    end
    self:emit('CAPS',{vm='addon_server_vm_not_native_bot_vm',missing_bot_globals=missing,
        note='absence_here_does_not_prove_absence_in_bot_vm'})
    self.listeners[#self.listeners+1]=CustomGameEventManager:RegisterListener('lan_action',function(source,keys)
        local ok,err=pcall(function() self:dispatch(source,keys) end)
        if not ok then self:error('event_exception:'..tostring(err)) end
    end)
    Convars:RegisterCommand('lan_status',function()
        if Convars:GetCommandClient()~=nil then return end
        self:emit('STATE',self:publish())
    end,'LAN addon status (server console only)',0)
    Convars:RegisterCommand('lan_release_host',function()
        if Convars:GetCommandClient()~=nil then return end
        if self.room.phase=='setup' then self.room.host=-1; self.room:elect_host(true); self:publish() end
    end,'Re-elect setup host after disconnect (server console only)',0)
    self.mode:SetContextThink('LANLabThink',function()
        local ok,delay=pcall(function() return self:tick() end)
        if not ok then self:error('tick_exception:'..tostring(delay));return 2 end
        return delay
    end,0.5)
    self:emit('BOOT',{client_revision=self.config.client_revision,source_sha256=self.config.source_sha256,sv_cheats=method(Convars,'GetBool') and Convars:GetBool('sv_cheats') or false,game_rules_cheats=GameRules:IsCheatMode()})
    self:publish()
end
return Engine
