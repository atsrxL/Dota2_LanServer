-- Engine-independent authoritative setup model. Lua 5.1-compatible subset.
local Room = {}; Room.__index = Room
local function copy(t) local out={} for k,v in pairs(t) do out[k]=v end return out end
local function integer(v,lo,hi) return type(v)=='number' and v==math.floor(v) and v>=lo and v<=hi end
local function default_options()
    return {bot_mode='none', fill_bots=false, ack_unverified=false, radiant_difficulty=1, dire_difficulty=4,
            selection_seconds=60, pregame_seconds=30, gold_percent=100,radiant_gold_multiplier=1,radiant_xp_multiplier=1,radiant_gold_start=600,radiant_player_number=5,dire_gold_multiplier=1,dire_xp_multiplier=1,dire_gold_start=600,dire_player_number=5,respawn_time_percentage=30,buyback_cooldown=60,tower_power=1,tower_endure=1,max_level=50,}
end
function Room.new(clock, revision)
    return setmetatable({clock=clock, client_revision=revision, revision=1, phase='waiting_engine',
        players={}, host=-1, host_missing_since=nil, options=default_options(), error='',
        started=false, bot_available=false, cheats=false, caps={}, last_action={}},Room)
end
function Room:changed(reset)
    self.revision=self.revision+1
    if reset then for _,p in pairs(self.players) do p.ready=false end end
end
function Room:sync(roster)
    local next_players={}; local changed=false
    for _,incoming in ipairs(roster) do
        local pid=incoming.pid
        if integer(pid,0,63) then
            local p=self.players[pid]
            if not p or p.identity~=incoming.identity then
                p={pid=pid,identity=incoming.identity,ready=false,hello=false,role=0}; changed=true
            end
            if p.connected~=incoming.connected then p.hello=false end
            if p.connected~=incoming.connected or p.team~=incoming.team then changed=true; p.ready=false end
            p.connected=incoming.connected; p.team=incoming.team; p.name=incoming.name
            next_players[pid]=p
        end
    end
    for pid in pairs(self.players) do if not next_players[pid] then changed=true end end
    self.players=next_players
    if changed then self:changed(true) end
    self:elect_host()
end
function Room:elect_host(force)
    if self.started then return end
    local owner=self.players[self.host]
    if not force and owner and owner.connected and owner.hello then self.host_missing_since=nil; return end
    if not force and self.host>=0 then
        self.host_missing_since=self.host_missing_since or self.clock()
        if self.clock()-self.host_missing_since<30 then return end
    end
    local best=nil
    for pid,p in pairs(self.players) do
        if p.connected and p.hello and (not best or pid<best) then best=pid end
    end
    local chosen=best or -1
    if chosen~=self.host then self.host=chosen; self:changed(false) end
    self.host_missing_since=nil
end
function Room:hello(pid, version)
    local p=self.players[pid]
    if not p or not p.connected then return false,'player_not_connected' end
    if version~=self.client_revision then return false,'client_revision_mismatch' end
    if not p.hello then p.hello=true; p.ready=false; self:changed(false) end
    self:elect_host(); return true
end
function Room:authorize(pid, expected, owner_only)
    if self.phase~='setup' or self.started then return false,'not_in_setup' end
    local p=self.players[pid]
    if not p or not p.connected or not p.hello then return false,'ui_handshake_required' end
    if not integer(expected,1,2147483647) or expected~=self.revision then return false,'stale_revision' end
    if owner_only and pid~=self.host then return false,'host_only' end
    return true
end
function Room:check_team(pid,expected,team,role)
    local ok,err=self:authorize(pid,expected,false); if not ok then return false,err end
    if (team~=2 and team~=3) or not integer(role,1,5) then return false,'invalid_team_or_role' end
    local count=0
    for other,p in pairs(self.players) do
        if other~=pid and p.team==team then
            count=count+1
            if p.role==role then return false,'role_taken' end
        end
    end
    if count>=5 then return false,'team_full' end
    return true
end
function Room:assign(pid,team,role)
    local p=self.players[pid]; p.team=team; p.role=role; self:changed(true)
