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

// Replaced with the server source identity when the release pipeline stages this file
// for compilation (tools/addon_assets.py). Left as-is, the build is unknown.
var CLIENT_BUILD='__LAN_SOURCE_SHA256__';
var context=$.GetContextPanel(), state=null, lastPhase=null, initialized=false, collapsed=false, pending=false;
function el(id){return context.FindChildTraverse(id);}
[
{id:'radiant_difficulty',label:'天辉 AI 难度',options:[0,1,2,3,4],labels:['消极','简单','中等','困难','不公平'],default_value:1},
{id:'dire_difficulty',label:'夜魇 AI 难度',options:[0,1,2,3,4],labels:['消极','简单','中等','困难','不公平'],default_value:4},
{"id": "radiant_player_number", "label": "天辉总人数", "options": [4, 5, 6, 7, 8, 9, 10, 11, 12], "default_value": 5},
{"id": "dire_player_number", "label": "夜魇总人数", "options": [4, 5, 6, 7, 8, 9, 10, 11, 12], "default_value": 5},
{"id": "respawn_time_percentage", "label": "复活时间比例", "options": [0, 10, 25, 30, 50, 75, 100], "default_value": 30},
{"id": "tower_power", "label": "防御塔威力等级", "options": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "default_value": 1},
{"id": "tower_endure", "label": "建筑耐久等级", "options": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "default_value": 1},
{"id": "max_level", "label": "最高等级", "options": [30, 50, 100, 200, 400, 800, 1600], "default_value": 50}
].forEach(function(o){AddDropDown(o,el('GameOptionSubpanelContainerInner'));});
function value(id){return Number(el(id).GetSelected().id);}

