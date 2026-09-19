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
			dropdownlabel.text = tDropDown.labels ? tDropDown.labels[j] : tDropDown.options[j].toString();
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
{id:'radiant_difficulty',label:'天辉 AI 难度',options:[0,1,2,3,4],labels:['消极','简单','中等','困难','不公平'],default_value:1},
{id:'dire_difficulty',label:'夜魇 AI 难度',options:[0,1,2,3,4],labels:['消极','简单','中等','困难','不公平'],default_value:4},
{"id": "radiant_gold_multiplier", "label": "天辉金钱倍率", "options": [1, 1.15, 1.25, 1.35, 1.5, 1.75, 2, 2.5, 3, 4, 5], "default_value": 1},
{"id": "dire_gold_multiplier", "label": "夜魇金钱倍率", "options": [1, 1.15, 1.25, 1.35, 1.5, 1.75, 2, 2.5, 3, 4, 5], "default_value": 1},
{"id": "radiant_xp_multiplier", "label": "天辉经验倍率", "options": [1, 1.15, 1.25, 1.35, 1.5, 1.75, 2, 2.5, 3, 4, 5], "default_value": 1},
{"id": "dire_xp_multiplier", "label": "夜魇经验倍率", "options": [1, 1.15, 1.25, 1.35, 1.5, 1.75, 2, 2.5, 3, 4, 5], "default_value": 1},
{"id": "radiant_gold_start", "label": "天辉初始金钱", "options": [600, 1000, 1700, 3200, 6000, 10000, 100000], "default_value": 600},
{"id": "dire_gold_start", "label": "夜魇初始金钱", "options": [600, 1000, 1700, 3200, 6000, 10000, 100000], "default_value": 600},
{"id": "radiant_player_number", "label": "天辉总人数", "options": [4, 5, 6, 7, 8, 9, 10, 11, 12], "default_value": 5},
{"id": "dire_player_number", "label": "夜魇总人数", "options": [4, 5, 6, 7, 8, 9, 10, 11, 12], "default_value": 5},
{"id": "respawn_time_percentage", "label": "复活时间比例", "options": [0, 10, 25, 30, 50, 75, 100], "default_value": 30},
{"id": "tower_power", "label": "防御塔威力等级", "options": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "default_value": 1},
{"id": "tower_endure", "label": "建筑耐久等级", "options": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "default_value": 1},
{"id": "max_level", "label": "最高等级", "options": [30, 50, 100, 200, 400, 800, 1600], "default_value": 50},
{id:'PregameSeconds',label:'出兵前时间（秒）',options:[10,15,30,45,60],default_value:30}
].forEach(function(o){AddDropDown(o,el('GameOptionSubpanelContainerInner'));});
function value(id){return Number(el(id).GetSelected().id);}

