import importlib.util
import json
from pathlib import Path
import pytest
from panel.common import DEFAULT_CONFIG, Fault, atomic_json, build_command, read_json, validate_config, credentials
from panel.logs import SafeLog

@pytest.mark.parametrize('bad',[
 {'port':True},{'port':0},{'port':70000},{'hostname':'hello; quit'}, {'hostname':'-exec'},
 {'map':'../../etc/passwd'},{'map':'dota;quit'},{'cheats':1},{'game_mode':99},
 {'steam_username':'bob\nquit'},{'game_password':'x" +exec foo'},{'exec':'/bin/sh'}, {'schema':True},
 {'hostname':'line\nbreak'}, {'hostname':'back\\slash'}, {'auto_start':'false'}])
def test_reject_unsafe_config(bad):
    with pytest.raises(Fault): validate_config(DEFAULT_CONFIG | bad)

def test_roundtrip(paths):
    c=validate_config(DEFAULT_CONFIG | {'hostname':'局域网测试服'})
    atomic_json(paths.config,c)
    assert read_json(paths.config)==c
    assert paths.config.stat().st_mode & 0o777 == 0o600

def test_missing_executable(paths):
    with pytest.raises(Fault): build_command(paths,DEFAULT_CONFIG)

def test_launch_argv_no_shell_injection(paths):
    (paths.game/'game').mkdir()
    (paths.game/'game/dota.sh').write_text('#!/bin/bash\n')
    cmd,env=build_command(paths,DEFAULT_CONFIG | {'hostname':'Dota 2 test'})
    assert cmd[:2]==['/bin/bash',str(paths.game/'game/dota.sh')]
    assert 'Dota 2 test' in cmd
    assert cmd[cmd.index('+sv_lan')+1]=='1'
    assert '-insecure' not in cmd
    assert env['HOME']==str(paths.state)
    assert '-c' not in cmd


def test_launch_prefers_current_linuxsteamrt64_binary(paths):
    wrapper = paths.game/'game/dota.sh'
    binary = paths.game/'game/bin/linuxsteamrt64/dota2'
    binary.parent.mkdir(parents=True)
    wrapper.write_text('#!/bin/bash\nexit 1\n')
    binary.write_text('#!/bin/bash\nexit 0\n')
    binary.chmod(0o755)
    cmd,_ = build_command(paths,DEFAULT_CONFIG)
    assert cmd[0] == str(binary)
    assert str(wrapper) not in cmd

def test_secret_credentials_are_not_shell_arguments():
    c=credentials({'username':'tester','password':'a; $(not-a-shell) " password','guard':'ABCDE'})
    assert c['password'].startswith('a;')
    with pytest.raises(Fault): credentials({'username':'abc','password':'bad\ncommand'})

def test_redaction_across_chunks(tmp_path):
    p=tmp_path/'test.log';s=SafeLog(p,['secret123','ABCDE'])
    s.write('echo sec');s.write('ret123 and ABC');s.write('DE\n')
    s.finish();text=p.read_text()
    assert 'secret123' not in text and 'ABCDE' not in text
    assert text.count('[REDACTED]')==2

def test_log_rotation(tmp_path):
    p=tmp_path/'test.log';s=SafeLog(p,max_bytes=10)
    s.event('first long line');s.event('second long line')
    assert p.with_suffix('.log.1').exists()

def renderer():
    p=Path(__file__).parents[1]/'install/render.py'
    spec=importlib.util.spec_from_file_location('render',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def test_render_firewall_and_nginx():
    m=renderer();c=m.validate(json.loads((Path(__file__).parents[1]/'install/bootstrap.example.json').read_text()))
    fw=m.firewall(c);ng=m.nginx(c)
    assert 'policy_in: DROP' in fw and '-p udp -dport 27015' in fw
    assert '-source 192.168.1.0/24' in fw and 'listen 8443;' in ng
    assert 'deny all;' in ng and 'ssl' not in ng and 'listen 80' not in ng
    assert 'proxy_pass http://127.0.0.1:8765;' in ng

def test_render_rejects_config_injection():
    m=renderer();base=json.loads((Path(__file__).parents[1]/'install/bootstrap.example.json').read_text())
    for patch in [{'hostname':'evil;}'},{'lan_cidrs':['0.0.0.0/0']},{'panel_port':True},{'timezone':'../../etc'}]:
        with pytest.raises((ValueError,AssertionError)):m.validate(base|patch)
