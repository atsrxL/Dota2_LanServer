from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from panel.resources import ResourceMonitor, cpu_ids, cpu_times

GIB=1024**3

class Clock:
    def __init__(self): self.value=100.0
    def __call__(self): return self.value
    def step(self,n=2): self.value+=n

@pytest.fixture
def sample_tree(tmp_path):
    proc=tmp_path/'proc'; cg=tmp_path/'cgroup'
    (proc/'self').mkdir(parents=True); cg.mkdir()
    def write(path,text): path.write_text(str(text))
    write(proc/'stat','\n'.join(f'cpu{i} 100 0 0 900 0 0 0 0 0 0' for i in range(6)))
    write(proc/'self/mountinfo','123 45 0:66 / /proc/stat rw - fuse.lxcfs lxcfs rw\n124 45 0:66 / /proc/meminfo rw - fuse.lxcfs lxcfs rw')
    write(proc/'meminfo',f'MemTotal: {6*GIB//1024} kB\nMemAvailable: {4*GIB//1024} kB\nCached: {GIB//1024} kB\nSwapTotal: 1048576 kB\nSwapFree: 524288 kB\n')
    write(cg/'cpuset.cpus.effective','0-5');write(cg/'cpu.max','600000 100000')
    write(cg/'cpu.stat','usage_usec 2000000\nuser_usec 1000000\nsystem_usec 1000000\n')
    write(cg/'memory.current',3*GIB);write(cg/'memory.max',6*GIB)
    write(cg/'memory.stat',f'file {GIB}\ninactive_file {GIB//2}\nanon {2*GIB}\n')
    write(cg/'memory.events','low 0\nmax 2\noom 1\noom_kill 1\n')
    write(cg/'memory.swap.current',GIB//4);write(cg/'memory.swap.max',GIB)
    clock=Clock()
    monitor=ResourceMonitor(proc,cg,clock=clock,wall_clock=clock,affinity=lambda:set(range(6)))
    return monitor,proc,cg,clock,write


def test_first_sample_is_not_fake_zero(sample_tree):
    m,p,c,t,w=sample_tree
    s=m.sample()
    assert s['cpu']['total_percent'] is None and s['interval_seconds'] is None
    assert len(s['cpu']['per_core'])==6 and all(x['percent'] is None for x in s['cpu']['per_core'])
    assert s['memory']['percent']==50


def test_cpu_delta_uses_total_quota_and_per_core_counter_delta(sample_tree):
    m,p,c,t,w=sample_tree;m.sample();t.step(2)
    w(c/'cpu.stat','usage_usec 8000000')  # 6M us in 2s = three busy cores out of six
    w(p/'stat','\n'.join(f'cpu{i} 180 0 0 1020 0 0 0 0 0 0' for i in range(6)))
    s=m.sample();assert s['cpu']['total_percent']==50 and s['cpu']['cores_used']==3
    assert s['cpu']['capacity_cores']==6
    assert all(x['percent']==40 for x in s['cpu']['per_core'])


def test_memory_charge_working_set_cache_swap_events(sample_tree):
    s=sample_tree[0].sample()['memory']
    assert s['used_bytes']==3*GIB and s['limit_bytes']==6*GIB
    assert s['working_set_bytes']==5*GIB//2 and s['cache_bytes']==GIB
    assert s['swap_used_bytes']==GIB//4 and s['swap_limit_bytes']==GIB
    assert s['events']['oom_kill']==1 and s['source']=='cgroup-v2/memory.current'


def test_reads_cgroup_root_not_agent_service_subset(sample_tree):
    m,p,c,t,w=sample_tree
    service=c/'system.slice/dota-agent.service';service.mkdir(parents=True)
    w(service/'memory.current',123);w(service/'memory.max',456)
    w(p/'self/cgroup','0::/system.slice/dota-agent.service')
    assert m.sample()['memory']['used_bytes']==3*GIB


def test_multiple_clients_use_one_sample_and_cannot_mutate_it(sample_tree):
    m,p,c,t,w=sample_tree;first=m.sample();t.step(.2);w(c/'memory.current',4*GIB)
    with ThreadPoolExecutor(max_workers=8) as pool:
        samples=list(pool.map(lambda _:m.sample(),range(20)))
    assert all(s['sequence']==first['sequence'] for s in samples)
    samples[0]['cpu']['per_core'].clear()
    assert len(m.sample()['cpu']['per_core'])==6
    t.step(1);assert m.sample()['memory']['used_bytes']==4*GIB


def test_missing_files_degrade_to_visible_proc_scope(sample_tree):
    m,p,c,t,w=sample_tree
    for f in c.iterdir(): f.unlink()
    w(p/'self/mountinfo','')
    s=m.sample();assert s['cpu']['source']=='/proc/stat' and s['cpu']['scope']=='system-visible'
    assert s['memory']['source']=='/proc/meminfo' and s['memory']['used_bytes']==2*GIB
    assert s['memory']['working_set_bytes'] is None
    assert s['memory']['swap_used_bytes']==GIB//2
    assert any('宿主' in x for x in s['warnings'])


def test_missing_everything_is_none_not_guessed_six_gib(sample_tree):
    m,p,c,t,w=sample_tree
    for f in list(c.iterdir())+[p/'stat',p/'meminfo',p/'self/mountinfo']: f.unlink()
    s=m.sample();assert s['memory']['used_bytes'] is None and s['memory']['limit_bytes'] is None
    assert s['cpu']['total_percent'] is None and s['cpu']['per_core']==[]


def test_no_finite_memory_limit_no_fake_percentage(sample_tree):
    m,p,c,t,w=sample_tree;w(c/'memory.max','max')
    w(p/'self/mountinfo','')
    s=m.sample();assert s['memory']['percent'] is None and s['memory']['limit_bytes'] is None
    assert s['memory']['used_bytes']==3*GIB


def test_lxcfs_inherited_memory_limit_without_hardcoded_capacity(sample_tree):
    m,p,c,t,w=sample_tree
    w(c/'memory.max','max');w(c/'memory.swap.max','max')
    w(p/'meminfo',f'MemTotal: {8*GIB//1024} kB'+chr(10)+'SwapTotal: 2097152 kB')
    memory=m.sample()['memory']
    assert memory['limit_bytes']==8*GIB and memory['percent']==37.5
    assert memory['swap_limit_bytes']==2*GIB
    assert memory['limit_source']=='lxcfs:/proc/meminfo/MemTotal'


def test_working_set_clamped_when_counters_read_between_reclaim(sample_tree):
    m,p,c,t,w=sample_tree;w(c/'memory.stat',f'inactive_file {10*GIB}\nfile {GIB}')
    assert m.sample()['memory']['working_set_bytes']==0


def test_guest_ticks_are_not_double_counted(sample_tree):
    m,p,c,t,w=sample_tree;m.sample();t.step()
    # User +100 includes guest +80. Idle +100. Correct use is 50%, not 64.3%.
    w(p/'stat','\n'.join(f'cpu{i} 200 0 0 1000 0 0 0 0 80 0' for i in range(6)))
    assert all(x['percent']==50 for x in m.sample()['cpu']['per_core'])


def test_counter_reset_and_hotplug_reprime_not_negative(sample_tree):
    m,p,c,t,w=sample_tree;m.sample();t.step()
    w(c/'cpu.stat','usage_usec 20');w(p/'stat','cpu0 1 0 0 1 0 0 0 0\ncpu9 20 0 0 30 0 0 0 0')
    s=m.sample();assert s['cpu']['total_percent'] is None
    assert all(x['percent'] is None for x in s['cpu']['per_core'])
    t.step();w(c/'cpu.stat','usage_usec 2000020')
    assert m.sample()['cpu']['total_percent']==pytest.approx(16.67)


def test_quota_change_reprime_then_use_fractional_quota(sample_tree):
    m,p,c,t,w=sample_tree;m.sample();t.step();w(c/'cpu.max','150000 100000');w(c/'cpu.stat','usage_usec 4000000')
    assert m.sample()['cpu']['total_percent'] is None
    t.step();w(c/'cpu.stat','usage_usec 6000000')
    s=m.sample();assert s['cpu']['capacity_cores']==1.5 and s['cpu']['total_percent']==pytest.approx(66.67)


def test_zero_and_malformed_quota_dont_crash(sample_tree):
    m,p,c,t,w=sample_tree;w(c/'cpu.max','0 0');w(c/'memory.current','not-a-number')
    assert m.sample()['cpu']['capacity_cores']==6
    t.step();w(c/'cpu.max','garbage')
    assert m.sample()['memory']['source']=='/proc/meminfo'


def test_lxcfs_ids_not_intersected_with_physical_affinity(sample_tree):
    m,p,c,t,w=sample_tree;m.affinity=lambda:set(range(12,18));w(c/'cpuset.cpus.effective','12-17')
    s=m.sample();assert len(s['cpu']['per_core'])==6
    assert [x['id'] for x in s['cpu']['per_core']]==list(range(6))


def test_non_virtual_proc_filtered_to_actual_affinity(sample_tree):
    m,p,c,t,w=sample_tree;w(p/'self/mountinfo','');m.affinity=lambda:{1,3,5};w(c/'cpuset.cpus.effective','0-5')
    s=m.sample();assert [x['id'] for x in s['cpu']['per_core']]==[1,3,5]
    assert s['cpu']['capacity_cores']==3 and s['cpu']['per_core_scope']=='system-visible'


def test_iowait_counts_as_idle(sample_tree):
    m,p,c,t,w=sample_tree;m.sample();t.step()
    w(p/'stat','\n'.join(f'cpu{i} 150 0 0 900 50 0 0 0' for i in range(6)))
    assert all(x['percent']==50 for x in m.sample()['cpu']['per_core'])


def test_fallback_cpu_not_load_average(sample_tree):
    m,p,c,t,w=sample_tree;(c/'cpu.stat').unlink();m.sample();t.step()
    w(p/'stat','\n'.join(f'cpu{i} 150 0 0 1050 0 0 0 0' for i in range(6)))
    assert m.sample()['cpu']['total_percent']==25


def test_sample_clock_rollback_reprimes(sample_tree):
    m,p,c,t,w=sample_tree;m.sample();t.value-=10
    assert m.sample()['cpu']['total_percent'] is None


@pytest.mark.parametrize('text,expected',[('0-5',set(range(6))),('1,3,8-9',{1,3,8,9}),('',set()),('4-2',set()),('1-99999999',set()),('x',set()),('1-2-3',set())])
def test_cpu_list_parsing(text,expected): assert cpu_ids(text)==expected


def test_short_and_malformed_proc_lines():
    assert cpu_times('cpu 0 0 0 0\ncpu0 10 0 0 20\ncpu1 broken\ncpu2 -1 2 3 4')=={0:(10,0,0,20,0,0,0,0)}


def test_manager_metrics_rpc_and_compatibility_keys(paths):
    from panel.agent import Manager
    manager=Manager(paths)
    snap=manager.dispatch({'op':'metrics'})
    assert snap['schema']==1 and 'per_core' in snap['cpu']
    old=manager.status()['metrics']
    assert 'resources' in old and 'disk_free' in old and 'memory_current' in old
    manager.close()
