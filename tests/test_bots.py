"""Offline fixtures: no actual Workshop download or Dota compatibility claim."""
import io
import json
import os
import shutil
import stat
import struct
import threading
import time
import zipfile
import zlib
from pathlib import Path

import pytest

from panel.agent import Manager
from panel.bot_files import Writer, inventory, safe_name, stage_content, unpack_vpk, unpack_zip
from panel.bots import BotLibrary, locate_download, lookup_item, validate_metadata, version_id, workshop_id
from panel.common import DEFAULT_CONFIG, Fault, atomic_json, build_command, read_json
from panel.steam import Cancelled

ID = '1627071163'


def raw_metadata(item=ID):
    return {'publishedfileid': item, 'result': 1, 'consumer_app_id': 570, 'file_type': 0,
            'title': '天地星AI · 测试元数据（非实际下载）', 'tags': [{'tag': 'Bot Scripts'}],
            'file_size': '512', 'time_updated': 1700000000, 'banned': False}


def metadata(item=ID):
    return validate_metadata(item, raw_metadata(item))


def content(tmp, name='fixture', text='-- version one\n'):
    root = tmp / name
    root.mkdir()
    (root / 'hero_selection.lua').write_text(text + 'function Think() end\n')
    (root / 'bot_generic.lua').write_text('function Think() end\n')
    (root / 'lib').mkdir()
    (root / 'lib/data.json').write_text('{"fixture":true}')
    return root


def wait(m, timeout=25):
    end = time.monotonic() + timeout
    while m.active and time.monotonic() < end:
        time.sleep(.03)
    assert m.active is None, 'job did not finish'
    return m.jobs[-1]


@pytest.fixture
def manager(paths):
    m = Manager(paths, workshop_lookup=metadata)
    yield m
    m.close()


@pytest.mark.parametrize('value', ['', '0', '-1', '1;quit', '1\nquit', '../1', '123/45',
                                  'https://steamcommunity.com/sharedfiles/filedetails/?id=1',
                                  '18446744073709551616', 1627071163, True, None])
def test_id_validation(value):
    with pytest.raises(Fault):
        workshop_id(value)


def test_id_is_string_and_uint64():
    assert workshop_id(' 1627071163 ') == ID
    assert workshop_id('18446744073709551615') == '18446744073709551615'
    assert version_id('a'*64) == 'a'*64
    with pytest.raises(Fault): version_id('../x')


@pytest.mark.parametrize('patch', [{'result': 9}, {'consumer_app_id': 730}, {'file_type': 2},
                                  {'banned': True}, {'tags': [{'tag': 'Custom Game'}]},
                                  {'file_size': str(300*1024**2)}, {'publishedfileid': '9'}])
def test_reject_ineligible_metadata(patch):
    with pytest.raises(Fault): validate_metadata(ID, raw_metadata() | patch)


def test_metadata_strips_control_not_markup():
    m = validate_metadata(ID, raw_metadata() | {'title': '<img src=x onerror=1>\n'})
    assert '\n' not in m['title']
    # It is plain data. The browser renders title with textContent, never innerHTML.
    assert m['title'].startswith('<img')


def test_official_metadata_endpoint_body_and_no_redirect(monkeypatch):
    seen = {}
    class Response(io.BytesIO):
        pass
    class Opener:
        def open(self, request, timeout):
            seen.update(url=request.full_url, body=request.data, timeout=timeout)
            return Response(json.dumps({'response': {'publishedfiledetails': [raw_metadata()]}}).encode())
    monkeypatch.setattr('urllib.request.build_opener', lambda *args: Opener())
    assert lookup_item(ID)['item_id'] == ID
    assert seen['url'].startswith('https://api.steampowered.com/ISteamRemoteStorage/')
    assert b'publishedfileids%5B0%5D=1627071163' in seen['body']
    assert b'password' not in seen['body']
    from panel.bots import NoRedirect
    with pytest.raises(Fault): NoRedirect().redirect_request(None,None,302,'',{},'http://127.0.0.1')


@pytest.mark.parametrize('name', ['../a.lua', '/a.lua', 'a/../b.lua', 'C:/a.lua', 'a\\b.lua',
                                 'a//b.lua', 'a/./b.lua', '.dota-panel-bot.json', 'a\x00.lua'])
def test_package_paths(name):
    with pytest.raises(Fault): safe_name(name)


