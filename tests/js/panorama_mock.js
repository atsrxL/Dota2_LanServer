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
all.get('radiant_gold_multiplier').SetSelected('1.25');
all.get('radiant_gold_multiplier').events.oninputsubmit();
all.get('Start').events.onactivate();
assert(sent.at(-1).action==='solo_start' && sent.at(-1).options.radiant_gold_multiplier===1.25);
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
for(const id of all.keys())if(id.startsWith('Add_')){all.get(id).events.onactivate();assert(sent.at(-1).tool==='self_ability_'+id.slice(4));}

assert(!all.has('Difficulty') && !all.has('bot_protection') && !all.has('radiant_lvl_start') && !all.has('dire_lvl_start'));
assert(sent.find(x=>x.action==='solo_start').options.dire_difficulty===4);

assert(!all.has('AllowPause'));

assert(!all.has('SelectionSeconds') && !all.has('buyback_cooldown'));
assert(all.get('respawn_time_percentage').selected==='30');
assert(all.get('max_level').selected==='50');
const rows=all.get('GameOptionSubpanelContainerInner').children.map(p=>p.id);
for(const setting of ['difficulty','gold_multiplier','xp_multiplier','gold_start','player_number']){
 assert(rows.indexOf('dire_'+setting+'_Container')===rows.indexOf('radiant_'+setting+'_Container')+1);
}

all.get('AbilityName').text='  axe_berserkers_call  ';all.get('AddAbilityName').events.onactivate();
assert(sent.at(-1).tool==='self_add_ability' && sent.at(-1).ability_name==='axe_berserkers_call');
let beforeInvalid=sent.length;all.get('AbilityName').text='bad;quit';all.get('AbilityName').events.oninputsubmit();assert(sent.length===beforeInvalid);
