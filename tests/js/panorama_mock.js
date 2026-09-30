/* Test fixture only: NOT a Panorama implementation or an in-game screenshot. */
'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const base=process.argv[2];
const xml=fs.readFileSync(base+'/layout/custom_game/lan_setup.xml','utf8');
const source=fs.readFileSync(base+'/scripts/custom_game/lan_setup.js','utf8');
const all=new Map(),sent=[],handlers={},listeners={},schedules=[];
function panel(id='') {
 const p={id,text:'',checked:false,enabled:true,selected:null,children:[],events:{},classes:{},
 GetChild(){return {text:''};},SetPanelEvent(e,fn){this.events[e]=fn;},SetSelected(x){this.selected=x;},GetSelected(){return this.selected?{id:this.selected}:null;},
 SetHasClass(k,v){this.classes[k]=v;},AddClass(k){this.classes[k]=true;},
 RemoveAndDeleteChildren(){this.children=[];},RemoveAllOptions(){this.children=[];this.selected=null;},
 AddOption(q){if(!this.selected)this.selected=q.id;},IsValid(){return true;}};
 if(id)all.set(id,p);return p;
}
for(const m of xml.matchAll(/\bid="([^"]+)"/g)){assert(!all.has(m[1]),'duplicate XML id '+m[1]);panel(m[1]);}
const context={FindChildTraverse(id){assert(all.has(id),'JS references absent XML id '+id);return all.get(id);},IsValid(){return true;}};
let current=null;
const sandbox={console,JSON,Object,String,Number,
 $:{GetContextPanel:()=>context,CreatePanel(type,parent,id){let p=panel(id);parent.children.push(p);return p;},Schedule(delay,fn){schedules.push(fn);}},
 Game:{GetLocalPlayerID:()=>0},
 GameEvents:{SendCustomGameEventToServer(name,data){assert(name==='lan_action');assert(!('PlayerID' in data));sent.push(data);},Subscribe(name,fn){handlers[name]=fn;}},
 CustomNetTables:{SubscribeNetTableListener(name,fn){listeners[name]=fn;},GetTableValue(){return current;}}};

sandbox.$=Object.assign(function(selector){return all.get(selector.slice(1));},sandbox.$);
const create=sandbox.$.CreatePanel;
sandbox.$.CreatePanel=function(type,parent,id,attrs){const p=create(type,parent,id);Object.assign(p,attrs||{});return p;};
vm.runInNewContext(source,sandbox,{filename:'lan_setup.js'});
assert(sent[0].action==='hello');
current={phase:'setup',revision:9,host:0,players:[{pid:0,hello:1}],bot_available:1,options:{radiant_difficulty:2,dire_difficulty:4,gold_percent:100,selection_seconds:60,pregame_seconds:30,allow_pause:1}};
listeners.lan_room('lan_room','state',current);
all.get('radiant_player_number').SetSelected('8');
all.get('radiant_player_number').events.oninputsubmit();
all.get('Start').events.onactivate();
assert(sent.at(-1).action==='solo_start' && sent.at(-1).options.radiant_player_number===8);
assert(!all.get('Start').enabled);
handlers.lan_reply({ok:0,message:'invalid_number'});assert(all.get('Start').enabled);
current.phase='playing';listeners.lan_room('lan_room','state',current);
assert(all.get('LANRoot').classes.InMatch && all.get('LANRoot').classes.Compact);
all.get('EnemyGold').events.onactivate();assert(sent.at(-1).action==='match_tool' && sent.at(-1).tool==='enemy_gold');
all.get('Toggle').events.onactivate();assert(!all.get('LANRoot').classes.Compact);
console.log('Panorama MOCK: adapted dynamic options, solo request, pending/reply, compact toggle PASS');
all.get('SelfRespawn').events.onactivate();assert(sent.at(-1).tool==='self_respawn');
all.get('BatDown').events.onactivate();assert(sent.at(-1).tool==='self_bat_down');
all.get('BatUp').events.onactivate();assert(sent.at(-1).tool==='self_bat_up');
all.get('BatReset').events.onactivate();assert(sent.at(-1).tool==='self_bat_reset');
// Quick abilities live in a collapsed submenu built from QUICK_ABILITIES.
assert(!all.get('QuickAbilityMenu').classes.Open && all.get('QuickAbilityToggleText').text.includes('▸'));
all.get('QuickAbilityToggle').events.onactivate();
assert(all.get('QuickAbilityMenu').classes.Open && all.get('QuickAbilityToggleText').text.includes('▾'));
const quick=all.get('QuickAbilityMenu').children;
assert(quick.length===36 && quick.every(b=>b.id.startsWith('Quick_') && b.children[0].text && b.classes.Owned===false));
for(const b of quick){b.events.onactivate();assert(sent.at(-1).tool==='self_ability_'+b.id.slice(6));}
// Owned quick abilities are marked and a click removes them instead of adding.
sandbox.Players={GetPlayerHeroEntityIndex:()=>7};
sandbox.Entities={GetAbilityByName:(hero,name)=>hero===7&&name==='tinker_eureka'?42:-1};
handlers.lan_reply({ok:1,message:'ok'});
assert(all.get('Quick_tinker_eureka').classes.Owned && all.get('Quick_tinker_eureka_Label').text==='✓ 尤里卡！');
assert(!all.get('Quick_centaur_horsepower').classes.Owned && all.get('Quick_centaur_horsepower_Label').text==='开足马力');
all.get('Quick_tinker_eureka').events.onactivate();
assert(sent.at(-1).tool==='self_remove_ability' && sent.at(-1).ability_name==='tinker_eureka');
all.get('Quick_centaur_horsepower').events.onactivate();assert(sent.at(-1).tool==='self_ability_centaur_horsepower');
delete sandbox.Players;delete sandbox.Entities;
all.get('QuickAbilityToggle').events.onactivate();assert(!all.get('QuickAbilityMenu').classes.Open);

