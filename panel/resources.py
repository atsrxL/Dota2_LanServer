"""Read-only Linux resource sampling. Stdlib only; no shell, root, sleep or agents.

Total CPU/memory prefer the *visible cgroup mount root*, not dota-agent.service's
subgroup. Per-core /proc/stat is explicitly a visible/LXCFS view; cgroup v2 has
no authoritative per-task-per-core accounting interface. Never invent six bars
or divide load averages to make a CPU percentage. Missing samples are None.
"""
from __future__ import annotations
import copy
import os
import re
import threading
import time
from pathlib import Path
from typing import Callable


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding='ascii').strip()
    except (OSError, UnicodeError):
        return ''


def _number(value: str) -> int | None:
    try:
        n = int(value)
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def _kv(text: str) -> dict[str, int]:
    values = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and (n := _number(parts[1])) is not None:
            values[parts[0].rstrip(':')] = n
    return values


def cpu_ids(text: str) -> set[int]:
    """Parse a bounded Linux CPU list, including non-contiguous assignments."""
    result: set[int] = set()
    try:
        for piece in text.strip().split(','):
            if not piece:
                continue
            pair = piece.split('-')
            if len(pair) > 2:
                return set()
            start = int(pair[0]); end = int(pair[-1])
            if start < 0 or start > end or end > 65535 or end - start > 8192:
                return set()
            result.update(range(start, end + 1))
            if len(result) > 8192:
                return set()
    except ValueError:
        return set()
    return result


def cpu_times(text: str) -> dict[int, tuple[int, ...]]:
    result = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts or not re.fullmatch(r'cpu\d+', parts[0]) or len(parts) < 5:
            continue
        try:
            # user,nice,system,idle,iowait,irq,softirq,steal. Guest time is
            # already counted in user/nice: do NOT add guest/guest_nice twice.
            values = tuple(int(x) for x in parts[1:9])
            if min(values) < 0:
                continue
            result[int(parts[0][3:])] = values + (0,) * (8 - len(values))
        except ValueError:
            continue
    return result


def _delta(current, previous) -> tuple[int, int] | None:
    if previous is None:
        return None
    changes = [a - b for a, b in zip(current, previous)]
    if any(x < 0 for x in changes):
        return None  # reset/hotplug/LXCFS counter discontinuity
    total = sum(changes)
    if total <= 0:
        return None
    idle = changes[3] + changes[4]  # idle + iowait
    return total - idle, total


def _percent(value: float | None) -> float | None:
    return round(max(0.0, min(100.0, value)), 2) if value is not None else None


