'use strict';
const $ = id => document.getElementById(id);
const labels = {login:'Steam 登录',install:'安装 / 校验',update:'更新',validate:'校验修复',start:'启动',stop:'停止',restart:'重启',backup:'配置备份',restore:'恢复配置'};
const states = {running:'执行中',waiting:'等待输入',success:'成功',failed:'失败',cancelled:'已取消',interrupted:'已中断'};
let csrf = null, currentPage = 'overview', config = null, status = null, jobs = [], polling = false;
let noAuth = true, toastTimer;
const gib = n => typeof n === 'number' ? (n / 1073741824).toFixed(1) + ' GiB' : '未提供';
function showMessage(text, bad=false) { const e=$('toast'); e.textContent=text; e.classList.toggle('danger',bad); e.hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>e.hidden=true,10000); }
function loggedOut() { if(noAuth){csrf=null;bootstrap();return;} csrf=null; config=null; status=null; jobs=[]; $('application').hidden=true; $('loginScreen').hidden=false; for(const id of ['loginPass','steamPass','steamGuard','taskSecret'])$(id).value=''; $('configForm').elements.namedItem('game_password').value=''; }
async function api(path, data) {
  const options={method:data===undefined?'GET':'POST',credentials:'same-origin',headers:{}};
  if(data!==undefined){ options.headers['Content-Type']='application/json'; if(csrf)options.headers['X-CSRF-Token']=csrf; options.body=JSON.stringify(data); }
  const res=await fetch(path,options);
  let body; try { body=await res.json(); } catch { throw new Error('服务器返回了非 JSON 响应，请检查 HTTP 代理、面板服务或访问白名单。'); }
  if(!res.ok){if(res.status===401&&path!=='/api/login')loggedOut(); throw new Error(body.error||`HTTP ${res.status}`);}
  return body;
}
function localDate(s){return s?new Date(s).toLocaleString(): '—';}
function setPage(page){
  if(!$(page)||!$(page).classList.contains('page'))return;
  currentPage=page; document.querySelectorAll('.page').forEach(x=>x.hidden=x.id!==page);
  document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===page));
  $('pageTitle').textContent={overview:'运行概览',steam:'SteamCMD',jobs:'任务记录',logs:'日志与控制台',settings:'服务器配置',backups:'备份与诊断'}[page];
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
  $('memory').textContent=s.metrics.memory_max?`${(s.metrics.memory_current/1073741824).toFixed(1)} / ${(s.metrics.memory_max/1073741824).toFixed(1)} GiB`:'未提供';
  $('disk').textContent=gib(s.metrics.disk_free); $('diskTotal').textContent=`文件系统总量 ${gib(s.metrics.disk_total)}`;
  $('buildId').textContent=s.manifest.buildid||'未安装'; $('udpState').textContent=`UDP ${s.port}：${s.udp_port_listening?'发现监听（非联机验收）':'未发现监听'}`;
  $('maintenanceWarning').hidden=!s.maintenance_block;
  const j=s.active_job;
  $('currentTask').textContent=j?`${labels[j.action]||j.action} · ${states[j.state]||j.state}\n${j.message}`:'当前没有任务；服务器运行与下载由独立代理管理。';
  $('progressLine').hidden=!j;
  $('pendingInput').hidden=!(j&&j.waiting_for);
  if(j&&j.waiting_for){$('inputTitle').textContent=j.waiting_for==='guard'?'Steam Guard 验证码':'Steam 登录密码';$('inputMessage').textContent=j.message;}
  $('cancelTask').disabled=!(j&&['login','install','update','validate'].includes(j.action));
  document.querySelectorAll('.action,.steam-action').forEach(b=>{const a=b.dataset.action; b.disabled=!!j||(a==='start'&&(s.running||!s.installed||!!s.maintenance_block))||(a==='stop'&&!s.running)||(a==='restart'&&(!s.installed||!!s.maintenance_block));});
}
function renderJobs(){
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
  if(currentPage==='backups')await loadBackups();
  if(currentPage==='logs'){const data=await api('/api/logs?name='+encodeURIComponent($('logChoice').value));$('mainLog').textContent=data.text;}
  if(currentPage==='steam'&&jobs.length){const data=await api('/api/logs?name='+encodeURIComponent(status?.active_job?.id||jobs[0].id));$('steamLog').textContent=data.text;}
}
async function poll(){
  if(!csrf||polling)return;polling=true;
  try{const [s,j]=await Promise.all([api('/api/status'),api('/api/jobs')]);renderStatus(s);jobs=j;renderJobs();await refreshExtra();}
  catch(e){$('apiState').textContent='连接异常';$('apiState').classList.remove('accent');if(csrf)showMessage(e.message,true);}
  finally{polling=false;}
}
async function afterLogin(token){csrf=token;$('loginScreen').hidden=true;$('application').hidden=false;$('loginError').textContent='';await loadConfig();await poll();}
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
$('loginForm').addEventListener('submit',async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{const d=await api('/api/login',{username:$('loginUser').value,password:$('loginPass').value});$('loginPass').value='';await afterLogin(d.csrf);}catch(err){$('loginError').textContent=err.message;}finally{button.disabled=false;}});
$('logout').onclick=async()=>{try{await api('/api/logout',{});}catch{}loggedOut();};
onClick('[data-page]',el=>setPage(el.dataset.page));onClick('[data-go]',el=>setPage(el.dataset.go));
onClick('.action',el=>submitAction(el.dataset.action));onClick('.steam-action',el=>steamAction(el.dataset.action));
onClick('.console-preset',el=>api('/api/console',{command:el.dataset.command}).then(()=>showMessage('命令已提交，检查游戏日志。')));
$('copyConnect').onclick=async()=>{try{await navigator.clipboard.writeText($('connectCommand').textContent);showMessage('连接命令已复制。');}catch{showMessage('浏览器不允许剪贴板访问，请选中连接命令手动复制。',true);}};
$('rememberUser').onclick=async()=>{try{const c=await api('/api/config');c.steam_username=$('steamUser').value.trim();await api('/api/config',c);config=c;showMessage('只保存了账号名，没有保存 Steam 密码。');}catch(e){showMessage(e.message,true);}};
$('taskInputForm').addEventListener('submit',async e=>{e.preventDefault();const value=$('taskSecret').value;$('taskSecret').value='';try{await api('/api/input',{job_id:status?.active_job?.id,value});showMessage('一次性输入已提交。');await poll();}catch(err){showMessage(err.message,true);}});
$('cancelTask').onclick=async()=>{if(!status?.active_job||!confirm('取消会中断 SteamCMD；安装中断后须成功校验才能开服。确认？'))return;try{await api('/api/cancel',{job_id:status.active_job.id});await poll();}catch(e){showMessage(e.message,true);}};
$('sayForm').addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/console',{command:'say',text:$('sayText').value});$('sayText').value='';showMessage('消息已提交。');}catch(err){showMessage(err.message,true);}});
$('configForm').addEventListener('submit',async e=>{e.preventDefault();const f=e.target;const c={schema:1};for(const key of ['hostname','map','game_password','steam_username'])c[key]=f.elements.namedItem(key).value;for(const key of ['port','game_mode'])c[key]=Number(f.elements.namedItem(key).value);for(const key of ['auto_start','auto_restart','cheats','insecure'])c[key]=f.elements.namedItem(key).checked;try{const r=await api('/api/config',c);config=c;$('serverName').textContent=c.hostname;showMessage('配置已保存。'+(r.restart_required?'下次重启游戏后生效。':'')+'更改端口须同步 PVE 防火墙。');}catch(err){showMessage(err.message,true);}});
$('reloadConfig').onclick=()=>loadConfig().then(()=>showMessage('已重新读取配置。')).catch(e=>showMessage(e.message,true));
$('refreshLog').onclick=()=>refreshExtra().catch(e=>showMessage(e.message,true));$('logChoice').onchange=$('refreshLog').onclick;
async function bootstrap(){try{const s=await api('/api/session');noAuth=!!s.no_auth;$('logout').hidden=noAuth;$('version').textContent='v'+s.version;if(s.authenticated)await afterLogin(s.csrf);}catch(e){$('application').hidden=true;$('loginScreen').hidden=false;$('loginError').textContent=e.message;}}
bootstrap();
setInterval(poll,2500);
