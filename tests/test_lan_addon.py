"""Offline source/transaction tests. Synthetic binary fixtures are NOT UI builds."""
import json
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path
import pytest
from panel.addon_assets import (COMPILED_FILES, CLIENT_REVISION, MARKER, source_identity,
    compiled_status,tree_inventory,validate_resource)
from panel.addon_runtime import AddonTelemetry
from panel.lan_addon import LanAddon,validate_addon,lua_value
from panel.bot_audit import mask_lua,audit_scripts,instrument_scripts,probe_header
from panel.bot_files import inventory
from panel.bots import BotLibrary
from panel.common import Fault,DEFAULT_CONFIG,atomic_json,build_command,read_json
from tools.addon_assets import stage,collect,import_assets,client_export
from tools.run_lua_tests import run_lua
ROOT=Path(__file__).resolve().parents[1]
SESSION='a'*32

@pytest.fixture
def source(tmp_path):
    p=tmp_path/'addon';shutil.copytree(ROOT/'addon/lan_dota',p);return p

def synthetic_resource():
    # Header structure only, NOT a Valve-compiled Panorama resource.
    return struct.pack('<IHHII4sII',32,12,0,8,1,b'DATA',8,4)+b'TEST'

def fake_compiled(source):
    out=source/'compiled';out.mkdir(exist_ok=True)
    files={}
    for name in COMPILED_FILES:
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(synthetic_resource())
    files=tree_inventory(out)
    atomic_json(out/'asset_manifest.json',{'schema':1,'client_revision':CLIENT_REVISION,
      'ui_source_sha256':source_identity(source)['ui_source_sha256'],'files':files})

@pytest.fixture
def bot(paths,tmp_path):
    library=BotLibrary(paths)
    raw=tmp_path/'bot_fixture';raw.mkdir()
    (raw/'hero_selection.lua').write_text('function Think() local b=GetBot() end\n')
    (raw/'bot_generic.lua').write_text('function Think() return GetBot() end\n')
    metadata={'item_id':'1627071163','title':'TEST NOT DOWNLOADED'}
    info=library.install(raw,metadata)
    selection=library.select({'item_id':'1627071163','version':info['version']})
    return library,selection,raw

@pytest.mark.parametrize('raw',[[],{'unknown':1},{'enabled':1},{'probe_bots':'yes'},
 {'schema':True},{'launch_method':'dota;quit'},{'launch_method':None}])
def test_addon_config_rejects(raw):
    with pytest.raises(Fault):validate_addon(raw)

def test_config_partial_defaults():
    assert validate_addon({'enabled':True})['launch_method']=='custom_command'
    assert validate_addon({})['enabled'] is False

def test_missing_compiled_stops_before_bot_mutation(paths,source,bot):
    lan=LanAddon(paths,source);lan.save({'enabled':True,'probe_bots':True})
    assert not compiled_status(source)['ready']
    with pytest.raises(Fault):lan.prepare(bot[0])
    assert not bot[0].deployment_path.exists()

@pytest.mark.parametrize('bad',[b'<root>'+b'x'*40,b'console.log("x")'+b'x'*40,
 struct.pack('<IHHII',32,12,0,8,800)+b'0'*16,b''])
def test_compiled_rejects_renamed_sources_and_bad_header(bad):
    with pytest.raises(Fault):validate_resource(bad)

def test_compiled_manifest_tied_to_source(source):
    fake_compiled(source);assert compiled_status(source)['ready']
    (source/'content/panorama/scripts/custom_game/lan_setup.js').write_text('changed')
    assert not compiled_status(source)['ready']

def test_compile_header_blocks_reject_overflow():
    b=bytearray(synthetic_resource());struct.pack_into('<I',b,20,999)
    with pytest.raises(Fault):validate_resource(bytes(b))

def test_deploy_unknown_target_preserved(paths,source):
    lan=LanAddon(paths,source);lan.target.mkdir(parents=True)
    f=lan.target/'my.lua';f.write_text('user')
    with pytest.raises(Fault):lan.deploy()
    assert f.read_text()=='user'

def test_deploy_and_reject_external_edit(paths,source):
    lan=LanAddon(paths,source);first=lan.deploy();assert first['compiled_ui'] is False
    assert lan.status()['deployment']['source_sha256']==source_identity(source)['source_sha256']
    generated=lan.target/'scripts/vscripts/lan/generated.lua';generated.write_text('-- user edit')
    with pytest.raises(Fault):lan.deploy()
    assert generated.read_text()=='-- user edit'

def test_transaction_recovers_old_on_crash(paths,source,monkeypatch):
    import panel.lan_addon as module
    lan=LanAddon(paths,source);first=lan.deploy();real=module.os.replace
    def crash(a,b):
        if str(a).split('/')[-1].startswith('.lan-dota-new-'):raise OSError('crash fixture')
        return real(a,b)
    monkeypatch.setattr(module.os,'replace',crash)
    with pytest.raises(OSError):lan.deploy()
    assert lan.journal.exists()
    monkeypatch.setattr(module.os,'replace',real)
    lan.recover()
    assert read_json(lan.target/MARKER)['transaction']==first['transaction']
    assert not lan.journal.exists()

