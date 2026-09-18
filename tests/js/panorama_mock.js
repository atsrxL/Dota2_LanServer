/* Test fixture only: NOT a Panorama implementation or an in-game screenshot. */
'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const base=process.argv[2];
const xml=fs.readFileSync(base+'/layout/custom_game/lan_setup.xml','utf8');
const source=fs.readFileSync(base+'/scripts/custom_game/lan_setup.js','utf8');
const all=new Map(),sent=[],handlers={},listeners={},schedules=[];
function panel(id='') {
 const p={id,text:'',checked:false,enabled:true,selected:null,children:[],events:{},classes:{},
 SetPanelEvent(e,fn){this.events[e]=fn;},SetSelected(x){this.selected=x;},GetSelected(){return this.selected?{id:this.selected}:null;},
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
vm.runInNewContext(source,sandbox,{filename:'lan_setup.js'});
assert(sent[0].action==='hello');assert(all.get('MyTeam').selected==='team2');
current={phase:'setup',revision:9,host:0,players:[{pid:0,name:'TEST PLAYER',connected:1,hello:1,ready:0,team:2,role:1}],
 options:{bot_mode:'none',fill_bots:0,ack_unverified:0,difficulty:2,selection_seconds:60,pregame_seconds:30,allow_pause:1},
 bot_available:0,cheats:0};
listeners.lan_room('lan_room','state',current);
assert(all.get('Start').enabled&&all.get('Ready').enabled);
assert(all.get('RadiantRows').children.length===5);
all.get('Assign').events.onactivate();assert(sent.at(-1).action==='team'&&sent.at(-1).team===2);
all.get('Ready').events.onactivate();assert(sent.at(-1).ready===1);
all.get('SaveOptions').events.onactivate();assert(sent.at(-1).options.selection_seconds===60);
all.get('Start').events.onactivate();assert(sent.at(-1).action==='start'&&sent.at(-1).revision===9);
handlers.lan_reply({ok:0,message:'host_only'});assert(all.get('Message').text.includes('配置者'));
current.host=1;listeners.lan_room('lan_room','state',current);assert(!all.get('Start').enabled);
current.phase='playing';listeners.lan_room('lan_room','state',current);assert(all.get('LANRoot').classes.Compact&&!all.get('Ready').enabled);
current.phase='error';current.error='ENGINE TEST FAILURE';listeners.lan_room('lan_room','state',current);assert(all.get('Message').text==='ENGINE TEST FAILURE');
console.log('Panorama MOCK: XML ids, hello, rendering, 5 slots/team, team/options/ready/start payloads, authority UI, errors PASS');
