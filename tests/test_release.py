import pytest
from pathlib import Path
from panel.common import Fault
from tools import release as r
from tools.build_windows_client import publish


@pytest.fixture
def steps(monkeypatch):
    calls = []
    monkeypatch.setattr(r, 'as_user', lambda user, args: calls.append(('as_user', user, Path(args[1]).name)) if args[0] != 'find' else calls.append(('prune',)))
    monkeypatch.setattr(r.addon_assets, 'collect', lambda s, t, a: (a.write_bytes(b'zip'), calls.append(('collect', a.name))))
    monkeypatch.setattr(r.addon_assets, 'import_assets', lambda s, a, apply, replace_invalid: calls.append(('import', apply, replace_invalid)))
    monkeypatch.setattr(r, 'compiled_status', lambda s: {'ready': True, 'source_sha256': 'abc'})
    monkeypatch.setattr(r, 'build', lambda s, o, v: calls.append(('build', v)) or {'files': {'exe': {}}})
    return calls


def test_release_runs_every_step_in_order(steps, tmp_path):
    result = r.release('r25', tmp_path, tmp_path, tmp_path, 'steam', False, log=lambda _: None)
    assert [c[0] for c in steps] == ['as_user', 'prune', 'as_user', 'collect', 'import', 'build']
    assert steps[0][2] == 'addon_assets.py' and steps[2][2] == 'compile_panorama_wine.py'
    assert steps[4] == ('import', True, True) and steps[5] == ('build', 'r25')
    assert result['source_sha256'] == 'abc' and result['restarted'] is False


def test_release_stops_before_packaging_when_compiled_ui_invalid(steps, monkeypatch, tmp_path):
    monkeypatch.setattr(r, 'compiled_status', lambda s: {'ready': False, 'reason': 'stale'})
    with pytest.raises(Fault):
        r.release('r25', tmp_path, tmp_path, tmp_path, None, True, log=lambda _: None)
    assert 'build' not in [c[0] for c in steps]


def test_publish_replaces_files_and_leaves_no_staging(tmp_path):
    built, out = tmp_path / 'built', tmp_path / 'out'
    built.mkdir(); out.mkdir()
    (out / 'a.exe').write_text('old')
    (built / 'a.exe').write_text('new'); (built / 'manifest.json').write_text('{}')
    publish(built, out, ['a.exe', 'manifest.json'])
    assert (out / 'a.exe').read_text() == 'new' and (out / 'manifest.json').exists()
    assert sorted(p.name for p in out.iterdir()) == ['a.exe', 'manifest.json']


def test_release_archives_and_rotates_only_marked_releases(steps, tmp_path):
    artifacts = tmp_path / 'artifacts'; artifacts.mkdir()
    (artifacts / 'r24').mkdir()  # hand-made, no marker: never pruned
    source = tmp_path / 'addon' / 'lan_dota'; source.mkdir(parents=True)
    for i in range(5):
        (source.parent / f'lan_dota.compiled-backup-{i}').mkdir()
    out = tmp_path / 'client'; out.mkdir(); (out / 'manifest.json').write_text('{}')
    for v in ('r25', 'r26', 'r27', 'r28'):
        r.release(v, source, tmp_path, out, None, False, log=lambda _: None, artifacts=artifacts, keep=3)
    kept = sorted(p.name for p in artifacts.iterdir())
    assert kept == ['r24', 'r26', 'r27', 'r28']
    assert (artifacts / 'r28' / 'lan-dota-r28-compiled.zip').read_bytes() == b'zip'
    assert (artifacts / 'r28' / 'manifest.json').exists() and (artifacts / 'r28' / 'release.json').exists()
    assert len(list(source.parent.glob('lan_dota.compiled-backup-*'))) == 3
    with pytest.raises(Fault):
        r.release('r28', source, tmp_path, out, None, False, log=lambda _: None, artifacts=artifacts)
