'use strict';
const $ = id => document.getElementById(id);
const labels = {addon_deploy:'部署附加模式',addon_scan:'扫描天地星兼容性',login:'Steam 登录',install:'安装 / 校验',update:'更新',validate:'校验修复',start:'启动',stop:'停止',restart:'重启',backup:'配置备份',restore:'恢复配置',bot_download:'下载机器人',bot_check:'核对机器人条目',bot_select:'选择下局机器人',bot_default:'停用下局机器人',bot_rollback:'恢复上次机器人选择',bot_remove:'移除机器人版本'};
const states = {running:'执行中',waiting:'等待输入',success:'成功',failed:'失败',cancelled:'已取消',interrupted:'已中断'};
let csrf = null, currentPage = 'overview', config = null, status = null, jobs = [], polling = false;
let toastTimer;
const gib = n => typeof n === 'number' ? (n / 1073741824).toFixed(1) + ' GiB' : '未提供';
function showMessage(text, bad=false) { const e=$('toast'); e.textContent=text; e.classList.toggle('danger',bad); e.hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>e.hidden=true,10000); }
async function api(path, data) {
  const options={method:data===undefined?'GET':'POST',credentials:'same-origin',headers:{}};
  if(data!==undefined){ options.headers['Content-Type']='application/json'; if(csrf)options.headers['X-CSRF-Token']=csrf; options.body=JSON.stringify(data); }
  const res=await fetch(path,options);
  let body; try { body=await res.json(); } catch { throw new Error('服务器返回了非 JSON 响应，请检查 HTTP 代理或访问白名单。'); }
  if(!res.ok){if(res.status===403)csrf=null; throw new Error(body.error||`HTTP ${res.status}`);}
  return body;
}
function localDate(s){return s?new Date(s).toLocaleString(): '—';}
function setPage(page){
  if(!$(page)||!$(page).classList.contains('page'))return;
  currentPage=page; document.querySelectorAll('.page').forEach(x=>x.hidden=x.id!==page);
  document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===page));
  $('pageTitle').textContent={overview:'运行概览',steam:'SteamCMD',jobs:'任务记录',logs:'日志与控制台',settings:'服务器配置',backups:'备份与诊断',bots:'机器人脚本',addon:'LAN 附加模式'}[page];
  if(page==='settings'&&!config)loadConfig().catch(e=>showMessage(e.message,true));
  if(page==='backups')loadBackups().catch(e=>showMessage(e.message,true));
  refreshExtra().catch(e=>showMessage(e.message,true));
}
async function loadConfig(){
  config=await api('/api/config'); const form=$('configForm');
  for(const [key,value] of Object.entries(config)){const el=form.elements.namedItem(key);if(!el)continue;if(el.type==='checkbox')el.checked=value;else el.value=value;}
  $('steamUser').value=config.steam_username; $('serverName').textContent=config.hostname;
}
function renderStatus(s){
  status=s; $('apiState').textContent='代理在线'; $('apiState').classList.add('accent');
  $('serverState').textContent=s.running?'● 游戏进程运行中 · 客户端连接待验证':s.installed?'○ 已安装 · 当前未运行':'○ 等待安装 Dota 2';
  const host=location.hostname; $('connectCommand').textContent=`connect ${host}:${s.port}`;
  $('uptime').textContent=s.running?`${Math.floor(s.uptime/3600)}h ${Math.floor(s.uptime%3600/60)}m`:'未运行';
  $('pid').textContent=s.running?`PID ${s.pid}`:s.last_exit?`上次退出：${s.last_exit.exit_code??'signal '+s.last_exit.signal}`:'等待进程启动';
  $('memory').textContent=typeof s.metrics.memory_current==='number'&&s.metrics.memory_max?`${(s.metrics.memory_current/1073741824).toFixed(1)} / ${(s.metrics.memory_max/1073741824).toFixed(1)} GiB`:'未提供';
  $('disk').textContent=gib(s.metrics.disk_free); $('diskTotal').textContent=`文件系统总量 ${gib(s.metrics.disk_total)}`;
  $('buildId').textContent=s.manifest.buildid||'未安装'; $('udpState').textContent=`UDP ${s.port}：${s.udp_port_listening?'发现监听（非联机验收）':'未发现监听'}`;
  $('maintenanceWarning').hidden=!s.maintenance_block;
  const j=s.active_job;
  $('currentTask').textContent=j?`${labels[j.action]||j.action} · ${states[j.state]||j.state}\n${j.message}`:'当前没有任务；服务器运行与下载由独立代理管理。';
  $('progressLine').hidden=!j;
  $('pendingInput').hidden=!(j&&j.waiting_for);
  if(j&&j.waiting_for){$('inputTitle').textContent=j.waiting_for==='guard'?'Steam Guard 验证码':'Steam 登录密码';$('inputMessage').textContent=j.message;}
  $('cancelTask').disabled=!(j&&['login','install','update','validate','bot_download','bot_check'].includes(j.action));
  document.querySelectorAll('.action,.steam-action').forEach(b=>{const a=b.dataset.action; b.disabled=!!j||(a==='start'&&(s.running||!s.installed||!!s.maintenance_block))||(a==='addon_deploy'&&s.running)||(a==='stop'&&!s.running)||(a==='restart'&&(!s.installed||!!s.maintenance_block));});
}
function renderSteamAuth(){
 const steamActions=['login','install','update','validate','bot_download'];
 const relevant=jobs.filter(j=>steamActions.includes(j.action));
 const latest=relevant[0];
 const success=relevant.find(j=>j.authenticated_at||(j.action==='login'&&j.state==='success'));
 const active=status?.active_job;
 const busy=active&&steamActions.includes(active.action);
 const stageNames={logging_in:'正在登录',awaiting_mobile_approval:'等待 Steam 手机批准',authenticated:'本次登录已验证',starting:'正在启动 SteamCMD'};
 $('steamAuthState').textContent=busy?(active.waiting_for?'等待密码 / Steam Guard 输入':stageNames[active.stage]||'正在执行 SteamCMD 任务'):latest&&['failed','cancelled','interrupted'].includes(latest.state)?'最近 SteamCMD 任务'+(states[latest.state]||latest.state):success?'最近登录验证成功':'尚无成功登录验证记录';
 $('steamAuthDetail').textContent=(success?'最近成功验证：'+localDate(success.authenticated_at||success.finished_at)+'。 ':'')+(latest?'最近任务：'+(labels[latest.action]||latest.action)+' · '+(states[latest.state]||latest.state)+' · '+latest.message:'点击“测试登录 / 授权”验证。');
 $('steamAccountState').textContent=config?.steam_username?'已保存账号名：'+config.steam_username:'尚未保存账号名；登录成功后可点“仅保存账号名”，方便下次使用。';
}
function renderJobs(){
  renderSteamAuth();
  const tbody=$('jobTable');tbody.replaceChildren();
  if(!jobs.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=5;td.textContent='暂无任务记录。';tr.append(td);tbody.append(tr);return;}
  for(const j of jobs){
    const tr=document.createElement('tr');
    const td=document.createElement('td'),btn=document.createElement('button');btn.className='table-action';btn.textContent=labels[j.action]||j.action;btn.addEventListener('click',()=>showJobLog(j.id));
    const small=document.createElement('small');small.textContent=j.id;td.append(btn,small);tr.append(td);
    for(const val of [states[j.state]||j.state,j.stage,localDate(j.started_at),j.message]){const c=document.createElement('td');c.textContent=val;tr.append(c);}tbody.append(tr);
  }
  const select=$('logChoice'),selected=select.value;
  select.replaceChildren();
  for(const [value,text] of [['server','游戏服务器'],['agent','运行代理'],...jobs.slice(0,30).map(j=>[j.id,`${labels[j.action]} · ${j.id}`])]){const o=document.createElement('option');o.value=value;o.textContent=text;select.append(o);}
  if(Array.from(select.options).some(x=>x.value===selected))select.value=selected;
}
async function refreshExtra(){
  if(!csrf)return;
  if(currentPage==='overview'&&window.AddonPanel)await window.AddonPanel.refresh();
  if(currentPage==='backups')await loadBackups();
  if(currentPage==='logs'){const data=await api('/api/logs?name='+encodeURIComponent($('logChoice').value));$('mainLog').textContent=data.text;}
  if(currentPage==='steam'){const j=jobs.find(j=>['login','install','update','validate','bot_download'].includes(j.action));$('steamLog').textContent=j?(await api('/api/logs?name='+encodeURIComponent(j.id))).text:'暂无 SteamCMD 任务日志。';}
}
async function poll(){
  if(polling||document.hidden)return;polling=true;
  try{if(!csrf||!config)await initializePanel();const [s,j]=await Promise.all([api('/api/status'),api('/api/jobs')]);renderStatus(s);jobs=j;renderJobs();await refreshExtra();}
  catch(e){$('apiState').textContent='连接异常';$('apiState').classList.remove('accent');showMessage(e.message,true);}
  finally{polling=false;}
}
async function initializePanel(){
  const s=await api('/api/session'); csrf=s.csrf; $('version').textContent='v'+s.version;
  if(!config)await loadConfig();
}
async function submitAction(action, extra={}){
  if(['stop','restart'].includes(action)&&!confirm(`${labels[action]}会中断当前对局，确认继续？`))return;
  const j=await api('/api/actions',{action,...extra});showMessage(`已提交：${labels[action]}，任务 ${j.id}`);await poll();if(action==='backup')await loadBackups();
}
async function steamAction(action){
  if(action!=='login'&&$('stopForUpdate').checked&&status?.running&&!confirm('本次维护将停止服务器并中断当前对局，确认继续？'))return;
  const payload={username:$('steamUser').value.trim(),password:$('steamPass').value,guard:$('steamGuard').value.trim(),stop_server:$('stopForUpdate').checked,restart_after:$('restartAfter').checked};
  try{await submitAction(action,payload);}finally{$('steamPass').value='';$('steamGuard').value='';payload.password='';payload.guard='';}
}
async function showJobLog(id){setPage('logs');$('logChoice').value=id;const d=await api('/api/logs?name='+encodeURIComponent(id));$('mainLog').textContent=d.text;}
async function loadBackups(){
  const list=await api('/api/backups'),root=$('backupList');root.replaceChildren();
  if(!list.length){root.textContent='暂无配置快照。';return;}
  for(const b of list){const row=document.createElement('div');row.className='backup-item';const name=document.createElement('code');name.textContent=b.name;const actions=document.createElement('div');actions.className='button-row';const dl=document.createElement('a');dl.textContent='下载';dl.href='/api/backup?name='+encodeURIComponent(b.name);const restore=document.createElement('button');restore.className='ghost';restore.textContent='恢复';restore.onclick=async()=>{if(!confirm('恢复该配置？必须先停服；不会回滚游戏资源。'))return;try{await submitAction('restore',{backup:b.name});config=null;}catch(e){showMessage(e.message,true);}};actions.append(dl,restore);row.append(name,actions);root.append(row);}
}
function onClick(selector,handler){document.querySelectorAll(selector).forEach(el=>el.addEventListener('click',async()=>{try{await handler(el);}catch(e){showMessage(e.message,true);}}));}
onClick('[data-page]',el=>setPage(el.dataset.page));onClick('[data-go]',el=>setPage(el.dataset.go));
onClick('.action',el=>submitAction(el.dataset.action));onClick('.steam-action',el=>steamAction(el.dataset.action));
onClick('.console-preset',el=>api('/api/console',{command:el.dataset.command}).then(()=>showMessage('命令已提交，检查游戏日志。')));
$('copyConnect').onclick=async()=>{try{await navigator.clipboard.writeText($('connectCommand').textContent);showMessage('连接命令已复制。');}catch{const range=document.createRange();range.selectNodeContents($('connectCommand'));const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);showMessage('HTTP 下已选中连接命令，请按 Ctrl+C / Cmd+C 复制。');}};
$('rememberUser').onclick=async()=>{try{const c=await api('/api/config');c.steam_username=$('steamUser').value.trim();await api('/api/config',c);config=c;showMessage('只保存了账号名，没有保存 Steam 密码。');}catch(e){showMessage(e.message,true);}};
$('taskInputForm').addEventListener('submit',async e=>{e.preventDefault();const value=$('taskSecret').value;$('taskSecret').value='';try{await api('/api/input',{job_id:status?.active_job?.id,value});showMessage('一次性输入已提交。');await poll();}catch(err){showMessage(err.message,true);}});
$('cancelTask').onclick=async()=>{if(!status?.active_job||!confirm('取消会中断 SteamCMD；安装中断后须成功校验才能开服。确认？'))return;try{await api('/api/cancel',{job_id:status.active_job.id});await poll();}catch(e){showMessage(e.message,true);}};
$('sayForm').addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/console',{command:'say',text:$('sayText').value});$('sayText').value='';showMessage('消息已提交。');}catch(err){showMessage(err.message,true);}});
$('configForm').addEventListener('submit',async e=>{e.preventDefault();const f=e.target;const c={schema:1};for(const key of ['hostname','map','game_password','steam_username'])c[key]=f.elements.namedItem(key).value;for(const key of ['port','game_mode'])c[key]=Number(f.elements.namedItem(key).value);for(const key of ['auto_start','auto_restart','cheats','insecure'])c[key]=f.elements.namedItem(key).checked;try{const r=await api('/api/config',c);config=c;$('serverName').textContent=c.hostname;showMessage('配置已保存。'+(r.restart_required?'下次重启游戏后生效。':'')+'更改端口须同步 PVE 防火墙。');}catch(err){showMessage(err.message,true);}});
$('reloadConfig').onclick=()=>loadConfig().then(()=>showMessage('已重新读取配置。')).catch(e=>showMessage(e.message,true));
$('refreshLog').onclick=()=>refreshExtra().catch(e=>showMessage(e.message,true));$('logChoice').onchange=$('refreshLog').onclick;
poll();
setInterval(poll,2500);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
