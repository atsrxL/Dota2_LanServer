'use strict';
/* Overview summary: game resource readiness and source / deployment / client package consistency. */
window.AddonPanel=(()=>{
 let polling=false,last=-Infinity;
 const short=h=>h?h.slice(0,12):'—';
 function render(d,client){
  const r=d.runtime,src=d.source.source_sha256,dep=d.deployment?.source_sha256;
  $('addonSummary').textContent=(d.source.ready?'游戏资源已核对':'游戏资源未就绪：'+d.source.reason)+(d.recovery_required?'；部署需要恢复':'')+(d.deployment_error?'；'+d.deployment_error:'')+(r?.running?'；'+(r.fresh?r.state.phase:'等待游戏心跳'):'；游戏未运行')+(r?.running&&r.errors.length?'；'+r.errors.join('；'):'')
   +(r?.running&&r.stale_clients?.length?'；'+r.stale_clients.length+' 名玩家的客户端资源版本不符，需重新安装':'')
   +(r?.running&&r.restart_requested?'；游戏内已请求重启对局':'');
  const deployState=!dep?'尚未部署':dep===src?'已部署 · 与源码一致':'已部署旧版本 · 需停服重新部署';
  const clientState=!client?.available?(client?.message||'客户端包未发布'):client.version+(client.server_matches?' · 与源码一致':' · 与源码不一致，需重新发布');
  $('addonVersions').textContent=`源码 ${short(src)}　服务器 ${short(dep)}（${deployState}）　客户端包 ${clientState}`;
  $('addonVersions').classList.toggle('error',!!(dep&&dep!==src)||!!(client?.available&&!client.server_matches));
 }
 // The source hash walks the addon tree; the overview does not need it every 2.5 s poll.
 async function refresh(force=false){
  if(polling||(!force&&performance.now()-last<15000))return;polling=true;
  try{const [d,client]=await Promise.all([api('/api/addon'),api('/api/client-resources')]);render(d,client);last=performance.now();}finally{polling=false;}
 }
 return {refresh,render};
})();