def test_loose_stage_preserves_dependencies(tmp_path):
    source = content(tmp_path)
    work = tmp_path / 'work'; work.mkdir()
    info = stage_content(source, work)
    assert len(info['files']) == 3
    assert info['version'] == inventory(work / 'scripts')[0]
    assert (work/'scripts/lib/data.json').is_file()
    assert not (work/'scripts/fixture/hero_selection.lua').exists()


def test_nested_root_and_skip_native_binary(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    folder = content(source, 'bots')
    (folder/'installer.sh').write_text('do not execute')
    (folder/'x.dll').write_bytes(b'not a library')
    work = tmp_path / 'work';work.mkdir()
    info=stage_content(source,work)
    assert info['skipped_count'] == 2
    assert not (work/'scripts/x.dll').exists()


def test_ambiguous_roots_and_symlinks_fail(tmp_path):
    root = tmp_path/'root';root.mkdir()
    content(root,'a');content(root,'b')
    work=tmp_path/'work';work.mkdir()
    with pytest.raises(Fault): stage_content(root,work)
    source=content(tmp_path,'single')
    (source/'link.lua').symlink_to('/etc/passwd')
    with pytest.raises(Fault): stage_content(source,work)


def test_zip_nested_package(tmp_path):
    source=tmp_path/'source';source.mkdir()
    with zipfile.ZipFile(source/'bot.zip','w') as z:
        z.writestr('repo/bots/hero_selection.lua','function Think() end')
        z.writestr('repo/bots/lib/helper.lua','return {}')
    work=tmp_path/'work';work.mkdir()
    info=stage_content(source,work)
    assert info['source_format']=='zip'
    assert (work/'scripts/lib/helper.lua').exists()


@pytest.mark.parametrize('kind', ['traversal','symlink','duplicate','case_collision','too_large'])
def test_bad_zip(tmp_path, kind, monkeypatch):
    file=tmp_path/'bad.zip'
    with zipfile.ZipFile(file,'w') as z:
        if kind=='traversal': z.writestr('../bad.lua','evil')
        elif kind=='symlink':
            info=zipfile.ZipInfo('a.lua');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(info,'/etc/passwd')
        elif kind in {'duplicate','case_collision'}:
            z.writestr('a.lua','a');z.writestr('a.lua' if kind=='duplicate' else 'A.lua','b')
        else:
            monkeypatch.setattr('panel.bot_files.MAX_FILE_BYTES',4)
            z.writestr('a.lua','a'*10)
    with pytest.raises(Fault): unpack_zip(file,Writer(tmp_path/'out',lambda:None))
    assert not (tmp_path/'bad.lua').exists()


def make_vpk(path, version=1, folder=' ', crc_bad=False, split=False, bad_offset=False):
    payload=b'-- TEST VPK\nfunction Think() end\n';preload=payload[:5];data=payload[5:]
    entry=struct.pack('<IHHIIH', 0 if crc_bad else zlib.crc32(payload),len(preload),0 if split else 0x7fff,
                      100000 if bad_offset else 0,len(data),0xffff)
    tree=b'lua\0'+folder.encode()+b'\0hero_selection\0'+entry+preload+b'\0\0\0'
    header=struct.pack('<III',0x55aa1234,version,len(tree))
    if version==2:header+=struct.pack('<IIII',0 if split else len(data),0,0,0)
    path.write_bytes(header+tree+(b'' if split else data))
    if split:path.with_name(path.name[:-8]+'_000.vpk').write_bytes(data)


@pytest.mark.parametrize('version,split',[(1,False),(2,False),(1,True),(2,True)])
def test_vpk_crc_preload_and_split(tmp_path,version,split):
    source=tmp_path/'source';source.mkdir()
    make_vpk(source/'bot_dir.vpk',version=version,split=split)
    work=tmp_path/'work';work.mkdir()
    info=stage_content(source,work)
    assert info['source_format']=='vpk'
    assert (work/'scripts/hero_selection.lua').read_text().startswith('-- TEST VPK')


@pytest.mark.parametrize('patch',[{'crc_bad':True},{'folder':'../bad'},{'bad_offset':True}])
def test_bad_vpk(tmp_path,patch):
    file=tmp_path/'bot_dir.vpk';make_vpk(file,**patch)
    with pytest.raises(Fault):unpack_vpk(file,Writer(tmp_path/'out',lambda:None))


def test_cancel_during_extract(tmp_path):
    source=content(tmp_path);work=tmp_path/'work';work.mkdir()
    def cancel():raise Cancelled()
    with pytest.raises(Cancelled):stage_content(source,work,cancel)


def test_cache_resolver_does_not_accept_external_path(paths,tmp_path):
    target=paths.steam/'steamapps/workshop/content/570'/ID;target.mkdir(parents=True)
    line=f'Success. Downloaded item {ID} to "{target}" (12 bytes)'
    assert locate_download(paths,ID,line)==target
    with pytest.raises(Fault): locate_download(paths,ID,f'Success. Downloaded item {ID} to "/etc" (12 bytes)')
    other=paths.game/'steamapps/workshop/content/570'/ID;other.mkdir(parents=True)
    with pytest.raises(Fault):locate_download(paths,ID,'Success. Downloaded item '+ID)
    assert locate_download(paths,ID,line)==target


def test_versions_pinned_and_original_restored(paths,tmp_path):
    lib=BotLibrary(paths);lib.parent.mkdir(parents=True)
    lib.target.mkdir();(lib.target/'original.lua').write_text('-- original user file')
    info=lib.install(content(tmp_path),metadata())
    assert not lib.list()['selected']
    lib.select({'item_id':ID,'version':info['version']})
    spec=lib.prepare_launch()
    assert spec['version']==info['version']
    assert spec['probe_token'] in (lib.target/'hero_selection.lua').read_text()
    original=lib.root/'items'/ID/'versions'/info['version']/'scripts/hero_selection.lua'
    assert 'DOTA_PANEL_BOT_ENTRY' not in original.read_text()
    assert not lib.journal.exists()
    lib.select({'item_id':None});assert lib.prepare_launch() is None
    assert (lib.target/'original.lua').read_text()=='-- original user file'
    assert not (lib.target/'hero_selection.lua').exists()
    assert not (lib.target/'.dota-panel-bot.json').exists()
    assert lib.prepare_launch() is None


def test_disable_with_no_original_and_reenable(paths,tmp_path):
    lib=BotLibrary(paths)
    info=lib.install(content(tmp_path),metadata());lib.select({'item_id':ID,'entry_probe':False})
    spec=lib.prepare_launch();assert spec['probe_token'] is None
    lib.select({'item_id':None});lib.prepare_launch();assert not lib.target.exists()
    lib.rollback_selection();assert lib.prepare_launch()['version']==info['version']


def test_immutable_versions_and_selection_rollback(paths,tmp_path):
    lib=BotLibrary(paths)
    a=lib.install(content(tmp_path,'a','-- a\n'),metadata());lib.select({'item_id':ID})
    b=lib.install(content(tmp_path,'b','-- b\n'),metadata());assert a['version']!=b['version']
    assert lib.list()['selected']['version']==a['version']
    lib.select({'item_id':ID});assert lib.list()['selected']['version']==b['version']
    assert lib.rollback_selection()['version']==a['version']
    with pytest.raises(Fault):lib.remove({'item_id':ID,'version':b['version']},None)


def test_corrupted_library_blocks_launch(paths,tmp_path):
    lib=BotLibrary(paths);a=lib.install(content(tmp_path),metadata());lib.select({'item_id':ID})
    root=lib._version_path(ID,a['version'])/'scripts'
    (root/'hero_selection.lua').write_text('-- modified')
    with pytest.raises(Fault,match='改变或损坏'):lib.prepare_launch()
    assert not lib.target.exists()


def test_external_edit_not_overwritten(paths,tmp_path):
    lib=BotLibrary(paths);lib.install(content(tmp_path),metadata());lib.select({'item_id':ID});lib.prepare_launch()
    (lib.target/'hero_selection.lua').write_text('-- precious user edit')
    with pytest.raises(Fault,match='手工修改'):lib.prepare_launch()
    assert (lib.target/'hero_selection.lua').read_text()=='-- precious user edit'


def test_atomic_deploy_rollback_on_injected_rename_failure(paths,tmp_path,monkeypatch):
    lib=BotLibrary(paths);lib.install(content(tmp_path),metadata());lib.select({'item_id':ID})
    lib.parent.mkdir(parents=True);lib.target.mkdir();(lib.target/'mine.lua').write_text('-- original')
    original=os.replace
    def fail_once(src,dst):
        if Path(src).name.startswith('.dota-panel-bots-new-'):raise OSError('test interrupted rename')
        return original(src,dst)
    monkeypatch.setattr(os,'replace',fail_once)
    with pytest.raises(OSError):lib.prepare_launch()
    assert lib.journal.exists()
    monkeypatch.setattr(os,'replace',original)
    lib.recover()
    assert not lib.journal.exists()
    assert (lib.target/'mine.lua').read_text()=='-- original'
    assert lib.prepare_launch()['item_id']==ID


def test_workshop_download_task_end_to_end_fake(manager):
    manager.submit({'action':'bot_download','item_id':ID,'username':'tester','password':'bot-secret','select_after':True})
    j=wait(manager);assert j['state']=='success',j
    assert manager.bots.list()['selected']['item_id']==ID
    assert not manager.bots.target.exists()  # install is not deploy
    assert not manager.status()['maintenance_block']
    text='\n'.join(p.read_text(errors='replace') for p in manager.paths.state.rglob('*') if p.is_file())
    assert 'bot-secret' not in text
    assert ID in manager.dispatch({'op':'logs','data':{'name':j['id']}})['text']


@pytest.mark.parametrize('behavior',['error','missing','wrong_id','no_success'])
def test_download_failure_not_success(manager,behavior):
    (manager.paths.state.parent/'fixtures/workshop_behavior').write_text(behavior)
    manager.submit({'action':'bot_download','item_id':ID,'username':'tester','password':'pass'})
    j=wait(manager);assert j['state']=='failed',j
    assert not manager.bots.list()['selected']
    assert not manager.status()['maintenance_block']


def test_running_game_not_touched_and_auto_restart_pins_old_version(manager):
    manager.submit({'action':'install','username':'tester','password':'pass'});assert wait(manager)['state']=='success'
    manager.submit({'action':'bot_download','item_id':ID,'username':'tester','password':'pass','select_after':True});assert wait(manager)['state']=='success'
    manager.submit({'action':'start'});assert wait(manager)['state']=='success'
    old=manager.game.bot_spec['version'];pid=manager.game.child.pid
    deployed=(manager.bots.target/'hero_selection.lua').read_bytes()
    (manager.paths.state.parent/'fixtures/workshop_behavior').write_text('changed')
    manager.submit({'action':'bot_download','item_id':ID,'username':'tester','password':'pass','select_after':True});assert wait(manager)['state']=='success'
    assert manager.game.child.pid==pid
    assert manager.game.bot_spec['version']==old
    assert (manager.bots.target/'hero_selection.lua').read_bytes()==deployed
    assert manager.bots.list()['selected']['version']!=old
    manager.game.stop();manager._start_game(reuse_running=True)
    assert manager.game.bot_spec['version']==old
    manager.submit({'action':'restart'});assert wait(manager)['state']=='success'
    assert manager.game.bot_spec['version']!=old


def test_bot_download_guard_cancel_and_task_mutex(manager):
    j=manager.submit({'action':'bot_download','item_id':ID,'username':'tester','password':'needs_guard'})
    end=time.monotonic()+12
    while manager.active and manager.active.get('waiting_for')!='guard' and time.monotonic()<end:time.sleep(.05)
    assert manager.active is not None, manager.jobs[-1]  # Preserve early child-start failure diagnostics.
    assert manager.active['waiting_for']=='guard'
    with pytest.raises(Fault):manager.submit({'action':'start'})
    with pytest.raises(Fault):manager.save_config(DEFAULT_CONFIG)
    manager.provide_input({'job_id':j['id'],'value':'ABCDE'})
    assert wait(manager)['state']=='success'
    assert 'ABCDE' not in manager.dispatch({'op':'logs','data':{'name':j['id']}})['text']
    (manager.paths.state.parent/'fixtures/workshop_behavior').write_text('slow')
    j=manager.submit({'action':'bot_download','item_id':ID,'username':'tester','password':'pass'})
    end=time.monotonic()+12
    while manager.active and manager.active.get('stage')!='downloading_workshop' and time.monotonic()<end:time.sleep(.05)
    manager.dispatch({'op':'cancel','data':{'job_id':j['id']}})
    assert wait(manager)['state']=='cancelled'
    assert len(manager.bots.list()['items'][0]['versions'])==1


def test_bot_check_requires_no_steam_password(manager):
    manager.submit({'action':'bot_check','item_id':ID})
    j=wait(manager);assert j['state']=='success'
    assert j['workshop']['item_id']==ID
    assert not manager.bots.list()['items']


def test_launch_flags_and_order(paths):
    (paths.game/'game').mkdir();(paths.game/'game/dota.sh').write_text('#!/bin/bash\n')
    cmd,_=build_command(paths,DEFAULT_CONFIG,{'difficulty':3})
    assert '-allow_no_lobby_connect' in cmd
    assert cmd.index('+dota_bot_practice_script') < cmd.index('+map')
    assert cmd[cmd.index('+dota_bot_practice_script')+1]=='0'
    assert '+dota_bot_populate' not in cmd
    with pytest.raises(Fault):build_command(paths,DEFAULT_CONFIG,{'difficulty':'; evil'})


def test_metadata_file_type_optional_for_old_response():
    raw=raw_metadata();raw.pop('file_type')
    assert validate_metadata(ID,raw)['item_id']==ID


def test_entry_probe_is_runtime_output_not_install_claim(manager):
    manager.submit({'action':'install','username':'tester','password':'pass'});wait(manager)
    manager.submit({'action':'bot_download','item_id':ID,'username':'tester','password':'pass','select_after':True});wait(manager)
    assert manager.status()['bot_runtime']['acceptance']=='not_verified'
    manager.submit({'action':'start'});assert wait(manager)['state']=='success'
    assert not manager.game.bot_entry_seen
    token=manager.game.bot_spec['probe_token']
    manager.game.console({'command':'say','text':'DOTA_PANEL_BOT_ENTRY:'+token+':hero_selection'})
    time.sleep(.2);assert not manager.game.bot_entry_seen  # not an exact standalone log line
    with pytest.raises(Fault,match='Bot 控制功能已停用'):
        manager.game.console({'command':'bots'})
    # Drive the synthetic child directly; the product console no longer exposes population.
    manager.game.child.sendline('dota_bot_populate')
    end=time.monotonic()+3
    while not manager.game.bot_entry_seen and time.monotonic()<end:time.sleep(.03)
    assert manager.game.bot_entry_seen
    assert manager.status()['bot_runtime']['acceptance']=='entry_executed_not_full_ai_verified'


def test_interrupted_restore_marker_cleanup(paths,tmp_path):
    lib=BotLibrary(paths)
    lib.parent.mkdir(parents=True);lib.target.mkdir();(lib.target/'mine.lua').write_text('-- original')
    lib.install(content(tmp_path),metadata());lib.select({'item_id':ID});lib.prepare_launch()
    lib.select({'item_id':None});lib.prepare_launch()
    deployed=read_json(lib.deployment_path)
    atomic_json(lib.target/'.dota-panel-bot.json',{'transaction':deployed['transaction']})
    lib.recover()
    assert not (lib.target/'.dota-panel-bot.json').exists()
    assert lib.prepare_launch() is None


def test_symlink_version_root_rejected(paths,tmp_path):
    lib=BotLibrary(paths);info=lib.install(content(tmp_path),metadata())
    root=lib._version_path(ID,info['version']);scripts=root/'scripts'
    outside=tmp_path/'outside';shutil.move(scripts,outside);scripts.symlink_to(outside,target_is_directory=True)
    with pytest.raises(Fault):lib.select({'item_id':ID})


def test_no_steam_launch_after_metadata_failure(manager,monkeypatch):
    def deny(_):raise Fault('fixture metadata unavailable',502)
    manager.workshop_lookup=deny
    called=[]
    monkeypatch.setattr('panel.agent.SteamJob.run',lambda *a,**k:called.append(True))
    manager.submit({'action':'bot_download','item_id':ID,'username':'tester','password':'pass'})
    assert wait(manager)['state']=='failed'
    assert not called


@pytest.mark.parametrize('journal', [{}, [], {'old':'../outside'}, {'transaction':'x','had_target':False}])
def test_invalid_recovery_journal_preserves_original(paths, journal):
    lib=BotLibrary(paths)
    lib.parent.mkdir(parents=True);lib.target.mkdir()
    (lib.target/'user.lua').write_text('-- preserve me')
    atomic_json(lib.journal,journal)
    reopened=BotLibrary(paths)
    assert reopened.recovery_error
    with pytest.raises(Fault,match='日志损坏'):reopened.prepare_launch()
    assert (lib.target/'user.lua').read_text()=='-- preserve me'
    assert lib.journal.exists()


def test_never_touch_unmanaged_default_bots_symlink(paths,tmp_path):
    lib=BotLibrary(paths)
    lib.parent.mkdir(parents=True)
    outside=tmp_path/'own-bots';outside.mkdir();(outside/'own.lua').write_text('-- mine')
    lib.target.symlink_to(outside,target_is_directory=True)
    assert lib.prepare_launch() is None
    assert lib.target.is_symlink() and (outside/'own.lua').read_text()=='-- mine'
