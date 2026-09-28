import hashlib
import io
import json
import zipfile
import pytest
from panel.common import build_info
from tools import deploy_kit as d

COMMIT = 'a' * 40


def package(files):
    files = dict(files)
    files['BUILD.json'] = json.dumps({'version': '1.3.0', 'commit': COMMIT, 'dirty': False}).encode()
    sums = ''.join(f'{hashlib.sha256(v).hexdigest()}  {k}\n' for k, v in sorted(files.items()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for k, v in files.items():
            z.writestr(d.PREFIX + k, v)
        z.writestr(d.PREFIX + 'SHA256SUMS', sums)
    buf.seek(0)
    return buf


def kit_files(tag):
    return {rel + '/f.txt': tag.encode() for rel in d.MANAGED_DIRS} | {'README.md': tag.encode()}


def test_install_swaps_managed_paths_only(tmp_path):
    kit = tmp_path / 'kit'
    for rel, data in kit_files('old').items():
        (kit / rel).parent.mkdir(parents=True, exist_ok=True); (kit / rel).write_bytes(data)
    (kit / 'panel/stale.py').write_text('removed on deploy')
    (kit / 'config').mkdir(); (kit / 'config/server.json').write_text('keep')
    (kit / 'addon/lan_dota/compiled').mkdir(parents=True); (kit / 'addon/lan_dota/compiled/x').write_text('keep')
    files, build = d.read_archive(package(kit_files('new')))
    assert build['commit'] == COMMIT
    d.install(kit, files)
    assert (kit / 'panel/f.txt').read_text() == 'new' and not (kit / 'panel/stale.py').exists()
    assert (kit / 'config/server.json').read_text() == 'keep'
    assert (kit / 'addon/lan_dota/compiled/x').read_text() == 'keep'
    assert json.loads((kit / 'BUILD.json').read_text())['commit'] == COMMIT
    assert not [p for p in kit.iterdir() if p.name.startswith(('.deploy-', '.retired-'))]


def test_tampered_or_unlisted_files_rejected():
    buf = package(kit_files('new'))
    raw = io.BytesIO()
    with zipfile.ZipFile(buf) as src, zipfile.ZipFile(raw, 'w') as dst:
        for info in src.infolist():
            data = src.read(info)
            dst.writestr(info, b'evil' if info.filename.endswith('panel/f.txt') else data)
        dst.writestr(d.PREFIX + 'panel/extra.py', b'x')
    raw.seek(0)
    with pytest.raises(d.DeployError):
        d.read_archive(raw)


def test_missing_directory_rolls_back(tmp_path):
    kit = tmp_path / 'kit'
    for rel, data in kit_files('old').items():
        (kit / rel).parent.mkdir(parents=True, exist_ok=True); (kit / rel).write_bytes(data)
    files = {k: v for k, v in kit_files('new').items() if not k.startswith('docs/')}
    with pytest.raises(d.DeployError):
        d.install(kit, files)
    assert (kit / 'panel/f.txt').read_text() == 'old'


def test_backup_rotation_keeps_newest(tmp_path):
    kit = tmp_path / 'kit'; (kit / 'panel').mkdir(parents=True); (kit / 'panel/a.py').write_text('x')
    backups = tmp_path / 'b'; backups.mkdir()
    (backups / 'unrelated.tgz').write_text('not ours')
    for i in range(4):
        (backups / f'kit-2026010{i}-000000-old.tgz').write_text('old')
    d.backup(kit, backups, 3, 'abc')
    names = sorted(p.name for p in backups.iterdir())
    assert len([n for n in names if n.startswith('kit-')]) == 3 and 'unrelated.tgz' in names


def test_build_info_reads_commit_and_deploy_time(tmp_path):
    assert build_info(tmp_path)['commit'] is None
    (tmp_path / 'BUILD.json').write_text(json.dumps({'commit': COMMIT, 'dirty': True}))
    (tmp_path / 'DEPLOYED.json').write_text(json.dumps({'deployed_at': '2026-09-28T01:00:00+00:00'}))
    info = build_info(tmp_path)
    assert info['commit'] == COMMIT and info['dirty'] and info['deployed_at'].startswith('2026')
    (tmp_path / 'BUILD.json').write_text(json.dumps({'commit': '../etc'}))
    assert build_info(tmp_path)['commit'] is None
