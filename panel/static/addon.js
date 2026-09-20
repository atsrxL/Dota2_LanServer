
'use strict';
window.AddonPanel=(()=>{
 let polling=false;
 function render(d){
  const r=d.runtime;
  $('addonSummary').textContent=(d.source.ready?'游戏资源已核对':'游戏资源未就绪：'+d.source.reason)+(d.recovery_required?'；部署需要恢复':'')+(r?.running?'；'+(r.fresh?r.state.phase:'等待游戏心跳'):'；游戏未运行')+(r?.running&&r.errors.length?'；'+r.errors.join('；'):'');
 }
 async function refresh(){if(polling)return;polling=true;try{render(await api('/api/addon'));}finally{polling=false;}}
 return {refresh,render};
})();