class ResourceMonitor:
    """One cached sampler per manager, shared safely by all browser requests.

    cgroup_root is a fixed installation path, never HTTP/user controlled. Reading
    the root intentionally includes all guest services/SteamCMD/game descendants.
    In non-LXC environments its scope can be wider: the API discloses sources.
    """
    def __init__(self, proc_root: Path = Path('/proc'), cgroup_root: Path = Path('/sys/fs/cgroup'),
                 min_interval: float = 1.0, clock: Callable[[], float] = time.monotonic,
                 wall_clock: Callable[[], float] = time.time,
                 affinity: Callable[[], set[int]] | None = None):
        self.proc = proc_root
        self.cgroup = cgroup_root
        self.min_interval = max(0.1, min_interval)
        self.clock = clock
        self.wall_clock = wall_clock
        self.affinity = affinity or (lambda: set(os.sched_getaffinity(0)))
        self.lock = threading.Lock()
        self.latest: dict | None = None
        self.last_time: float | None = None
        self.previous: dict = {}
        self.sequence = 0

    def _lxcfs(self, name: str, mounts: str) -> bool:
        for line in mounts.splitlines():
            fields = line.split()
            if len(fields) > 6 and fields[4] == '/proc/' + name:
                after = line.split(' - ', 1)[-1].split()
                if any('lxcfs' in x for x in after[:2]):
                    return True
        return False

    def sample(self) -> dict:
        with self.lock:
            tick = self.clock()
            elapsed = tick - self.last_time if self.last_time is not None else None
            if self.latest is not None and elapsed is not None and 0 <= elapsed < self.min_interval:
                return copy.deepcopy(self.latest)
            if elapsed is not None and elapsed <= 0:
                self.previous = {}
                elapsed = None
            warnings: list[str] = []
            mounts = _text(self.proc / 'self/mountinfo')
            times = cpu_times(_text(self.proc / 'stat'))
            virtual = self._lxcfs('stat', mounts)
            cpuset = cpu_ids(_text(self.cgroup / 'cpuset.cpus.effective'))
            try:
                affinity = self.affinity()
            except (AttributeError, OSError):
                affinity = set()
            if not virtual:
                permitted = cpuset or affinity
                if cpuset and affinity:
                    permitted = cpuset & affinity
                if permitted:
                    times = {i: v for i, v in times.items() if i in permitted}
            # LXCFS can renumber visible cores; do not intersect virtual IDs with
            # physical affinity IDs (e.g. visible 0-5 vs physical 12-17).
            bounds: list[float] = []
            if cpuset:
                bounds.append(float(len(cpuset)))
            if not virtual and affinity:
                bounds.append(float(len(affinity)))
            if not bounds and times:
                bounds.append(float(len(times)))
            quota = _text(self.cgroup / 'cpu.max').split()
            if len(quota) == 2:
                q, period = _number(quota[0]), _number(quota[1])
                if q is not None and period and q > 0:
                    bounds.append(q / period)
            capacity = min(bounds) if bounds else None
            usage = _kv(_text(self.cgroup / 'cpu.stat')).get('usage_usec')
            cores_used = total_percent = None
            if usage is not None:
                source, scope = 'cgroup-v2/cpu.stat', 'cgroup-mount-root'
                before = self.previous.get('usage_usec')
                if (before is not None and elapsed and usage >= before and
                        capacity == self.previous.get('capacity')):
                    cores_used = (usage - before) / (elapsed * 1_000_000)
                    if capacity:
                        total_percent = _percent(100 * cores_used / capacity)
            else:
                source, scope = '/proc/stat', 'lxcfs-visible' if virtual else 'system-visible'
                warnings.append('总 CPU 的 cgroup 计数不可读，已降级为可见 /proc/stat；不是已验证的容器独占统计。')
            if not virtual:
                warnings.append('未检测到 /proc/stat 的 LXCFS 挂载；每核心可能包含宿主任务，请勿当作本容器逐核用量。')
            elif cpuset and len(times) != len(cpuset):
                warnings.append('LXCFS 可见核心数与 cpuset 不一致，请现场检查 PVE/LXCFS；没有伪造或截取 6 个核心。')
            if virtual:
                warnings.append('每核心来自 LXCFS 虚拟视图；cgroup v2 下不保证精确反映本容器任务的物理逐核归属。')
            per_core = []
            busy_sum = total_sum = 0
            for core_id, values in sorted(times.items()):
                delta = _delta(values, self.previous.get('times', {}).get(core_id))
                percent = _percent(100 * delta[0] / delta[1]) if delta else None
                if delta:
                    busy_sum += delta[0]; total_sum += delta[1]
                per_core.append({'id': core_id, 'label': f'CPU {core_id}', 'percent': percent})
            if usage is None and total_sum:
                total_percent = _percent(100 * busy_sum / total_sum)
                if capacity:
                    cores_used = total_percent * capacity / 100
            if not times:
                warnings.append('每核心计数暂不可读。等待下一次采样，不将缺失数据显示为 0%。')
            cpu = {'total_percent': total_percent, 'cores_used': round(cores_used, 3) if cores_used is not None else None,
                   'capacity_cores': capacity, 'visible_core_count': len(per_core),
                   'source': source, 'scope': scope, 'per_core_source': 'lxcfs:/proc/stat' if virtual else '/proc/stat',
                   'per_core_scope': 'virtualized-view' if virtual else 'system-visible', 'per_core': per_core}
            memory = self._memory(mounts, warnings)
            self.sequence += 1
            self.latest = {'schema': 1, 'sequence': self.sequence, 'sampled_at': self.wall_clock(),
                           'interval_seconds': round(elapsed, 3) if elapsed else None,
                           'min_interval_seconds': self.min_interval,
                           'cpu': cpu, 'memory': memory, 'warnings': warnings}
            self.previous = {'times': times, 'usage_usec': usage, 'capacity': capacity}
            self.last_time = tick
            return copy.deepcopy(self.latest)

    def _memory(self, mounts: str, warnings: list[str]) -> dict:
        current = _number(_text(self.cgroup / 'memory.current'))
        limit = _number(_text(self.cgroup / 'memory.max'))
        stat = _kv(_text(self.cgroup / 'memory.stat'))
        events = _kv(_text(self.cgroup / 'memory.events'))
        swap_current = _number(_text(self.cgroup / 'memory.swap.current'))
        swap_limit = _number(_text(self.cgroup / 'memory.swap.max'))
        proc = {k: v * 1024 for k, v in _kv(_text(self.proc / 'meminfo')).items()}
        virtual = self._lxcfs('meminfo', mounts)
        source, scope = 'cgroup-v2/memory.current', 'cgroup-mount-root'
        limit_source = 'cgroup-v2/memory.max'
        if limit is None and virtual and proc.get('MemTotal', 0) > 0:
            limit = proc['MemTotal']
            limit_source = 'lxcfs:/proc/meminfo/MemTotal'
            if swap_limit is None:
                swap_limit = proc.get('SwapTotal')
        cache = stat.get('file')
        inactive = stat.get('inactive_file')
        working = max(0, current - inactive) if current is not None and inactive is not None else None
        available = max(0, limit - current) if current is not None and limit is not None else None
        if current is None:
            source, scope = '/proc/meminfo', 'lxcfs-visible' if virtual else 'system-visible'
            limit_source = 'lxcfs:/proc/meminfo/MemTotal' if virtual else '/proc/meminfo/MemTotal'
            limit, available = proc.get('MemTotal'), proc.get('MemAvailable')
            current = max(0, limit - available) if limit is not None and available is not None else None
            cache = proc.get('Cached')
            working = None  # MemAvailable-derived use is NOT the cgroup working set.
            swap_limit = proc.get('SwapTotal')
            swap_free = proc.get('SwapFree')
            swap_current = max(0, swap_limit - swap_free) if swap_limit is not None and swap_free is not None else None
            warnings.append('cgroup 内存计数不可读，显示 /proc/meminfo 可见视图；不是已验证的容器内存统计。')
        if not limit:
            warnings.append('未读取到有限内存上限；不硬编码 6 GiB，也不显示伪造的内存百分比。')
        return {'source': source, 'scope': scope, 'limit_source': limit_source, 'used_bytes': current, 'limit_bytes': limit,
                'available_bytes': available, 'working_set_bytes': working, 'cache_bytes': cache,
                'percent': _percent(100 * current / limit) if current is not None and limit else None,
                'swap_used_bytes': swap_current, 'swap_limit_bytes': swap_limit, 'events': events}