assert(!all.has('Difficulty') && !all.has('bot_protection') && !all.has('radiant_lvl_start') && !all.has('dire_lvl_start'));
assert(sent.find(x=>x.action==='solo_start').options.dire_difficulty===4);

assert(!all.has('AllowPause'));

assert(!all.has('SelectionSeconds') && !all.has('buyback_cooldown'));
assert(all.get('respawn_time_percentage').selected==='30');
assert(all.get('max_level').selected==='50');
const rows=all.get('GameOptionSubpanelContainerInner').children.map(p=>p.id);
for(const setting of ['difficulty','player_number']){
 assert(rows.indexOf('dire_'+setting+'_Container')===rows.indexOf('radiant_'+setting+'_Container')+1);
}

all.get('AbilityName').text='  axe_berserkers_call  ';all.get('AddAbilityName').events.onactivate();
assert(sent.at(-1).tool==='self_add_ability' && sent.at(-1).ability_name==='axe_berserkers_call');
let beforeInvalid=sent.length;all.get('AbilityName').text='bad;quit';all.get('AbilityName').events.oninputsubmit();assert(sent.length===beforeInvalid);

assert(!all.has('Quick_faceless_void_distortion_field') && !all.has('Quick_beastmaster_inner_beast'));
assert(!/id="Add_/.test(xml));
for(const id of ['PregameSeconds','radiant_gold_start','dire_gold_start','radiant_gold_multiplier','dire_gold_multiplier','radiant_xp_multiplier','dire_xp_multiplier']){
 assert(!all.has(id));assert(!(id in sent.find(x=>x.action==='solo_start').options));
}
assert.deepStrictEqual(quick.slice(0,3).map(b=>b.id),['Quick_ancient_apparition_bone_chill','Quick_bane_ichor_of_nyctasha','Quick_bloodseeker_sanguivore']);

// Remove typed ability.
all.get('AbilityName').text=' axe_berserkers_call ';all.get('RemoveAbilityName').events.onactivate();
assert(sent.at(-1).tool==='self_remove_ability' && sent.at(-1).ability_name==='axe_berserkers_call');
beforeInvalid=sent.length;all.get('AbilityName').text='Bad Name';all.get('RemoveAbilityName').events.onactivate();assert(sent.length===beforeInvalid);

// Restart needs two clicks; the first only arms the button.
beforeInvalid=sent.length;all.get('RestartMatch').events.onactivate();
assert(sent.length===beforeInvalid && all.get('RestartMatch').classes.Confirm);
all.get('RestartMatch').events.onactivate();
assert(sent.at(-1).action==='restart_match' && !all.get('RestartMatch').classes.Confirm);
handlers.lan_reply({ok:1,message:'restart_requested'});assert(all.get('ToolMessage').text.includes('重启'));

// Every action carries the baked client build; an unsubstituted placeholder never warns.
assert(sent.every(x=>x.client_build==='__LAN_SOURCE_SHA256__'));
current.source_sha256='a'.repeat(64);listeners.lan_room('lan_room','state',current);
assert(!all.get('BuildWarning').classes.Visible);
current.restarting=1;listeners.lan_room('lan_room','state',current);
assert(all.get('BuildWarning').classes.Visible && !all.get('RestartMatch').enabled);

// A staged build that differs from the server shows the stale-client banner.
{
 const staged=source.replace('__LAN_SOURCE_SHA256__','b'.repeat(64));
 all.clear();sent.length=0;
 for(const m of xml.matchAll(/\bid="([^"]+)"/g))panel(m[1]);
 vm.runInNewContext(staged,sandbox,{filename:'lan_setup.js'});
 current={phase:'playing',revision:1,host:0,players:[{pid:0,hello:1}],bot_available:1,options:{},source_sha256:'a'.repeat(64)};
 listeners.lan_room('lan_room','state',current);
 assert(all.get('BuildWarning').classes.Visible && all.get('BuildWarning').text.includes('重新安装'));
 current.source_sha256='b'.repeat(64);listeners.lan_room('lan_room','state',current);
 assert(!all.get('BuildWarning').classes.Visible);
}
console.log('Panorama MOCK: remove ability, two-step restart, client build banner PASS');
