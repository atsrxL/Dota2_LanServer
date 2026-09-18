-- All engine APIs below are MOCKS. This verifies our event/state logic only.
local Engine=require('lan.engine')
DOTA_TEAM_GOODGUYS=2;DOTA_TEAM_BADGUYS=3
DOTA_CONNECTION_STATE_CONNECTED=2;DOTA_CONNECTION_STATE_BOT=1
DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP=2;DOTA_GAMERULES_STATE_HERO_SELECTION=3
DOTA_GAMERULES_STATE_STRATEGY_TIME=4;DOTA_GAMERULES_STATE_WAIT_FOR_MAP_TO_LOAD=5
DOTA_GAMERULES_STATE_PRE_GAME=6;DOTA_GAMERULES_STATE_GAME_IN_PROGRESS=7
DOTA_GAMERULES_STATE_POST_GAME=8;DOTA_GAMERULES_STATE_DISCONNECT=9
local clock=0;Time=function()return clock end
local players={[0]={team=0,conn=2,name='A'},[1]={team=0,conn=2,name='B'}}
EntIndexToHScript=function(id) return players[id-100] end
PlayerResource={
 IsValidPlayerID=function(_,i)return players[i]~=nil end,
 GetConnectionState=function(_,i)return players[i].conn end,
 GetPlayer=function(_,i)return players[i] end,
 GetCustomTeamAssignment=function(_,i)return players[i].team end,
 SetCustomTeamAssignment=function(_,i,t)players[i].team=t end,
 GetSteamAccountID=function(_,i)return i+1 end,
 GetPlayerName=function(_,i)return players[i].name end}
local emitted={};local mode={SetPauseEnabled=function()end,SetBotThinkingEnabled=function(_,v)emitted.thinking=v end,
 SetContextThink=function(_,name,fn)emitted.tick=fn end}
local state=2;local cheat=false
GameRules={GetGameModeEntity=function()return mode end,IsCheatMode=function()return cheat end,
 State_Get=function()return state end,
 EnableCustomGameSetupAutoLaunch=function(_,v)emitted.autolaunch=v end,
 SetCustomGameSetupTimeout=function(_,v)emitted.timeout=v end,
 SetCustomGameTeamMaxPlayers=function()end,LockCustomGameSetupTeamAssignment=function()end,
 SetHeroSelectionTime=function()end,SetPreGameTime=function()end,
 FinishCustomGameSetup=function()emitted.finish=(emitted.finish or 0)+1;state=3 end,
 BotPopulate=function()emitted.fill=(emitted.fill or 0)+1;for i=2,9 do players[i]={team=i<5 and 2 or 3,conn=1,name='bot'} end end}
CustomNetTables={SetTableValue=function(_,table,key,value) emitted.state=value end}
CustomGameEventManager={RegisterListener=function(_,name,fn)emitted.listener=fn;return 1 end,
 Send_ServerToPlayer=function(_,p,name,data)emitted.reply=data end}
Convars={RegisterCommand=function()end,GetCommandClient=function()return nil end}
SendToServerConsole=function(s)assert(not s:find('sv_cheats'));end
PauseGame=function(v)emitted.pause=v end
local engine=Engine.new({client_revision='v1',session=string.rep('a',32),source_sha256='fixture',bot_available=true,bot_globals={'GetBot'}})
engine:init();assert(emitted.autolaunch==false and emitted.timeout==-1 and emitted.thinking==false)
engine:tick();assert(engine.room.phase=='setup' and not engine.room.started)
local function act(id,action,data)
 local k=data or {};k.action=action;k.revision=engine.room.revision;k.client_revision='v1'
 emitted.listener(100+id,k)
