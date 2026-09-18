local Room=require('lan.room')
local t=0; local r=Room.new(function() return t end,'v1')
local a={pid=0,identity='a',name='A',team=0,connected=true}
local b={pid=1,identity='b',name='B',team=0,connected=true}
r:sync({a,b});r.phase='setup'
assert(r.host==-1)
assert(not r:hello(0,'wrong'))
assert(r:hello(0,'v1'));assert(r:hello(1,'v1'));assert(r.host==0)
assert(not r:set_options(1,r.revision,{}))
assert(not r:check_team(0,r.revision-1,2,1))
assert(not r:check_team(0,r.revision,2,0))
assert(r:check_team(0,r.revision,2,1));r:assign(0,2,1)
assert(not r:check_team(1,r.revision,2,1))
assert(r:check_team(1,r.revision,3,2));r:assign(1,3,2)
assert(r:set_ready(0,r.revision,true));assert(not r:can_start(0,r.revision))
assert(r:set_ready(1,r.revision,true));assert(r:can_start(0,r.revision))
assert(r:set_options(0,r.revision,{selection_seconds=80}));assert(not r.players[0].ready)
assert(not r:set_options(0,r.revision,{cheats=true}))
assert(not r:set_options(0,r.revision,{selection_seconds=5}))
assert(not r:set_options(0,r.revision,{bot_mode='tiandixing_native_lab'}))
r.bot_available=true
assert(r:set_options(0,r.revision,{bot_mode='tiandixing_native_lab',fill_bots=true}))
assert(r:set_ready(0,r.revision,true));assert(r:set_ready(1,r.revision,true))
local ok,e=r:can_start(0,r.revision);assert(not ok and e=='experimental_ack_required')
assert(r:set_options(0,r.revision,{bot_mode='tiandixing_native_lab',fill_bots=true,ack_unverified=true}))
r:set_ready(0,r.revision,true);r:set_ready(1,r.revision,true)
ok,e=r:can_start(0,r.revision);assert(not ok and e=='bot_thinking_api_missing')
r.caps={bot_thinking=true,bot_populate=true}
ok,e=r:can_start(0,r.revision);assert(not ok and e=='bot_populate_requires_explicit_cheats')
r.cheats=true;assert(r:can_start(0,r.revision))
assert(r:transfer(0,r.revision,1));assert(r.host==1)
a.team=2;b.team=3;b.connected=false;r:sync({a,b});assert(r.host==1)
assert(not r.players[1].hello)
t=31;r:elect_host();assert(r.host==0);assert(not r.players[0].ready)
-- A reused player slot must not inherit auth/role/ready.
a.identity='new';r:sync({a,b});assert(not r.players[0].hello and r.players[0].role==0)
r:hello(0,'v1');r:assign(0,2,3);r:set_ready(0,r.revision,true)
r:elect_host(true);assert(r:can_start(0,r.revision));r:begin()
assert(not r:can_start(0,r.revision));assert(not r:check_team(0,r.revision,3,3))
local snapshot=r:snapshot();assert(snapshot.players[1].identity==nil)
r:fail('test');assert(r.phase=='error' and r.started)
print('room_spec: authority, revisions, ready, host, slots and cheat gates PASS')
-- Trimmed personal-match options: native difficulty and explicit multiplier presets.
do
 local r=Room.new(function()return 0 end,'v1')
 r:sync({{pid=0,identity='solo',connected=true,team=2,name='Solo'}})
 r:hello(0,'v1');r.phase='setup'
 assert(r:set_options(0,r.revision,{radiant_difficulty=4,dire_difficulty=0,radiant_gold_multiplier=1.25,dire_xp_multiplier=1.35}))
 assert(r:set_options(0,r.revision,{radiant_gold_multiplier=5}))
 assert(not r:set_options(0,r.revision,{radiant_gold_multiplier=5.1}))
 assert(not r:set_options(0,r.revision,{radiant_gold_multiplier=1.1}))
 assert(not r:set_options(0,r.revision,{universal_shop=1}))
end

do
 local r=Room.new(function()return 0 end,'v1')
 r:sync({{pid=0,identity='solo',connected=true,team=2,name='Solo'}})
 r:hello(0,'v1');r.phase='setup'
 assert(r:set_options(0,r.revision,{radiant_difficulty=0,dire_difficulty=4}))
 assert(r.options.radiant_difficulty==0 and r.options.dire_difficulty==4)
 for _,key in ipairs({'difficulty','radiant_lvl_start','dire_lvl_start','bot_protection','anti_diving','allow_pause'}) do
  assert(not r:set_options(0,r.revision,{[key]=1}))
 end
 assert(not r:set_options(0,r.revision,{dire_difficulty=5}))
end

do
 local r=Room.new(function()return 0 end,'v1')
 r:sync({{pid=0,identity='solo',connected=true,team=2,name='Solo'}})
 r:hello(0,'v1');r.phase='setup'
 for n=4,12 do assert(r:set_options(0,r.revision,{radiant_player_number=n,dire_player_number=n})) end
 for _,n in ipairs({1,2,3,13}) do assert(not r:set_options(0,r.revision,{radiant_player_number=n})) end
end

-- Random drafts exclude selected heroes, never mutate the source, and support 12v12.
do
 local draft=require('lan.bot_selection').draft
 local supported={}
 for i=1,53 do supported[i]='hero_'..i end
 supported[54]='hero_2' -- duplicates in input cannot produce duplicate bots
 local used={npc_dota_hero_hero_1=true}
 local a=draft(supported,used,function(lo,hi)return lo end)
 local b=draft(supported,used,function(lo,hi)return hi end)
 assert(#a==52 and #b==52 and a[1]~=b[1] and supported[1]=='hero_1')
 local seen={}
 for i=1,23 do assert(not seen[a[i]] and a[i]~='hero_1');seen[a[i]]=true end
 assert(not pcall(draft,nil,used,function()return 1 end))
end
