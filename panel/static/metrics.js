'use strict';
// No login, dependencies, WebSocket server, or browser storage. Read-only HTTP.
(() => {
  const byId = id => document.getElementById(id);
  if (!byId('resourceMonitor')) return;
  const INTERVAL = 2000, WINDOW = 120000;
  let timer = null, controller = null, inFlight = false;
  let lastKey = null, lastChange = null, history = [];
  const valid = n => typeof n === 'number' && Number.isFinite(n);
  const percent = n => valid(n) ? `${n.toFixed(1)}%` : '—';
  const size = n => valid(n) ? `${(n / 1073741824).toFixed(2)} GiB` : '未提供';
  function bar(id, n) {
    const el = byId(id); el.hidden = !valid(n);
    if (valid(n)) el.value = Math.max(0, Math.min(100, n));
  }
  function drawHistory() {
    const now = performance.now();
    history = history.filter(p => now - p.at <= WINDOW).slice(-64);
    for (const [key, id] of [['cpu', 'cpuHistory'], ['memory', 'memoryHistory']]) {
      let path = '', connected = false;
      for (const p of history) {
        if (!valid(p[key])) { connected = false; continue; }
        const x = Math.max(0, 600 * (1 - (now - p.at) / WINDOW));
        const y = 130 - Math.max(0, Math.min(100, p[key])) * 1.2;
        path += `${connected ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)} `;
        connected = true;
      }
      byId(id).setAttribute('d', path.trim());
    }
  }
  function unavailable(message) {
    byId('resourceState').textContent = '监控暂不可用';
    byId('resourceState').classList.remove('accent');
    byId('resourceFreshness').textContent = message;
    byId('cpuPercent').textContent = byId('memoryPercent').textContent = '—';
    bar('cpuBar', null); bar('memoryBar', null);
    byId('cpuCores').textContent = '数据已失效；正在自动重试，不把缺失数据记为 0%。';
    for (const id of ['memoryBytes','memoryWorking','memoryCache','memorySwap','memoryOom']) byId(id).textContent = '—';
    history.push({at:performance.now(),cpu:null,memory:null}); drawHistory();
  }
  function render(data) {
    if (data?.schema !== 1 || !data.cpu || !data.memory || !Array.isArray(data.cpu.per_core) || !valid(data.sampled_at)) {
      throw new Error('监控 API 格式不匹配，请检查前后端版本。');
    }
    const now = performance.now(), key = `${data.sequence}:${data.sampled_at}`;
    const changed = key !== lastKey;
    if (changed) { lastKey = key; lastChange = now; }
    if (lastChange !== null && now - lastChange > 6000) {
      unavailable('采样超过 6 秒未更新；旧曲线仅供历史参考，正在自动重试。'); return;
    }
    const cpu = data.cpu, mem = data.memory;
    byId('resourceState').textContent = valid(cpu.total_percent) ? '实时 · 2 秒' : '首轮 / 重置后采样中';
    byId('resourceState').classList.add('accent');
    byId('resourceFreshness').textContent = `采样时间 ${new Date(data.sampled_at * 1000).toLocaleTimeString()} · 页面隐藏时暂停 · 趋势仅保存在当前页面`;
    byId('cpuPercent').textContent = percent(cpu.total_percent); bar('cpuBar',cpu.total_percent);
    byId('cpuCapacity').textContent = `占用 ${valid(cpu.cores_used)?cpu.cores_used.toFixed(2):'—'} 核 / 有效配额 ${valid(cpu.capacity_cores)?cpu.capacity_cores:'—'} 核；可见 ${cpu.visible_core_count} 核`;
    byId('cpuScope').textContent = `总量：${cpu.source}（${cpu.scope}）；每核：${cpu.per_core_source}（${cpu.per_core_scope}）。100% 表示有效总配额占满，不是只占满单核。`;
    const root = byId('cpuCores'); root.replaceChildren();
    for (const core of cpu.per_core) {
      const row = document.createElement('div'); row.className = 'cpu-core';
      const label = document.createElement('span'); label.textContent = core.label;
      const meter = document.createElement('progress'); meter.max = 100; meter.hidden = !valid(core.percent);
      if (valid(core.percent)) meter.value = core.percent;
      meter.setAttribute('aria-label', `${core.label} 占用`);
      const value = document.createElement('strong'); value.textContent = percent(core.percent);
      row.append(label,meter,value); root.append(row);
    }
    if (!cpu.per_core.length) root.textContent = '每核心数据不可用；未伪造核心列表。';
    byId('memoryPercent').textContent = percent(mem.percent); bar('memoryBar',mem.percent);
    byId('memoryBytes').textContent = `${size(mem.used_bytes)} / ${size(mem.limit_bytes)} · ${mem.source.startsWith('cgroup')?'总占用包含已计费缓存':'按 MemTotal − MemAvailable 计算的可见占用'}`;
    byId('memoryWorking').textContent = size(mem.working_set_bytes);
    byId('memoryCache').textContent = size(mem.cache_bytes);
    byId('memorySwap').textContent = `${size(mem.swap_used_bytes)} / ${size(mem.swap_limit_bytes)}`;
    byId('memoryOom').textContent = `${mem.events?.oom ?? '—'} / ${mem.events?.oom_kill ?? '—'}`;
    byId('memoryScope').textContent = `来源：${mem.source}（${mem.scope}）。工作集估算 = cgroup 总占用 − inactive_file，不是所有进程 RSS 之和。`;
    byId('resourceWarnings').textContent = (data.warnings || []).join(' ') || '只读采样。CPU 与内存是可见 cgroup 根统计，不是仅 Dota 2 进程的占用。';
    if (changed) history.push({at:now,cpu:cpu.total_percent,memory:mem.percent});
    drawHistory();
  }
  async function tick() {
    if (document.hidden || inFlight) return;
    inFlight = true; controller = new AbortController();
    const timeout = setTimeout(() => controller?.abort(), 5000);
    try {
      const res = await fetch('/api/metrics',{cache:'no-store',credentials:'same-origin',signal:controller.signal});
      if (!res.ok) throw new Error(`监控 HTTP ${res.status}；请检查运行代理和 LAN 白名单。`);
      const data = await res.json();
      if (!document.hidden) render(data);
    } catch (error) {
      if (!document.hidden) unavailable(error.name === 'AbortError' ? '监控请求超时，正在自动重试。' : error.message);
    } finally {
      clearTimeout(timeout); controller = null; inFlight = false;
      if (!document.hidden) timer = setTimeout(tick,INTERVAL);
    }
  }
  document.addEventListener('visibilitychange', () => {
    clearTimeout(timer);
    if (document.hidden) {
      controller?.abort();
      history.push({at:performance.now(),cpu:null,memory:null});
      byId('resourceState').textContent = '已暂停';
    } else if (!inFlight) tick();
  });
  tick();
})();