function yes(v){return v===true || v===1 || v==='1';}
function msg(s){el('Message').text=String(s);el('ToolMessage').text=String(s);}
function send(action,extra){var d=extra||{};d.action=action;d.revision=state?Number(state.revision):0;d.client_revision='lanlab-130.1';d.client_build=CLIENT_BUILD;GameEvents.SendCustomGameEventToServer('lan_action',d);}
function renderBuildWarning(s){
 var known=CLIENT_BUILD.indexOf('__')!==0;
 var server=String(s.source_sha256||'');
 var stale=known && /^[0-9a-f]{64}$/.test(server) && server!==CLIENT_BUILD;
 var text='';
 if(yes(s.restarting))text='对局正在重启：服务器将关闭并重开，约 30 秒后请重新连接。';
 else if(stale)text='客户端资源版本与服务器不一致：请退出 Dota 2，从控制面板重新安装客户端资源。';
 el('BuildWarning').text=text;
 el('BuildWarning').SetHasClass('Visible',text!=='');
}
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
 if(!initialized && s.options){initialized=true;el('radiant_difficulty').SetSelected(String(s.options.radiant_difficulty));el('dire_difficulty').SetSelected(String(s.options.dire_difficulty));}
 el('BotInfo').text=yes(s.bot_available)?'天地星 AI 已加载 · 按双方人数自动补位':'天地星 AI 加载异常，请检查服务器。';
 el('Start').enabled=s.phase==='setup' && Number(s.host)===Game.GetLocalPlayerID() && yes(s.bot_available) && !pending;
 renderBuildWarning(s);
 el('RestartMatch').enabled=!yes(s.restarting) && s.phase!=='waiting_engine';
 if(s.error)msg(s.error);
}
el('Start').SetPanelEvent('onactivate',function(){
 try{pending=true;render(state);msg('正在应用设置并开始…');
 var options={radiant_difficulty:value('radiant_difficulty'),dire_difficulty:value('dire_difficulty')};
options.radiant_player_number=value('radiant_player_number');
options.dire_player_number=value('dire_player_number');
options.respawn_time_percentage=value('respawn_time_percentage');
options.tower_power=value('tower_power');
options.tower_endure=value('tower_endure');
options.max_level=value('max_level');



send('solo_start',{options:options});
 $.Schedule(5,function(){if(pending){pending=false;msg('尚未收到确认，请检查连接后重试。');render(state);}});
 }catch(e){pending=false;msg('操作失败：'+String(e));render(state);}
});
// Quick-add innate abilities: [internal name, ability, hero]. Keep in sync with cheats.lua M.abilities.
var QUICK_ABILITIES=[
 ['ancient_apparition_bone_chill','刺骨严寒','远古冰魄'],
 ['bane_ichor_of_nyctasha','妮塔莎脓血','祸乱之源'],
 ['bloodseeker_sanguivore','食血动物','血魔'],
 ['brewmaster_liquid_courage','壮胆酒','酒仙'],
 ['centaur_horsepower','开足马力','半人马战行者'],
 ['chaos_knight_fundamental_forging','基本法则锻造','混沌骑士'],
 ['rattletrap_armor_power','装甲力量','发条技师'],
 ['dark_seer_aggrandize','才思敏捷','黑暗贤者'],
 ['death_prophet_witchcraft','巫术精研','死亡先知'],
 ['drow_ranger_trueshot','精准光环','卓尔游侠'],
 ['enigma_event_horizon','事件视界','谜团'],
 ['grimstroke_ink_trail','墨痕','天涯墨客'],
 ['huskar_blood_magic','血魔法','哈斯卡'],
 ['jakiro_double_trouble','天生一对','杰奇洛'],
 ['largo_encore','安可','朗戈'],
 ['leshrac_defilement','大肆污染','拉席克'],
 ['medusa_mana_shield','魔法盾','美杜莎'],
 ['morphling_ebb_and_flow','潮涨潮落','变体精灵'],
 ['necrolyte_sadist','施虐之心','瘟疫法师'],
 ['omniknight_degen_aura','退化光环','全能骑士'],
 ['obsidian_destroyer_equilibrium','精华变迁','殁境神蚀者'],
 ['phoenix_dying_light','消逝之光','凤凰'],
 ['primal_beast_colossal','庞','獸'],
 ['pudge_innate_graft_flesh','腐肉堆积','帕吉'],
 ['razor_unstable_current','不稳定电流','雷泽'],
 ['rubick_curiosity','奇心','拉比克'],
 ['shadow_demon_menace','威胁','暗影恶魔'],
 ['silencer_brain_drain','默默受苦','沉默术士'],
 ['slark_essence_shift','能量转移','斯拉克'],
 ['tinker_eureka','尤里卡！','修补匠'],
 ['tiny_insurmountable','不可逾越','小小'],
 ['vengefulspirit_retribution','恶有恶报','复仇之魂'],
 ['void_spirit_intrinsic_edge','内在优势','虚无之灵'],
 ['windrunner_tailwind','一路顺风','风行者'],
 ['winter_wyvern_eldwurms_edda','古龙诗集','寒冬飞龙'],
 ['skeleton_king_vampiric_spirit','吸血灵魂','冥魂大帝']
];
function buildQuickAbilityMenu(){
 var menu=el('QuickAbilityMenu');
 QUICK_ABILITIES.forEach(function(a){
  var button=$.CreatePanel('Button',menu,'Quick_'+a[0],{class:'QuickAbility'});
  var label=$.CreatePanel('Label',button,'',{text:a[1]});label.hittest=false;
  button.SetPanelEvent('onactivate',function(){msg('正在添加 '+a[1]+'…');send('match_tool',{tool:'self_ability_'+a[0]});});
  button.SetPanelEvent('onmouseover',function(){$.DispatchEvent('DOTAShowTextTooltip',button,a[2]+' · '+a[0]);});
  button.SetPanelEvent('onmouseout',function(){$.DispatchEvent('DOTAHideTextTooltip',button);});
 });
}
var quickAbilitiesOpen=false;
function setQuickAbilitiesOpen(open){
 quickAbilitiesOpen=open;
 el('QuickAbilityMenu').SetHasClass('Open',open);
 el('QuickAbilityToggleText').text='快捷技能（'+QUICK_ABILITIES.length+'）'+(open?'▾':'▸');
}
buildQuickAbilityMenu();
setQuickAbilitiesOpen(false);
el('QuickAbilityToggle').SetPanelEvent('onactivate',function(){setQuickAbilitiesOpen(!quickAbilitiesOpen);});
[['SelfRespawn','self_respawn'],['SelfRefresh','self_refresh'],['SelfGold','self_gold'],['AllyGold','ally_gold'],['EnemyGold','enemy_gold'],['AllyLevel','ally_level'],['EnemyLevel','enemy_level'],['BatDown','self_bat_down'],['BatUp','self_bat_up'],['BatReset','self_bat_reset']].forEach(function(pair){el(pair[0]).SetPanelEvent('onactivate',function(){msg('正在执行…');send('match_tool',{tool:pair[1]});});});
function addTypedAbility(){
 var name=String(el('AbilityName').text||'').trim();
 if(!/^[a-z][a-z0-9_]{0,95}$/.test(name)){msg('只填技能内部名称，例如 bloodseeker_thirst');return;}
 msg('正在添加技能…');send('match_tool',{tool:'self_add_ability',ability_name:name});
}
function removeTypedAbility(){
 var name=String(el('AbilityName').text||'').trim();
 if(!/^[a-z][a-z0-9_]{0,95}$/.test(name)){msg('只填技能内部名称，例如 bloodseeker_thirst');return;}
 msg('正在删除技能…');send('match_tool',{tool:'self_remove_ability',ability_name:name});
}
// Destroying the match needs a second click within 5 seconds.
var restartArmed=false;
function disarmRestart(){restartArmed=false;el('RestartMatch').SetHasClass('Confirm',false);el('RestartMatchText').text='restart：摧毁本局并重启一局游戏';}
el('RestartMatch').SetPanelEvent('onactivate',function(){
 if(!restartArmed){
  restartArmed=true;el('RestartMatch').SetHasClass('Confirm',true);el('RestartMatchText').text='再次点击确认：本局将被销毁';
  $.Schedule(5,function(){if(restartArmed)disarmRestart();});
  return;
 }
 disarmRestart();msg('正在请求重启…');send('restart_match');
});
el('RemoveAbilityName').SetPanelEvent('onactivate',removeTypedAbility);
el('AddAbilityName').SetPanelEvent('onactivate',addTypedAbility);
el('AbilityName').SetPanelEvent('oninputsubmit',addTypedAbility);
el('Toggle').SetPanelEvent('onactivate',function(){collapsed=!collapsed;render(state);});
var errors={solo_requires_one_player:'单人模式只允许一名真人连接。',bot_snapshot_missing:'尚未加载 AI 脚本。',invalid_options:'参数无效，请检查设置。',invalid_number:'参数超出允许范围。',bot_populate_requires_explicit_cheats:'服务器需要开启 sv_cheats 后重开。',stale_revision:'状态已更新，请重试。',only_host_can_restart:'只有房主可以重启对局。',restart_already_requested:'已在重启中，请稍候。',engine_not_ready:'服务器尚未就绪。'};
var notices={restart_requested:'已请求重启：服务器即将关闭并重开，约 30 秒后重新连接。'};
GameEvents.Subscribe('lan_reply',function(r){pending=false;msg(yes(r.ok)?(r.message&&r.message!=='ok'?(notices[r.message]||r.message):'设置已确认。'):(errors[r.message]||String(r.message)));render(state);});
CustomNetTables.SubscribeNetTableListener('lan_room',function(_,key,v){if(key==='state')render(v);});
function poll(){if(!context.IsValid())return;var s=CustomNetTables.GetTableValue('lan_room','state');render(s);var ps=s?Object.keys(s.players||{}).map(function(k){return s.players[k];}):[];if(!ps.some(function(p){return Number(p.pid)===Game.GetLocalPlayerID()&&yes(p.hello);}))send('hello');$.Schedule(2,poll);}
poll();
})();