end
act(0,'hello');act(1,'hello');assert(engine.room.host==0)
-- Forged payload identity is ignored; engine source belongs to player 1.
act(1,'options',{PlayerID=0,options={selection_seconds=90}})
assert(emitted.reply.ok==0 and engine.room.options.selection_seconds==60)
act(0,'options',{options={selection_seconds={1}}});assert(emitted.reply.ok==0 and engine.room.phase=='setup')
act(0,'team',{team=2,role=1});act(1,'team',{team=3,role=2})
act(0,'options',{options={bot_mode='tiandixing_native_lab',fill_bots=1,ack_unverified=1}})
act(0,'ready',{ready=1});act(1,'ready',{ready=1});act(0,'start')
assert(not engine.room.started and emitted.reply.message=='bot_populate_requires_explicit_cheats')
cheat=true;act(0,'start');assert(engine.room.started and emitted.finish==1 and emitted.thinking)
act(0,'start');assert(emitted.finish==1)
clock=3;engine:tick();assert(emitted.fill==1 and engine.bot_fill_deadline==nil)
clock=6;engine:tick();assert(emitted.fill==1)
state=7;engine:tick();assert(engine.room.phase=='playing')
engine:error('fixture_error');clock=20;engine:tick();assert(emitted.state.phase=='error' and emitted.pause)
-- Engine advancing without a host click is surfaced, never treated as success.
local other=Engine.new({client_revision='v1',session=string.rep('b',32),source_sha256='fixture',bot_available=false})
state=2;other:init();other:tick();state=3;other:tick();assert(other.room.phase=='error')
print('engine_spec: MOCK waiting/identity/invalid input/start/fill/heartbeat/watchdog PASS')

-- Dedicated INIT recovery must not force hero selection or bypass host start.
DOTA_GAMERULES_STATE_INIT=0
state=0
local resets=0
GameRules.ResetToCustomGameSetup=function() resets=resets+1;state=2 end
local recovered=Engine.new({client_revision='v1',session=string.rep('b',32),source_sha256='fixture'})
recovered:init();recovered:tick()
assert(resets==1 and recovered.room.phase=='setup' and not recovered.room.started)
recovered:tick();assert(resets==1)

-- Positive rewards scale; spending and losses remain unchanged.
local filter
mode.SetModifyGoldFilter=function(_,fn,ctx) filter=function(e)return fn(ctx,e)end end
mode.SetFilterMoreGold=function(_,enabled) assert(enabled) end
recovered.room.options.gold_percent=200
recovered:start_match()
local gain={gold=37};assert(filter(gain) and gain.gold==74)
local loss={gold=-100};assert(filter(loss) and loss.gold==-100)
local zero={gold=0};assert(filter(zero) and zero.gold==0)

-- Solo confirmation validates authority/count and starts only once.
players={[0]={team=5,conn=2,name='Solo'}};state=2;cheat=true
local solo=Engine.new({client_revision='v1',session=string.rep('c',32),source_sha256='fixture',bot_available=true})
solo:init();solo:tick()
local function soloact(action,opts)
 emitted.listener(100,{action=action,revision=solo.room.revision,client_revision='v1',options=opts})
end
soloact('hello')
players[1]={team=5,conn=2,name='Other'};solo:tick()
soloact('solo_start',{})
assert(emitted.reply.message=='solo_requires_one_player' and not solo.room.started)
players[1]=nil;solo:tick()
soloact('solo_start',{gold_percent=0})
assert(not solo.room.started)
local before=emitted.finish
soloact('solo_start',{gold_percent=150,difficulty=2,allow_pause=1})
assert(solo.room.started and players[0].team==2 and solo.room.options.fill_bots)
assert(solo.room.options.gold_percent==150 and emitted.finish==before+1)
soloact('solo_start',{})
assert(emitted.finish==before+1)
-- Tutorial fill uses configured team sizes, once, at strategy time.
players={[0]={team=2,conn=2,name='Solo'}};state=2
local adds=0
Tutorial={AddBot=function(_,hero,a,b,radiant) adds=adds+1;players[adds]={team=radiant and 2 or 3,conn=1,name='bot'} end}
PlayerResource.GetPlayerCountForTeam=function(_,team)local n=0;for _,p in pairs(players)do if p.team==team then n=n+1 end end;return n end
local tutorial=Engine.new({client_revision='v1',session=string.rep('d',32),source_sha256='fixture',bot_available=true})
tutorial:init();tutorial:tick()
local function tutorialact(action,opts)emitted.listener(100,{action=action,revision=tutorial.room.revision,client_revision='v1',options=opts})end
tutorialact('hello');tutorialact('solo_start',{radiant_player_number=3,dire_player_number=4,radiant_gold_multiplier=1.5})
assert(tutorial.room.started and tutorial.room.options.radiant_gold_multiplier==1.5)
state=4;tutorial:tick();assert(adds==6 and tutorial.bot_fill_deadline==nil)
tutorial:tick();assert(adds==6)

-- Tutorial fake clients can report CONNECTED instead of BOT.
PlayerResource.IsFakeClient=function(_,pid)return pid~=0 end
for pid,p in pairs(players) do p.conn=2 end
assert(tutorial:bot_count()==6)
tutorial:refresh_players();assert(tutorial.room.players[1]==nil)