function yes(v){return v===true || v===1 || v==='1';}
function msg(s){el('Message').text=String(s);el('ToolMessage').text=String(s);}
function send(action,extra){var d=extra||{};d.action=action;d.revision=state?Number(state.revision):0;d.client_revision='lanlab-130.1';GameEvents.SendCustomGameEventToServer('lan_action',d);}
function render(s){
 if(!s)return;state=s;
 if(lastPhase!==s.phase){lastPhase=s.phase;collapsed=['hero_selection','pregame','playing','postgame'].indexOf(s.phase)>=0;}
 el('LANRoot').SetHasClass('Compact',collapsed);
 var inMatch=['pregame','playing','postgame'].indexOf(s.phase)>=0;
 el('LANRoot').SetHasClass('InMatch',inMatch);
 el('MenuTitle').text=inMatch?'对局操作':'游戏选项';
 el('ToggleText').text='收起 / 展开';
 var phases={setup:'调整参数后开始',waiting_engine:'等待服务器',starting:'正在开始',hero_selection:'英雄选择',pregame:'准备出兵',playing:'比赛中',postgame:'比赛结束',error:'运行异常'};
 el('Phase').text=phases[s.phase]||s.phase;
 if(!initialized && s.options){initialized=true;el('radiant_difficulty').SetSelected(String(s.options.radiant_difficulty));el('dire_difficulty').SetSelected(String(s.options.dire_difficulty));el('PregameSeconds').SetSelected(String(s.options.pregame_seconds));}
 el('BotInfo').text=yes(s.bot_available)?'天地星 AI 已加载 · 按双方人数自动补位':'天地星 AI 加载异常，请检查服务器。';
 el('Start').enabled=s.phase==='setup' && Number(s.host)===Game.GetLocalPlayerID() && yes(s.bot_available) && !pending;
 if(s.error)msg(s.error);
}
el('Start').SetPanelEvent('onactivate',function(){
 try{pending=true;render(state);msg('正在应用设置并开始…');
 var options={radiant_difficulty:value('radiant_difficulty'),dire_difficulty:value('dire_difficulty'),pregame_seconds:value('PregameSeconds')};
options.radiant_gold_multiplier=value('radiant_gold_multiplier');
options.radiant_xp_multiplier=value('radiant_xp_multiplier');
options.radiant_gold_start=value('radiant_gold_start');
options.radiant_player_number=value('radiant_player_number');
options.dire_gold_multiplier=value('dire_gold_multiplier');
options.dire_xp_multiplier=value('dire_xp_multiplier');
options.dire_gold_start=value('dire_gold_start');
options.dire_player_number=value('dire_player_number');
options.respawn_time_percentage=value('respawn_time_percentage');
options.tower_power=value('tower_power');
options.tower_endure=value('tower_endure');
options.max_level=value('max_level');



send('solo_start',{options:options});
 $.Schedule(5,function(){if(pending){pending=false;msg('尚未收到确认，请检查连接后重试。');render(state);}});
 }catch(e){pending=false;msg('操作失败：'+String(e));render(state);}
});
[['SelfRespawn','self_respawn'],['SelfRefresh','self_refresh'],['SelfGold','self_gold'],['AllyGold','ally_gold'],['EnemyGold','enemy_gold'],['AllyLevel','ally_level'],['EnemyLevel','enemy_level'],['BatDown','self_bat_down'],['BatUp','self_bat_up'],['BatReset','self_bat_reset'],['Add_death_prophet_witchcraft','self_ability_death_prophet_witchcraft'],['Add_winter_wyvern_eldwurms_edda','self_ability_winter_wyvern_eldwurms_edda'],['Add_silencer_brain_drain','self_ability_silencer_brain_drain'],['Add_tinker_eureka','self_ability_tinker_eureka'],['Add_beastmaster_inner_beast','self_ability_beastmaster_inner_beast'],['Add_razor_unstable_current','self_ability_razor_unstable_current'],['Add_bloodseeker_thirst','self_ability_bloodseeker_thirst'],['Add_faceless_void_distortion_field','self_ability_faceless_void_distortion_field']].forEach(function(pair){el(pair[0]).SetPanelEvent('onactivate',function(){msg('正在执行…');send('match_tool',{tool:pair[1]});});});
function addTypedAbility(){
 var name=String(el('AbilityName').text||'').trim();
 if(!/^[a-z][a-z0-9_]{0,95}$/.test(name)){msg('只填技能内部名称，例如 bloodseeker_thirst');return;}
 msg('正在添加技能…');send('match_tool',{tool:'self_add_ability',ability_name:name});
}
el('AddAbilityName').SetPanelEvent('onactivate',addTypedAbility);
el('AbilityName').SetPanelEvent('oninputsubmit',addTypedAbility);
el('Toggle').SetPanelEvent('onactivate',function(){collapsed=!collapsed;render(state);});
var errors={solo_requires_one_player:'单人模式只允许一名真人连接。',bot_snapshot_missing:'尚未加载 AI 脚本。',invalid_options:'参数无效，请检查数字范围。',invalid_number:'选人30–120秒，赛前10–60秒，金币25–1000%。',bot_populate_requires_explicit_cheats:'服务器需要开启 sv_cheats 后重开。',stale_revision:'状态已更新，请重试。'};
GameEvents.Subscribe('lan_reply',function(r){pending=false;msg(yes(r.ok)?(r.message&&r.message!=='ok'?r.message:'设置已确认。'):(errors[r.message]||String(r.message)));render(state);});
CustomNetTables.SubscribeNetTableListener('lan_room',function(_,key,v){if(key==='state')render(v);});
function poll(){if(!context.IsValid())return;var s=CustomNetTables.GetTableValue('lan_room','state');render(s);var ps=s?Object.keys(s.players||{}).map(function(k){return s.players[k];}):[];if(!ps.some(function(p){return Number(p.pid)===Game.GetLocalPlayerID()&&yes(p.hello);}))send('hello');$.Schedule(2,poll);}
poll();
})();
