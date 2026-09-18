/* Web control surface: engine telemetry, not a browser imitation of a lobby. */
'use strict';
window.AddonPanel = (() => {
  let data = null, editing = false, polling = false;
  const phaseNames = {waiting_engine:'等待引擎',setup:'等待配置 / 准备',starting:'开始初始化',hero_selection:'选人',pregame:'赛前',playing:'比赛中',postgame:'比赛结束',error:'运行异常'};
  function text(id,value){$(id).textContent=value;}
  function render(d){
    data=d;
    if(!editing){$('addonEnabled').checked=d.config.enabled;$('addonLaunch').value=d.config.launch_method;}
    text('addonAssetState',d.source.ready?'已核对编译资源文件（引擎待验收）':'缺少 / 无效编译资源');
    text('addonAssetReason',d.source.reason);
    text('addonSourceHash',d.source.source_sha256||'未读取源码');
    text('addonDeployState',d.deployment_error|| (d.deployment?'已部署 '+d.deployment.source_sha256.slice(0,16):'尚未部署'));
    text('addonRecovery',d.recovery_required?'存在部署中断记录；先停服，按接手文件核对恢复。':'');
    $('addonRecovery').hidden=!d.recovery_required;
    const r=d.runtime, s=r?.state;
    text('addonPhase',r?.fresh ? (phaseNames[s?.phase]||s?.phase||'未知') : r?.running?'未收到新鲜的附加模式心跳':'未运行附加模式');
    text('addonSession',r?'会话 '+r.session+' / 心跳 '+(r.heartbeat_age_seconds===null?'未收到':r.heartbeat_age_seconds+' 秒前'):'等待启动');
    const ps=$('addonPlayers');ps.replaceChildren();
    if(r?.fresh && Array.isArray(s?.players)){
      for(const p of s.players){const row=document.createElement('p');row.textContent=`${p.pid} · ${p.name} · ${p.team===2?'天辉':p.team===3?'夜魇':'未选边'} / 意向${p.role||'—'}号位 · ${p.connected?(p.ready?'已准备':'未准备'):'断线'}`;ps.append(row);}
      if(!s.players.length)ps.textContent='尚无玩家进入准备界面。';
    } else ps.textContent='没有新鲜玩家状态；不会沿用旧会话显示“等待开局”。';
    text('addonAudit',d.audit ? `固定版本 ${d.audit.content_sha256}\nLua 文件 ${d.audit.lua_files} / 入口 ${d.audit.entries.length} / 候选全局 API ${d.audit.bot_globals.length}\n${d.audit.notice}` : '尚未静态扫描。本服固定使用天地星 1573671599。');
    const evidence=r ? [`原生脚本入口：${r.bot_entries.length}`,`被调用的回调种类：${Object.keys(r.bot_callbacks).length}`,`缺失 API 记录：${Object.values(r.bot_missing_apis).filter(x=>x.length).length}`,`GetBot 返回有效句柄的入口：${Object.values(r.bot_contexts).filter(x=>x==='bot_handle').length}`,`完整 AI / 槽位 / 对局：仍需现场验收`,...r.connection_rejections.map(x=>'连接拒绝：'+x),...r.errors.map(x=>'异常：'+x)] : ['尚无当前游戏进程的探针证据。'];
    text('addonEvidence',evidence.join('\n'));
    text('addonEvents',r?.events.length?r.events.slice(-20).map(e=>`${e.elapsed}s [${e.kind}] ${e.detail}`).join('\n'):'暂无事件。');
    text('addonWarning',d.notice);
  }
  async function refresh(){if(polling)return;polling=true;try{render(await api('/api/addon'));}finally{polling=false;}}
  $('addonForm').addEventListener('change',()=>editing=true);
  $('addonForm').addEventListener('submit',async e=>{e.preventDefault();try{
    await api('/api/addon',{schema:1,enabled:$('addonEnabled').checked,probe_bots:true,launch_method:$('addonLaunch').value});
    editing=false;await refresh();showMessage('附加模式配置已保存。启动前会检查编译资源；没有自动重启。');
  }catch(err){showMessage(err.message,true);}});
  $('addonReload').onclick=()=>{editing=false;refresh().catch(e=>showMessage(e.message,true));};
  $('addonStatusRequest').onclick=async()=>{try{await api('/api/console',{command:'lan_status'});showMessage('已请求附加模式状态；等待引擎回复。');}catch(e){showMessage(e.message,true);}};
  $('addonReleaseHost').onclick=async()=>{if(!confirm('仅在准备阶段重新选举配置者；确定？'))return;try{await api('/api/console',{command:'lan_release_host'});showMessage('已发送重新选举请求。');}catch(e){showMessage(e.message,true);}};
  return {refresh,render};
})();
