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