end
function Room:set_options(pid,expected,raw)
    local ok,err=self:authorize(pid,expected,true); if not ok then return false,err end
    if type(raw)~='table' then return false,'invalid_options' end
    local value=default_options()
    for key in pairs(raw) do if value[key]==nil then return false,'unknown_option' end end
    for key in pairs(value) do if raw[key]~=nil then value[key]=raw[key] end end
    if value.bot_mode~='none' and value.bot_mode~='tiandixing_native_lab' then return false,'invalid_bot_mode' end
    for _,key in ipairs({'fill_bots','ack_unverified'}) do
        if type(value[key])~='boolean' then return false,'invalid_boolean' end
    end
    if not integer(value.radiant_difficulty,0,4) or not integer(value.dire_difficulty,0,4) or not integer(value.selection_seconds,30,120)
        or not integer(value.pregame_seconds,10,60) or not integer(value.gold_percent,25,1000) then return false,'invalid_number' end
    if not ({[1]=true,[1.15]=true,[1.25]=true,[1.35]=true,[1.5]=true,[1.75]=true,[2]=true,[2.5]=true,[3]=true,[4]=true,[5]=true})[value.radiant_gold_multiplier] then return false,'invalid_number' end
    if not ({[1]=true,[1.15]=true,[1.25]=true,[1.35]=true,[1.5]=true,[1.75]=true,[2]=true,[2.5]=true,[3]=true,[4]=true,[5]=true})[value.radiant_xp_multiplier] then return false,'invalid_number' end
    if not ({[600]=true,[1000]=true,[1700]=true,[3200]=true,[6000]=true,[10000]=true,[100000]=true})[value.radiant_gold_start] then return false,'invalid_number' end
    if not ({[4]=true,[5]=true,[6]=true,[7]=true,[8]=true,[9]=true,[10]=true,[11]=true,[12]=true})[value.radiant_player_number] then return false,'invalid_number' end
    if not ({[1]=true,[1.15]=true,[1.25]=true,[1.35]=true,[1.5]=true,[1.75]=true,[2]=true,[2.5]=true,[3]=true,[4]=true,[5]=true})[value.dire_gold_multiplier] then return false,'invalid_number' end
    if not ({[1]=true,[1.15]=true,[1.25]=true,[1.35]=true,[1.5]=true,[1.75]=true,[2]=true,[2.5]=true,[3]=true,[4]=true,[5]=true})[value.dire_xp_multiplier] then return false,'invalid_number' end
    if not ({[600]=true,[1000]=true,[1700]=true,[3200]=true,[6000]=true,[10000]=true,[100000]=true})[value.dire_gold_start] then return false,'invalid_number' end
    if not ({[4]=true,[5]=true,[6]=true,[7]=true,[8]=true,[9]=true,[10]=true,[11]=true,[12]=true})[value.dire_player_number] then return false,'invalid_number' end
    if not ({[0]=true,[10]=true,[25]=true,[30]=true,[50]=true,[75]=true,[100]=true})[value.respawn_time_percentage] then return false,'invalid_number' end
    if not ({[0]=true,[30]=true,[60]=true,[120]=true,[240]=true,[480]=true})[value.buyback_cooldown] then return false,'invalid_number' end
    if not ({[1]=true,[2]=true,[3]=true,[4]=true,[5]=true,[6]=true,[7]=true,[8]=true,[9]=true,[10]=true})[value.tower_power] then return false,'invalid_number' end
    if not ({[1]=true,[2]=true,[3]=true,[4]=true,[5]=true,[6]=true,[7]=true,[8]=true,[9]=true,[10]=true})[value.tower_endure] then return false,'invalid_number' end
    if not ({[30]=true,[50]=true,[100]=true,[200]=true,[400]=true,[800]=true,[1600]=true})[value.max_level] then return false,'invalid_number' end
    if value.bot_mode=='none' and value.fill_bots then return false,'fill_requires_bot_mode' end
    if value.bot_mode~='none' and not self.bot_available then return false,'bot_snapshot_missing' end
    self.options=value; self:changed(true); return true
end
function Room:set_ready(pid,expected,ready)
    local ok,err=self:authorize(pid,expected,false); if not ok then return false,err end
    local p=self.players[pid]
    if type(ready)~='boolean' then return false,'invalid_boolean' end
    if (p.team~=2 and p.team~=3) or p.role==0 then return false,'choose_team_and_role' end
    p.ready=ready; self:changed(false); return true
end
function Room:transfer(pid,expected,target)
    local ok,err=self:authorize(pid,expected,true); if not ok then return false,err end
    local p=self.players[target]
    if not p or not p.connected or not p.hello then return false,'target_unavailable' end
    self.host=target; self.host_missing_since=nil; self:changed(false); return true
end
function Room:can_start(pid,expected)
    local ok,err=self:authorize(pid,expected,true); if not ok then return false,err end
    local humans=0
    for _,p in pairs(self.players) do
        if p.connected then
            humans=humans+1
            if not p.hello or not p.ready or (p.team~=2 and p.team~=3) then return false,'players_not_ready' end
        end
    end
    if humans==0 then return false,'no_players' end
    if self.options.bot_mode~='none' then
        if not self.bot_available then return false,'bot_snapshot_missing' end
        if not self.options.ack_unverified then return false,'experimental_ack_required' end
        if not self.caps.bot_thinking then return false,'bot_thinking_api_missing' end
        if self.options.fill_bots and (not self.caps.bot_populate or (not self.caps.tutorial_bots and not self.cheats)) then
            return false,'bot_populate_requires_explicit_cheats'
        end
    end
    return true
end
function Room:begin()
    self.started=true; self.phase='starting'; self:changed(false)
end
function Room:fail(message)
    self.error=tostring(message); self.phase='error'; self.started=true; self:changed(false)
end
function Room:snapshot()
    local rows={}
    for _,p in pairs(self.players) do rows[#rows+1]={pid=p.pid,name=p.name,team=p.team,role=p.role,
        ready=p.ready and 1 or 0,hello=p.hello and 1 or 0,connected=p.connected and 1 or 0} end
    table.sort(rows,function(a,b) return a.pid<b.pid end)
    return {schema=1,client_revision=self.client_revision,phase=self.phase,revision=self.revision,
        host=self.host,players=rows,options=copy(self.options),error=self.error,
        bot_available=self.bot_available and 1 or 0,cheats=self.cheats and 1 or 0,
        capabilities=copy(self.caps),roles_are_preferences=1}
end
return Room
