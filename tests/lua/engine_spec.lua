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
local emitted={};local mode={SetFreeCourierModeEnabled=function(_,v)emitted.free_courier=v end,SetPauseEnabled=function(_,v)assert(v==true)end,SetBotThinkingEnabled=function(_,v)emitted.thinking=v end,
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
engine:init();assert(emitted.free_courier==true);assert(emitted.autolaunch==false and emitted.timeout==-1 and emitted.thinking==false)
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
soloact('solo_start',{gold_percent=150,radiant_difficulty=2,dire_difficulty=4})
assert(solo.room.started and players[0].team==2 and solo.room.options.fill_bots)
assert(solo.room.options.gold_percent==150 and emitted.finish==before+1)
soloact('solo_start',{})
assert(emitted.finish==before+1)
-- Tutorial fill uses configured team sizes, once, at strategy time.
players={[0]={team=2,conn=2,name='Solo'}};state=2
local adds=0;local picked={}
local random_calls=0
RandomInt=function(lo,hi)assert(lo==1 and hi>=2);random_calls=random_calls+1;return 1 end
PlayerResource.GetSelectedHeroName=function(_,pid)return pid==0 and 'npc_dota_hero_axe' or '' end
local hero_pool={'axe','bane','bloodseeker','crystal_maiden','drow_ranger','juggernaut','mirana','nevermore','razor','sven'}
Tutorial={AddBot=function(_,hero,a,b,radiant) assert(not picked[hero]);picked[hero]=true;adds=adds+1;players[adds]={team=radiant and 2 or 3,conn=1,name='bot'} end}
PlayerResource.GetPlayerCountForTeam=function(_,team)local n=0;for _,p in pairs(players)do if p.team==team then n=n+1 end end;return n end
local tutorial=Engine.new({client_revision='v1',session=string.rep('d',32),source_sha256='fixture',bot_available=true,bot={hero_pool=hero_pool}})
tutorial:init();tutorial:tick()
local function tutorialact(action,opts)emitted.listener(100,{action=action,revision=tutorial.room.revision,client_revision='v1',options=opts})end
tutorialact('hello');tutorialact('solo_start',{radiant_player_number=4,dire_player_number=5,radiant_gold_multiplier=1.5})
assert(tutorial.room.started and tutorial.room.options.radiant_gold_multiplier==1.5)
state=4;tutorial:tick();assert(adds==8 and tutorial.bot_fill_deadline==nil)
tutorial:tick();assert(adds==8 and random_calls==8 and not picked.npc_dota_hero_axe and hero_pool[1]=='axe')

-- Tutorial fake clients can report CONNECTED instead of BOT.
PlayerResource.IsFakeClient=function(_,pid)return pid~=0 end
for pid,p in pairs(players) do p.conn=2 end
assert(tutorial:bot_count()==8)
tutorial:refresh_players();assert(tutorial.room.players[1]==nil)

local tutorialStarts=0
Tutorial.StartTutorialMode=function()tutorialStarts=tutorialStarts+1 end
state=6;emitted.thinking=false;tutorial:tick()
assert(tutorialStarts==1 and emitted.thinking)
tutorial:tick();assert(tutorialStarts==1)

-- Engine chat events, exact gold changes and level bounds.
local balance=600;local level=1
local hero={SetGold=function(_,n,reliable)if not reliable then balance=n end end,GetLevel=function()return level end,HeroLevelUp=function()level=level+1 end}
PlayerResource.GetSelectedHeroEntity=function()return hero end
PlayerResource.GetGold=function()return balance end
PlayerResource.GetUnreliableGold=function()return balance end
PlayerResource.GetReliableGold=function()return 0 end
Convars.GetBool=function()return true end
local chats=require('lan.cheats')
chats.handle(tutorial,{playerid=0,text='-gold 100'});assert(balance==700)
chats.handle(tutorial,{playerid=0,text='-lvlup 2'});assert(level==3)
chats.handle(tutorial,{playerid=0,text='-gold 100;quit'});assert(balance==700)
chats.handle(tutorial,{playerid=1,text='-gold 100'});assert(balance==700)

-- Menu targets selected side bots, never other humans, with fixed amounts.
tutorial.room.phase='playing';tutorial.room.players[0].hello=true
local amounts={[0]=600,[1]=600,[2]=600,[3]=600}
players={[0]={team=2,conn=2},[1]={team=2,conn=2},[2]={team=3,conn=2},[3]={team=3,conn=2}}
PlayerResource.GetTeam=function(_,pid)return players[pid].team end
PlayerResource.IsFakeClient=function(_,pid)return pid==1 or pid==2 end
PlayerResource.GetUnreliableGold=function(_,pid)return amounts[pid] end
PlayerResource.GetSelectedHeroEntity=function(_,pid)return {SetGold=function(_,n)amounts[pid]=n end} end
assert(chats.button(tutorial,0,'ally_gold'));assert(amounts[1]==1600 and amounts[0]==600 and amounts[2]==600)
assert(chats.button(tutorial,0,'enemy_gold'));assert(amounts[2]==1600 and amounts[3]==600)
assert(not chats.button(tutorial,0,'arbitrary_command'))
tutorial.room.phase='setup';assert(not chats.button(tutorial,0,'self_gold'))

-- Self-only ability allowlist, duplicate/failure handling and reversible BAT.
tutorial.room.phase='playing'
local abilities={};local bat=1.7
local ownHero={GetBaseAttackTime=function(_,ignoreModifiers)assert(ignoreModifiers==false);return bat end,SetBaseAttackTime=function(_,v)bat=v end,
 FindAbilityByName=function(_,name)return abilities[name] end,GetAbilityByIndex=function()return {} end,
 AddAbility=function(_,name)
  local a={GetMaxLevel=function()return 4 end,SetLevel=function(self,n)self.level=n end,GetLevel=function(self)return self.level end}
  abilities[name]=a;return a
 end}
PlayerResource.GetSelectedHeroEntity=function(_,pid)assert(pid==0);return ownHero end
assert(chats.button(tutorial,0,'self_bat_down'));assert(math.abs(bat-1.6)<0.0001)
assert(chats.button(tutorial,0,'self_bat_up'));assert(math.abs(bat-1.7)<0.0001)
assert(chats.button(tutorial,0,'self_bat_down'));assert(chats.button(tutorial,0,'self_bat_reset'));assert(bat==1.7)
for name in pairs(chats.abilities) do
 assert(chats.button(tutorial,0,'self_ability_'..name));assert(abilities[name].level==4)
 assert(not chats.button(tutorial,0,'self_ability_'..name))
end
assert(not chats.button(tutorial,0,'self_ability_arbitrary'))
GetAbilityKeyValuesByName=function(name)return name=='axe_berserkers_call' and {AbilityType='DOTA_ABILITY_TYPE_BASIC'} or nil end
assert(chats.button(tutorial,0,'self_add_ability','  axe_berserkers_call  '));assert(abilities.axe_berserkers_call.level==4)
assert(not chats.button(tutorial,0,'self_add_ability','axe_berserkers_call'))
for _,invalid in ipairs({'','does_not_exist','axe_berserkers_call;quit','dota_create_ability axe_berserkers_call',string.rep('a',129)}) do assert(not chats.button(tutorial,0,'self_add_ability',invalid)) end
assert(not chats.button(tutorial,0,'self_add_ability',{}))
tutorial.room.players[0].hello=false;assert(not chats.button(tutorial,0,'self_add_ability','axe_berserkers_call'));tutorial.room.players[0].hello=true
ownHero.AddAbility=function()error('engine rejected ability')end;abilities={}
assert(not chats.button(tutorial,0,'self_ability_bloodseeker_thirst'))
assert(tutorial.room.phase=='playing')
tutorial.room.players[0].hello=false;assert(not chats.button(tutorial,0,'self_bat_up'))
tutorial.room.players[0].hello=true
bat=0.1;assert(not chats.button(tutorial,0,'self_bat_down'));assert(bat==0.1)
-- River-only spawn filter rejects bounty/xp and unknown spawners.
local runes=require('lan.runes')
EntIndexToHScript=function(id)
 local classes={[1]='dota_item_rune_spawner_powerup',[2]='dota_item_rune_spawner_bounty',[3]='dota_item_rune_spawner_xp'}
 return classes[id] and {GetClassname=function()return classes[id]end} or nil
end
assert(runes.allow({spawner_entindex_const=1}))
assert(not runes.allow({spawner_entindex_const=2}))
assert(not runes.allow({spawner_entindex_const=3}))
assert(not runes.allow({}))

-- Native per-hero difficulty is applied independently and never to humans.
local rules=require('lan.rules')
tutorial.room.options.radiant_difficulty=1;tutorial.room.options.dire_difficulty=4
local assigned={}
local function botHero(pid,team)
 return {IsRealHero=function()return true end,IsIllusion=function()return false end,
 GetPlayerOwnerID=function()return pid end,GetTeamNumber=function()return team end,
 SetBotDifficulty=function(_,d)assigned[pid]=d end}
end
rules.apply_bot_difficulty(tutorial,botHero(1,2))
rules.apply_bot_difficulty(tutorial,botHero(2,3))
rules.apply_bot_difficulty(tutorial,botHero(0,2))
assert(assigned[1]==1 and assigned[2]==4 and assigned[0]==nil)

-- Disconnects and pauses do not become our own game-end/unpause actions.
local lifecycle_values={}
Convars.SetBool=function(_,k,v)lifecycle_values[k]=v end
Convars.SetInt=function(_,k,v)lifecycle_values[k]=v end
require('lan.lifecycle').init(tutorial)
assert(lifecycle_values.dota_surrender_on_disconnect==false)
assert(lifecycle_values.sv_hibernate_when_empty==false)
assert(lifecycle_values.dota_pause_force_unpause_time==2147483647)
assert(lifecycle_values.dota_auto_surrender_all_disconnected_timeout==2147483647)
PlayerResource.GetSelectedHeroEntity=function()return nil end
state=7;players[0].conn=3;tutorial:tick()
assert(tutorial.room.phase=='playing' and tutorial.room.started)
state=8;tutorial:tick();assert(tutorial.room.phase=='postgame')

-- Adaptive rewards are independent per bot and preserve small fractional ticks.
local comeback=require('lan.bot_comeback')
local heroes={}
local ce={room={phase='playing',options={radiant_gold_multiplier=1.5,dire_gold_multiplier=1,radiant_xp_multiplier=1,dire_xp_multiplier=2,gold_percent=100}},emit=function()end}
PlayerResource.IsValidPlayerID=function(_,p)return p==0 or p==1 or p==2 end
PlayerResource.IsFakeClient=function(_,p)return p~=0 end
PlayerResource.GetSelectedHeroEntity=function(_,p)return heroes[p] end
local function victim(pid)
 return {IsRealHero=function()return true end,IsIllusion=function()return false end,
 GetPlayerOwnerID=function()return pid end,GetTeamNumber=function()return pid==2 and 3 or 2 end}
end
for pid=0,2 do heroes[pid]=victim(pid) end
comeback.killed(ce,heroes[0]);assert(comeback.bonus(ce,0,'gold')==0)
comeback.killed(ce,heroes[1]);comeback.killed(ce,heroes[1])
assert(ce.bot_death_bonus[1]==2 and comeback.bonus(ce,2,'gold')==0)
assert(comeback.scale(ce,1,'gold',100,1.5)==190)
assert(comeback.scale(ce,1,'xp',100,1)==120)
assert(comeback.scale(ce,2,'xp',100,2)==200)
assert(comeback.scale(ce,0,'gold',100,1.5)==150)
assert(comeback.scale(ce,1,'gold',-100,1.5)==-100)
local total=0;for i=1,10 do total=total+comeback.scale(ce,1,'gold',1,1) end;assert(total==14)
comeback.killed(ce,victim(1));assert(ce.bot_death_bonus[1]==2)
heroes[1].IsReincarnating=function()return true end;comeback.killed(ce,heroes[1]);assert(ce.bot_death_bonus[1]==2)
heroes[1].IsReincarnating=nil;heroes[1].IsIllusion=function()return true end;comeback.killed(ce,heroes[1]);assert(ce.bot_death_bonus[1]==2)
comeback.killed(ce,heroes[2]);assert(ce.bot_death_bonus[2]==1)
assert(comeback.bonus({room=ce.room},1,'gold')==0)

-- A credited enemy hero kill resets both multipliers to exactly 1x, even
-- when the configured side baseline is higher; subsequent deaths start there.
heroes[1].IsIllusion=function()return false end
comeback.hero_kill(ce,heroes[2],heroes[1])
assert(ce.bot_death_bonus[1]==0 and ce.bot_income_reset[1])
assert(comeback.scale(ce,1,'gold',100,1.5)==100)
assert(comeback.scale(ce,1,'xp',100,2)==100)
assert(ce.bot_reward_remainders[1]==nil)
comeback.killed(ce,heroes[1])
assert(comeback.scale(ce,1,'gold',100,1.5)==120)
assert(comeback.scale(ce,1,'xp',100,2)==110)
comeback.hero_kill(ce,heroes[0],heroes[1]);assert(ce.bot_death_bonus[1]==1) -- ally deny
comeback.hero_kill(ce,{IsRealHero=function()return false end},heroes[1]);assert(ce.bot_death_bonus[1]==1)
comeback.hero_kill(ce,heroes[1],heroes[2]);assert(ce.bot_death_bonus[2]==0 and ce.bot_death_bonus[1]==1)
