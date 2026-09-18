(function () {
// Adapted from installed DOTA2 AI Fun 12v12 (Workshop 956357541),
// game_mode.js AddDropDown: dynamic AddOption + oninputsubmit.
'use strict';
var GameOptions={},tGameOptionsControlDropDowns={};
function AddDropDown(tDropDown, hParent) {
	$.CreatePanel('Panel', hParent, tDropDown.id+"_Container",{id:tDropDown.id+"_Container", class:"GameOptionsSubPanel_DropDown"})
	$.CreatePanel('Label', $("#"+tDropDown.id+'_Container'), '',{text:tDropDown.label})
	
	$.CreatePanel('DropDown', $("#"+tDropDown.id+'_Container'), tDropDown.id,{id:tDropDown.id, class:"GameOptionsDropdown"})
	for (var j in tDropDown.options) {
		var dropdownlabel = $.CreatePanel('Label', $("#"+tDropDown.id), tDropDown.options[j].toString())
		if (tDropDown.percentage)
			dropdownlabel.text = tDropDown.options[j].toString()+"%";
		else
			dropdownlabel.text = tDropDown.options[j].toString();
		$("#"+tDropDown.id).AddOption(dropdownlabel)
	}
	$("#"+tDropDown.id).SetSelected(tDropDown.default_value.toString())
	GameOptions[tDropDown.id] = tDropDown.default_value.toString()
 tGameOptionsControlDropDowns[tDropDown.id] = $("#"+tDropDown.id);
 $("#"+tDropDown.id).SetPanelEvent('oninputsubmit',function(){GameOptions[tDropDown.id]=$("#"+tDropDown.id).GetSelected().id;});
}

var context=$.GetContextPanel(), state=null, lastPhase=null, initialized=false, collapsed=false, pending=false;
function el(id){return context.FindChildTraverse(id);}
[
{id:'Difficulty',label:'AI 难度（0简单 / 3不公平）',options:[0,1,2,3],default_value:2},
{id:'GoldPercent',label:'金币收入倍率',options:[25,50,75,100,150,200,300,500,1000],default_value:100,percentage:true},
{id:'SelectionSeconds',label:'选人时间（秒）',options:[30,45,60,90,120],default_value:60},
{id:'PregameSeconds',label:'出兵前时间（秒）',options:[10,15,30,45,60],default_value:30}
].forEach(function(o){AddDropDown(o,el('GameOptionSubpanelContainerInner'));});
function value(id){return Number(el(id).GetSelected().id);}

function yes(v){return v===true || v===1 || v==='1';}
function msg(s){el('Message').text=String(s);}
function send(action,extra){var d=extra||{};d.action=action;d.revision=state?Number(state.revision):0;d.client_revision='lanlab-130.1';GameEvents.SendCustomGameEventToServer('lan_action',d);}
function render(s){
 if(!s)return;state=s;
 if(lastPhase!==s.phase){lastPhase=s.phase;collapsed=['hero_selection','pregame','playing','postgame'].indexOf(s.phase)>=0;}
 el('LANRoot').SetHasClass('Compact',collapsed);
 var phases={setup:'调整参数后开始',waiting_engine:'等待服务器',starting:'正在开始',hero_selection:'英雄选择',pregame:'准备出兵',playing:'比赛中',postgame:'比赛结束',error:'运行异常'};
 el('Phase').text=phases[s.phase]||s.phase;
 if(!initialized && s.options){initialized=true;el('Difficulty').SetSelected(String(s.options.difficulty));el('GoldPercent').SetSelected(String(s.options.gold_percent));el('SelectionSeconds').SetSelected(String(s.options.selection_seconds));el('PregameSeconds').SetSelected(String(s.options.pregame_seconds));el('AllowPause').checked=yes(s.options.allow_pause);}
 el('BotInfo').text=yes(s.bot_available)?'天地星 AI 已加载 · 开始时自动补齐 9 名 AI':'AI 未加载，请在管理面板启用机器人脚本。';
 el('Start').enabled=s.phase==='setup' && Number(s.host)===Game.GetLocalPlayerID() && yes(s.bot_available) && !pending;
 if(s.error)msg(s.error);
}
el('Start').SetPanelEvent('onactivate',function(){
 try{var d=el('Difficulty').GetSelected();pending=true;render(state);msg('正在应用设置并开始…');
 send('solo_start',{options:{difficulty:value('Difficulty'),gold_percent:value('GoldPercent'),selection_seconds:value('SelectionSeconds'),pregame_seconds:value('PregameSeconds'),allow_pause:el('AllowPause').checked?1:0}});
 $.Schedule(5,function(){if(pending){pending=false;msg('尚未收到确认，请检查连接后重试。');render(state);}});
 }catch(e){pending=false;msg('操作失败：'+String(e));render(state);}
});
el('Toggle').SetPanelEvent('onactivate',function(){collapsed=!collapsed;render(state);});
var errors={solo_requires_one_player:'单人模式只允许一名真人连接。',bot_snapshot_missing:'尚未加载 AI 脚本。',invalid_options:'参数无效，请检查数字范围。',invalid_number:'选人30–120秒，赛前10–60秒，金币25–1000%。',bot_populate_requires_explicit_cheats:'服务器需要开启 sv_cheats 后重开。',stale_revision:'状态已更新，请重试。'};
GameEvents.Subscribe('lan_reply',function(r){pending=false;msg(yes(r.ok)?'设置已确认。':(errors[r.message]||String(r.message)));render(state);});
CustomNetTables.SubscribeNetTableListener('lan_room',function(_,key,v){if(key==='state')render(v);});
function poll(){if(!context.IsValid())return;var s=CustomNetTables.GetTableValue('lan_room','state');render(s);var ps=s?Object.keys(s.players||{}).map(function(k){return s.players[k];}):[];if(!ps.some(function(p){return Number(p.pid)===Game.GetLocalPlayerID()&&yes(p.hello);}))send('hello');$.Schedule(2,poll);}
poll();
})();