def test_bad_journal_not_deleted(paths,source):
    lan=LanAddon(paths,source);atomic_json(lan.journal,{'transaction':'../bad'})
    with pytest.raises(Fault):lan.recover()
    assert lan.journal.exists()

def test_probe_launch_pins_library_and_instruments_copy(paths,source,bot):
    fake_compiled(source);library,selection,raw=bot;lan=LanAddon(paths,source)
    lan.save({'enabled':True,'probe_bots':True})
    spec,runtime=lan.prepare(library)
    assert runtime['bot']['version']==selection['version']
    assert 'LANLAB|' in (library.target/'bot_generic.lua').read_text()
    assert 'LANLAB|' not in (library._version_path(selection['item_id'],selection['version'])/'scripts/bot_generic.lua').read_text()
    assert inventory(library.target)[0]==read_json(library.deployment_path)['deployed_sha256']
    before=runtime['session'];again,new=lan.prepare(library,override=spec,reuse=True,prior=runtime)
    assert new['session']!=before and again['version']==spec['version']
    (source/'game/addoninfo.txt').write_text('changed source')
    with pytest.raises(Fault):lan.prepare(library,override=again,reuse=True,prior=new)

def test_addon_without_ai_restores_managed_bot_and_no_bot_available(paths,source,bot):
    fake_compiled(source);library,selection,_=bot;library.prepare_launch()
    lan=LanAddon(paths,source);lan.save({'enabled':True,'probe_bots':False})
    spec,runtime=lan.prepare(library)
    assert spec is None and runtime['bot'] is None
    assert 'false' in (lan.target/'scripts/vscripts/lan/generated.lua').read_text()

def test_static_audit_and_lexer_no_false_string_calls(tmp_path):
    t='-- GetBot()\nlocal s="DotaTime()"\nlocal l=[=[ GetTeam() ]=]\nGetBot()\n'
    masked=mask_lua(t);assert len(masked)==len(t)
    assert masked.count('GetBot')==1 and 'DotaTime' not in masked and 'GetTeam' not in masked
    root=tmp_path/'scripts';root.mkdir()
    (root/'bot_generic.lua').write_text(t+'function Think() GetBot() end\nrequire(GetScriptDirectory().."/lib")')
    sha=inventory(root)[0];report=audit_scripts(root,{'version':sha})
    assert report['bot_globals']==['GetBot','GetScriptDirectory']
    assert not report['runtime_verified'] and report['unresolved']

def test_instrument_callback_return_and_errors_preserved(tmp_path):
    p=tmp_path/'bot_generic.lua'
    p.write_text('local text="function Think()"\nfunction Think() return 17 end\nreturn {run=Think}\n')
    before=p.read_text();spec={};instrument_scripts(tmp_path,spec,SESSION,{'bot_globals':[]})
    text=p.read_text();assert text.count('__lanlab_probe_130("Think")')==1
    assert 'local text="function Think()"' in text
    run_lua('GetBot=function()return {}end;GetScriptDirectory=function()return "bots"end\nlocal f=function()\n'+text+'\nend\nassert(f().run()==17)')
    p.write_text('function Think() error("ORIGINAL_ERROR") end\nreturn {run=Think}')
    instrument_scripts(tmp_path,{},SESSION,{'bot_globals':[]})
    with pytest.raises(AssertionError,match='ORIGINAL_ERROR'):
        run_lua('local f=function()\n'+p.read_text()+'\nend\nf().run()')

def test_no_arbitrary_probe_entry():
    with pytest.raises(Fault):probe_header(SESSION,'evil".lua',[])
    with pytest.raises(Fault):probe_header('x','bot_generic.lua',[])

@pytest.mark.parametrize('method',['custom_command','addon_flag'])
def test_addon_command_exclusive(paths,method):
    (paths.game/'dota.sh').write_text('#!/bin/sh\n')
    cmd,env=build_command(paths,DEFAULT_CONFIG,{'difficulty':2},{'name':'lan_dota','launch_method':method})
    assert '+dota_force_gamemode' not in cmd and '+dota_wait_for_players_to_load_timeout' not in cmd
    assert cmd.count('+map')==(0 if method=='custom_command' else 1)
    assert cmd[-3:]==(['+dota_launch_custom_game','lan_dota','dota'] if method=='custom_command' else ['lan_dota','+map','dota'])
    assert cmd[cmd.index('+sv_cheats')+1]=='0'

def test_telemetry_current_token_split_and_stale():
    clock=[0];t=AddonTelemetry(SESSION,lambda:clock[0])
    payload=json.dumps({'phase':'setup','players':[]})
    t.feed('LANLAB|'+'b'*32+'|STATE|'+payload+'\n');assert not t.snapshot(True)['fresh']
    line='LANLAB|'+SESSION+'|STATE|'+payload+'\n'
    t.feed(line[:19]);t.feed(line[19:]);assert t.snapshot(True)['fresh']
    clock[0]=16;assert not t.snapshot(True)['fresh']
    t.feed('LANLAB|'+SESSION+'|BOT_ENTRY|bot_generic.lua:loaded\n')
    t.feed('LANLAB|'+SESSION+'|BOT_CALLBACK|bot_generic.lua:Think:64\n')
    t.feed('LANLAB|'+SESSION+'|BOT_API|bot_generic.lua:GetBot,GetTeam\n')
    s=t.snapshot(False);assert not s['full_ai_verified'] and not s['fresh']
    assert s['bot_callbacks']['bot_generic.lua:Think']==64 and s['bot_missing_apis']['bot_generic.lua']==['GetBot','GetTeam']

