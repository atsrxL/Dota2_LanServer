'use strict';
// No external assets, persisted credentials, HTML injection or browser Steam API calls.
window.BotPanel = (() => {
  let refreshing = false;
  const describe = s => s ? `${s.title || s.item_id} · ${s.item_id}\nSHA ${s.version.slice(0, 16)}… · 难度 ${s.difficulty}` : '不使用面板自定义脚本（恢复接管前目录）';
  const options = () => ({difficulty:Number($('botDifficulty').value),entry_probe:$('botEntryProbe').checked});
  const run = async (action, data = {}) => {
    try { await submitAction(action, data); await refresh(); }
    catch (e) { showMessage(e.message, true); }
  };
  function renderRuntime(s) {
    const j = s.active_job;
    document.querySelectorAll('.bot-action').forEach(b => b.disabled = !!j);
    $('botRunning').textContent = s.running ? describe(s.bot_runtime?.selection) : '游戏未运行';
    $('botEvidence').textContent = !s.running || !s.bot_runtime?.selection ? '未验证 / 当前无自定义脚本'
      : s.bot_runtime.entry_seen ? '入口日志已检测到；完整 AI 与位置仍待实机验收'
      : '尚未检测到入口日志（可能未填充机器人、探针关闭或未加载）';
    $('botCancel').disabled = !(j && ['bot_download','bot_check'].includes(j.action));
    $('botPopulate').disabled = !s.running || !!j;
  }
  function button(text, handler, className='secondary') {
    const b=document.createElement('button');b.type='button';b.className=className+' bot-action';b.textContent=text;
    b.disabled=!!status?.active_job;b.onclick=handler;return b;
  }
  async function refresh() {
    if (refreshing || !csrf) return;
    refreshing=true;
    try {
      const data=await api('/api/bots');
      $('botNext').textContent=describe(data.selected);
      $('botRecovery').hidden=!data.recovery_required && !data.recovery_error;
      $('botRecovery').textContent=data.recovery_error || '上次部署中断；下次启动前将尝试恢复原目录。请勿手工删除备份。';
      const root=$('botLibrary');
      const chosen=new Map(Array.from(root.querySelectorAll('select')).map(el=>[el.dataset.item,el.value]));
      if(!root.contains(document.activeElement)) {
        root.replaceChildren();
        if(!data.items.length)root.textContent='还没有安装机器人。输入左上角的 ID 下载即可。';
        for(const item of data.items) {
          const card=document.createElement('div');card.className='bot-library-item';card.dataset.item=item.item_id;
          const head=document.createElement('h4');head.textContent=item.title;
          const meta=document.createElement('p');meta.className='footnote';meta.textContent=`Workshop ${item.item_id} · ${item.versions.length} 个本地版本 · 最近元数据检查 ${localDate(item.checked_at)}`;
          const select=document.createElement('select');select.dataset.item=item.item_id;select.setAttribute('aria-label',`${item.item_id} 的已安装版本`);
          for(const version of item.versions) {
            const option=document.createElement('option');option.value=version.version;
            option.textContent=`${version.version.slice(0,16)}… · ${localDate(version.installed_at)} · ${((version.bytes||0)/1048576).toFixed(2)} MiB`;
            select.append(option);
          }
          const desired=chosen.get(item.item_id) || (data.selected?.item_id===item.item_id ? data.selected.version : item.latest_version);
          if(Array.from(select.options).some(o=>o.value===desired))select.value=desired;
          const row=document.createElement('div');row.className='button-row';
          row.append(button('设为下一局',()=>run('bot_select',{item_id:item.item_id,version:select.value,...options()})),
            button('下载最新版本',()=>download(item.item_id,false)),
            button('移除此版本',()=>{if(confirm('只移除这个未被引用的版本？不会删除 Steam 缓存。'))run('bot_remove',{item_id:item.item_id,version:select.value});},'ghost'));
          card.append(head,meta,select,row);root.append(card);
        }
      }
      const recent=jobs.find(j=>j.action.startsWith('bot_'));
      if(recent) {
        if(recent.workshop)$('botLookup').textContent=`${recent.workshop.title} · App 570 · ${recent.workshop.item_id}\n${recent.message}`;
        const log=await api('/api/logs?name='+encodeURIComponent(recent.id));$('botLog').textContent=log.text;
      }
      if(status)renderRuntime(status);
    } finally { refreshing=false; }
  }
  async function download(item, selectAfter) {
    const payload={item_id:item, username:$('steamUser').value.trim() || config?.steam_username || '',
      password:$('steamPass').value,guard:$('steamGuard').value.trim(),select_after:selectAfter,...options()};
    if(!payload.username){showMessage('请先在 SteamCMD 页面填写并保存 Steam 账号名；这不是面板登录。',true);setPage('steam');return;}
    try {await run('bot_download',payload);}
    finally {$('steamPass').value='';$('steamGuard').value='';payload.password='';payload.guard='';}
  }
  $('botDownloadForm').onsubmit=e=>{e.preventDefault();download($('botItemId').value.trim(),$('botSelectAfter').checked);};
  $('botCheck').onclick=()=>run('bot_check',{item_id:$('botItemId').value.trim()});
  $('botDefault').onclick=()=>run('bot_default');
  $('botRollback').onclick=()=>run('bot_rollback');
  $('botRefresh').onclick=()=>refresh().catch(e=>showMessage(e.message,true));
  $('botPopulate').onclick=async()=>{if(!confirm('确认人类玩家已连接并选好队伍，再填充空位？'))return;try{await api('/api/console',{command:'bots'});showMessage('填充命令已发送；检查游戏和入口日志。');}catch(e){showMessage(e.message,true);}};
  $('botCancel').onclick=async()=>{if(!status?.active_job||!confirm('取消当前机器人下载/检查？已安装和运行版本不会被更换。'))return;try{await api('/api/cancel',{job_id:status.active_job.id});await poll();}catch(e){showMessage(e.message,true);}};
  return {refresh,renderRuntime};
})();
