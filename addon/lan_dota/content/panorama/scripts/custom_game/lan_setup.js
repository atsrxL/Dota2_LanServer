/* Panorama JavaScript, not browser DOM. Compile with Valve Workshop Tools. */
(function () {
    'use strict';
    var CLIENT_REVISION = 'lanlab-130.1', state = null, lastOptions = '', lastRoster = '', collapsed = false;
    var context = $.GetContextPanel();
    function el(id) { return context.FindChildTraverse(id); }
    function truth(v) { return v === true || v === 1 || v === '1'; }
    function pid() { return Game.GetLocalPlayerID(); }
    function rows(v) { return Object.keys(v || {}).map(function(k) { return v[k]; }).filter(function(p) { return p && p.pid !== undefined; }); }
    function me() { return state && rows(state.players).filter(function(p) { return Number(p.pid) === pid(); })[0]; }
    function chosen(id, fallback) { var p = el(id).GetSelected(); return p ? p.id : fallback; }
    function msg(s) { el('Message').text = String(s); }
    var errors = {
        engine_team_assignment_failed:'引擎未接受队伍分配，请保留本提示。', invalid_team_or_role:'队伍或位置值无效。', host_only:'只有配置者可以操作。', stale_revision:'配置已经改变，请检查最新内容后重试。',
        not_in_setup:'当前不在可配置的准备阶段。', ui_handshake_required:'服务端尚未确认此界面的版本。',
        client_revision_mismatch:'客户端 UI 与服务端版本不一致；请安装同一份编译资源。',
        players_not_ready:'仍有连接中的玩家尚未完成界面握手、选边或准备。',
        role_taken:'该队伍的意向位置已被占用。', team_full:'该队伍已满。',
        bot_snapshot_missing:'服务端没有本局天地星脚本快照；停服后在面板启用探针与固定版本。',
        experimental_ack_required:'请确认实验说明并保存参数。',
        bot_populate_requires_explicit_cheats:'此 BotPopulate 路径要求明确开启服务器作弊；请在面板设置后重启，不会自动开启。',
        choose_team_and_role:'请先选择队伍和意向位置。', invalid_options:'参数无效。',
        fill_requires_bot_mode:'无机器人模式不能勾选补 AI。', bot_thinking_api_missing:'此引擎未提供机器人思考开关。'
    };
    function send(action, extra) {
        var data = extra || {}; data.action = action; data.revision = state ? Number(state.revision) : 0;
        data.client_revision = CLIENT_REVISION;
        // Do not send a player identity. The server resolves the event source.
        GameEvents.SendCustomGameEventToServer('lan_action', data);
    }
    function bind(id, fn) {
        el(id).SetPanelEvent('onactivate', function () {
            msg('正在提交操作…');
            try { fn(); } catch (e) { msg('界面操作失败：' + String(e)); }
        });
    }
    function render(table) {
        if (!table) return; state = table;
        var ps = rows(state.players), own = me(), host = Number(state.host) === pid(), setup = state.phase === 'setup';
        var phases = {waiting_engine:'等待引擎进入准备阶段',setup:'等待玩家配置与准备',starting:'开局初始化中',hero_selection:'选人阶段',pregame:'赛前阶段',playing:'比赛中',postgame:'比赛结束，请在面板重开',error:'运行异常，请保留日志并停服检查'};
        el('Phase').text = phases[state.phase] || state.phase;
        el('Owner').text = '本机：' + pid() + ' / 配置者：' + (Number(state.host) >= 0 ? 'Player ' + state.host : '等待有效玩家');
        el('LANRoot').SetHasClass('Compact', collapsed || (state.phase !== 'setup' && state.phase !== 'waiting_engine' && state.phase !== 'starting' && state.phase !== 'error'));
        ['RadiantRows','DireRows'].forEach(function(id,i) {
            var root = el(id), team = i+2; root.RemoveAndDeleteChildren();
            for (var role=1;role<=5;role++) {
                var p = ps.filter(function(x) { return Number(x.team)===team && Number(x.role)===role; })[0];
                var line = $.CreatePanel('Label',root,''); line.AddClass('PlayerRow');
                line.text = role+'号位  '+(p ? p.name+'  '+(!truth(p.connected)?'断线':truth(p.ready)?'已准备':'未准备') : '空位'+(truth(state.options.fill_bots)?' → AI（开局时）':''));
            }
        });
        el('Start').enabled = host && setup; el('SaveOptions').enabled=host && setup;
        el('Ready').enabled=setup && !!own && truth(own.hello); el('Assign').enabled=setup && !!own && truth(own.hello);
        el('Transfer').enabled=host && setup;
        var opts = JSON.stringify(state.options);
        if (opts !== lastOptions) {
            lastOptions=opts; var o=state.options;
            el('BotMode').SetSelected(o.bot_mode); el('Difficulty').SetSelected('diff'+o.difficulty);
            el('FillBots').checked=truth(o.fill_bots); el('AckUnverified').checked=truth(o.ack_unverified);
            el('AllowPause').checked=truth(o.allow_pause);
            el('GoldPercent').text=String(o.gold_percent || 100);
            el('SelectionSeconds').text=String(o.selection_seconds); el('PregameSeconds').text=String(o.pregame_seconds);
        }
        el('BotInfo').text = (truth(state.bot_available)?'本局有天地星快照：'+String(state.bot_version).slice(0,16):'本局没有天地星快照')+'；作弊开关：'+(truth(state.cheats)?'已明确开启':'关闭');
        var roster=ps.filter(function(p){return truth(p.connected) && truth(p.hello);});
        var signature=JSON.stringify(roster.map(function(p){return [p.pid,p.name];}));
        if(signature!==lastRoster){
            lastRoster=signature;var select=el('TransferTarget');
            var old=chosen('TransferTarget','');select.RemoveAllOptions();
            roster.forEach(function(p){
                var option=$.CreatePanel('Label',select,'player'+p.pid);option.text=p.name;select.AddOption(option);
            });
            if(old)select.SetSelected(old);
        }
        if (state.error) msg(state.error);
    }
    bind('Assign',function(){send('team',{team:Number(chosen('MyTeam','team2').slice(4)),role:Number(chosen('MyRole','role1').slice(4))});});
    bind('Ready',function(){send('ready',{ready:me() && truth(me().ready)?0:1});});
    bind('Start',function(){send('start');});
    bind('SaveOptions',function(){send('options',{options:{bot_mode:chosen('BotMode','none'),
        fill_bots:el('FillBots').checked?1:0,ack_unverified:el('AckUnverified').checked?1:0,
        allow_pause:el('AllowPause').checked?1:0,difficulty:Number(chosen('Difficulty','diff2').slice(4)),
        gold_percent:Number(el('GoldPercent').text),selection_seconds:Number(el('SelectionSeconds').text),pregame_seconds:Number(el('PregameSeconds').text)}});});
    bind('Transfer',function(){send('transfer',{target:Number(chosen('TransferTarget','player-1').slice(6))});});
    bind('Toggle',function(){collapsed=!collapsed;if(state)render(state);});
    el('MyTeam').SetSelected('team2'); el('MyRole').SetSelected('role1');
    GameEvents.Subscribe('lan_reply',function(reply){msg(truth(reply.ok)?'服务端已确认操作。':(errors[reply.message]||String(reply.message)));});
    CustomNetTables.SubscribeNetTableListener('lan_room',function(_,key,value){if(key==='state')render(value);});
    function poll() {
        if (!context.IsValid()) return;
        var data=CustomNetTables.GetTableValue('lan_room','state'); if(data)render(data);
        if (!me() || !truth(me().hello)) send('hello');
        $.Schedule(2,poll);
    }
    poll();
})();