def test_telemetry_invalid_and_bounded():
    t=AddonTelemetry(SESSION)
    t.feed('LANLAB|'+SESSION+'|STATE|{"phase":"fake","players":[]}\n')
    assert t.snapshot(True)['state'] is None
    for i in range(700):t.feed('LANLAB|'+SESSION+'|BOT_ENTRY|entry'+str(i)+':loaded\n')
    assert len(t.entries)<=500 and len(t.events)==100
    t.feed('S2C_CONNREJECT 129 #GameUI_ServerNoLobby\n')
    assert 'ServerNoLobby' in t.snapshot(True)['connection_rejections']

def test_offline_tools_roundtrip(source,tmp_path):
    dota=tmp_path/'tools';(dota/'game').mkdir(parents=True);(dota/'content').mkdir()
    assert stage(source,dota)['dry_run']
    assert not (dota/'game/dota_addons/lan_dota').exists()
    stage(source,dota,True)
    for name in COMPILED_FILES:
        p=dota/'game/dota_addons/lan_dota'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(synthetic_resource())
    archive=tmp_path/'assets.zip';collect(source,dota,archive)
    assert import_assets(source,archive)['dry_run'] and not (source/'compiled').exists()
    import_assets(source,archive,True);assert compiled_status(source)['ready']
    client=tmp_path/'client.zip';client_export(source,client)
    with zipfile.ZipFile(client) as z:
        assert 'LANLAB_CLIENT.json' in z.namelist()
        assert all('bots/' not in n for n in z.namelist())
        assert b'"session":"' not in z.read('LANLAB_CLIENT.json')
    with pytest.raises(Fault):client_export(source,client)

def test_asset_import_zip_traversal_refused(source,tmp_path):
    z=tmp_path/'evil.zip'
    with zipfile.ZipFile(z,'w') as a:a.writestr('../outside','evil')
    with pytest.raises(Fault):import_assets(source,z,True)
    assert not (tmp_path/'outside').exists()

def test_stage_no_overwrite_user_edits(source,tmp_path):
    dota=tmp_path/'tools';(dota/'game').mkdir(parents=True);(dota/'content').mkdir()
    stage(source,dota,True)
    target=dota/'content/dota_addons/lan_dota/panorama/scripts/custom_game/lan_setup.js'
    target.write_text('my edits')
    with pytest.raises(Fault):stage(source,dota,True,True)
    assert target.read_text()=='my edits'

@pytest.mark.parametrize('spec',['room_spec.lua','identity_spec.lua','engine_spec.lua'])
def test_lua_mock_suite(spec):
    result=subprocess.run([sys.executable,str(ROOT/'tools/run_lua_tests.py'),str(ROOT/'tests/lua'/spec)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr

def test_lua_config_escape():
    text=lua_value({'a':'"\\\n中文','b':True,'c':[1,'x']})
    run_lua('local x='+text+'\nassert(x.b and x.c[1]==1 and #x.a>3)')


def test_panorama_xml_js_contract_and_mock_events():
    import xml.etree.ElementTree as ET
    base=ROOT/'addon/lan_dota/content/panorama'
    for f in base.rglob('*.xml'): ET.parse(f)
    result=subprocess.run(['node',str(ROOT/'tests/js/panorama_mock.js'),str(base)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+result.stderr


def test_known_vscript_log_prefix_supported():
    t=AddonTelemetry(SESSION)
    t.feed('[VScript] LANLAB|'+SESSION+'|BOT_ENTRY|bot_generic.lua:loaded\n')
    assert t.snapshot(True)['bot_entries']==['bot_generic.lua']


def test_counter_too_long_does_not_kill_log_reader():
    t=AddonTelemetry(SESSION)
    t.feed('LANLAB|'+SESSION+'|BOT_CALLBACK|bot_generic.lua:Think:'+('9'*6000)+'\n')
    assert not t.callbacks
    t.feed('LANLAB|'+SESSION+'|BOT_CALLBACK|bot_generic.lua:Think:64\n')
    assert t.callbacks['bot_generic.lua:Think']==64


def test_nettable_registration_uses_kv3_array():
    # Narrow structural regression check, not a replacement for the engine parser.
    import re
    text=(ROOT/'addon/lan_dota/game/scripts/custom_net_tables.txt').read_text()
    assert text.startswith('<!-- kv3 encoding:text:version{')
    body=re.sub(r'<!--.*?-->', '', text, flags=re.S).strip()
    assert re.fullmatch(r'\{\s*custom_net_tables\s*=\s*\[\s*"lan_room"\s*\]\s*\}',body)
