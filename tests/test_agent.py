import json
import sys
import os
import time
from pathlib import Path
import pytest
from panel.agent import Manager
from panel.common import DEFAULT_CONFIG,Fault,atomic_json,read_json


def wait(manager,timeout=20):
    end=time.monotonic()+timeout
    while manager.active and time.monotonic()<end:
        time.sleep(.05)
    assert manager.active is None,'job did not finish'
    return manager.jobs[-1]

@pytest.fixture
def manager(paths):
    m=Manager(paths)
    yield m
    m.close()

def install(m,password='test-secret-123'):
    m.submit({'action':'install','username':'tester','password':password})
    return wait(m)

def test_fake_install_start_console_stop(manager):
    assert install(manager)['state']=='success'
    s=manager.status();assert s['installed'] and s['manifest']['buildid']=='TEST-4242'
    assert not s['maintenance_block']
    manager.submit({'action':'start'});assert wait(manager)['state']=='success'
    assert manager.status()['running']
    # Production is Linux and reads /proc/net/udp; other development hosts do
    # not expose that interface. Real CT UDP listening is tracked separately.
    if sys.platform.startswith('linux'):
        assert manager.status()['udp_port_listening']
    manager.dispatch({'op':'console','data':{'command':'status'}})
    time.sleep(.2)
    assert 'TEST FIXTURE console: status' in manager.dispatch({'op':'logs','data':{'name':'server'}})['text']
    manager.submit({'action':'stop'});assert wait(manager)['state']=='success'
    assert not manager.status()['running']

def test_no_secrets_in_persisted_state_or_logs(manager):
    assert install(manager)['state']=='success'
    text='\n'.join(p.read_text(errors='replace') for p in manager.paths.state.rglob('*') if p.is_file())
    assert 'test-secret-123' not in text
    assert 'fixture echo [REDACTED]' in text
    assert 'password' not in json.dumps(manager.jobs)

def test_wrong_login_is_not_install_success(manager):
    result=install(manager,'wrong')
    assert result['state']=='failed'
    assert manager.status()['maintenance_block']
    with pytest.raises(Fault):manager.submit({'action':'start'})
    assert manager.config['steam_username'] != 'tester'

def test_successful_login_remembers_only_account(manager):
    manager.submit({'action':'login','username':'tester','password':'test-secret-123'})
    assert wait(manager)['authenticated_at']
    assert manager.config['steam_username'] == 'tester'
    saved = manager.paths.config.read_text()
    assert 'test-secret-123' not in saved
    assert json.loads(saved)['steam_username'] == 'tester'

def test_twofactor_input(manager):
    j=manager.submit({'action':'install','username':'tester','password':'needs_guard'})
    end=time.monotonic()+12
    while (not manager.active or manager.active.get('waiting_for')!='guard') and time.monotonic()<end:time.sleep(.05)
    assert manager.active['waiting_for']=='guard'
    with pytest.raises(Fault):manager.provide_input({'job_id':'wrong','value':'ABCDE'})
    manager.provide_input({'job_id':j['id'],'value':'ABCDE'})
    assert wait(manager)['state']=='success'
    assert 'ABCDE' not in manager.dispatch({'op':'logs','data':{'name':j['id']}})['text']

def test_preprovided_guard(manager):
    manager.submit({'action':'login','username':'tester','password':'needs_guard','guard':'ABCDE'})
    assert wait(manager)['state']=='success'
    assert not manager.status()['maintenance_block']

def test_update_running_server_requires_permission(manager):
    assert install(manager)['state']=='success'
    manager.submit({'action':'start'});wait(manager)
    with pytest.raises(Fault):manager.submit({'action':'update','username':'tester','password':'x'})
    manager.submit({'action':'update','username':'tester','password':'x','stop_server':True,'restart_after':True})
    assert wait(manager)['state']=='success'
    assert manager.status()['running']

def test_cancellation_and_lock(manager):
    (manager.paths.state.parent/'fixtures/behavior').write_text('slow')
    j=manager.submit({'action':'install','username':'tester','password':'secret-cancel'})
    with pytest.raises(Fault):manager.submit({'action':'backup'})
    with pytest.raises(Fault):manager.save_config(DEFAULT_CONFIG)
    end=time.monotonic()+12
    while manager.active and manager.active['stage'] not in {'validating','updating'} and time.monotonic()<end:time.sleep(.05)
    manager.dispatch({'op':'cancel','data':{'job_id':j['id']}})
    assert wait(manager)['state']=='cancelled'
    assert manager.status()['maintenance_block']
    with pytest.raises(Fault):manager.submit({'action':'start'})

def test_upstream_error_keeps_maintenance_block(manager):
    (manager.paths.state.parent/'fixtures/behavior').write_text('error')
    result=install(manager)
    assert result['state']=='failed'
    assert manager.status()['maintenance_block']

def test_backup_restore_and_traversal(manager):
    manager.submit({'action':'backup'});b=wait(manager)['backup']
    manager.save_config(DEFAULT_CONFIG | {'hostname':'Changed'})
    manager.submit({'action':'restore','backup':b});assert wait(manager)['state']=='success'
    assert manager.config['hostname']=='Dota 2 LAN'
    with pytest.raises(Fault):manager.dispatch({'op':'backup_read','data':{'name':'../../etc/passwd'}})
    with pytest.raises(Fault):manager.dispatch({'op':'logs','data':{'name':'../../etc/passwd'}})

def test_unknown_actions_and_config_rejected(manager):
    with pytest.raises(Fault):manager.submit({'action':'shell'})
    with pytest.raises(Fault):manager.dispatch({'op':'console','data':{'command':'exec /etc/passwd'}})
    with pytest.raises(Fault):manager.save_config({'shell':'bash -c evil'})
    with pytest.raises(Fault):manager.submit({'action':'update','username':'tester','stop_server':'yes'})

def test_mark_interrupted_jobs_after_restart(paths):
    atomic_json(paths.state/'jobs.json',[{'id':'x','state':'running','waiting_for':'password'}])
    m=Manager(paths)
    assert m.jobs[0]['state']=='interrupted'
    assert m.jobs[0]['waiting_for'] is None
    m.close()

def test_diagnostics_does_not_export_game_password(manager):
    (manager.paths.game/'game').mkdir()
    (manager.paths.game/'game/dota.sh').write_text('#!/bin/bash\n')
    manager.save_config(DEFAULT_CONFIG | {'game_password':'game-secret'})
    assert 'game-secret' not in json.dumps(manager.diagnostics())


def test_fixed_tiandixing_policy_rejects_bot_management_and_other_selection(manager):
    policy={'item_id':'1573671599','version':'a'*64}
    atomic_json(manager.paths.state/'bot-library/fixed-policy.json',policy)
    for action in ('bot_download','bot_check','bot_select','bot_default','bot_rollback','bot_remove'):
        with pytest.raises(Fault,match='固定使用天地星'):
            manager.submit({'action':action})
    with pytest.raises(Fault,match='固定版本'):
        manager._start_game()
