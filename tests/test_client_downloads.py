import hashlib
import json
import pytest
from panel import client_downloads as c
from panel.common import Fault
from test_web import request
from panel.web import WebApp

@pytest.fixture(autouse=True)
def fresh_caches():
    c._source_cache.clear();c._verified.clear()

@pytest.fixture
def release(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    monkeypatch.setattr(c, 'SOURCE', tmp_path / 'source')
    monkeypatch.setattr(c, 'source_identity', lambda _: {'source_sha256': 'same'})
    data = b'MZ-test-only'
    (tmp_path / c.NAMES['exe']).write_bytes(data)
    doc = {'source_sha256': 'same', 'files': {'exe': {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}}
    (tmp_path / 'manifest.json').write_text(json.dumps(doc))
    return tmp_path, doc

def test_fixed_download_and_hash(release):
    app = WebApp()
    result = request(app, '/api/client-download?kind=exe')
    assert result['status'] == 200 and result['raw'] == b'MZ-test-only'
    assert 'attachment' in result['headers']['Content-Disposition']
    assert request(app, '/api/client-download?kind=../../server.json')['status'] == 404
    (release[0] / c.NAMES['exe']).write_bytes(b'MZ-modified')
    assert request(app, '/api/client-download')['status'] == 503

def test_mismatch_and_symlink_rejected(release, monkeypatch):
    monkeypatch.setattr(c, 'source_identity', lambda _: {'source_sha256': 'new'})
    c._source_cache.clear()
    with pytest.raises(Fault) as e: c.download('exe')
    assert e.value.code == 409
    monkeypatch.setattr(c, 'source_identity', lambda _: {'source_sha256': 'same'})
    c._source_cache.clear()
    p = release[0] / c.NAMES['exe'];p.unlink();p.symlink_to('/etc/passwd')
    with pytest.raises(Fault) as e: c.download('exe')
    assert e.value.code == 503

def test_unpublished(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    assert c.metadata()['available'] is False

def test_corrupt_manifest_is_reported_not_500(release):
    (release[0] / 'manifest.json').write_text('{"files": 1}')
    assert c.metadata()['available'] is False and '损坏' in c.metadata()['message']
    assert request(WebApp(), '/api/client-download?kind=exe')['status'] == 503

def test_source_hash_recomputed_only_after_source_changes(release, monkeypatch):
    calls = []
    monkeypatch.setattr(c, 'source_identity', lambda _: calls.append(1) or {'source_sha256': 'same'})
    source = release[0] / 'source'; source.mkdir(); (source / 'a.lua').write_text('x')
    for _ in range(3): assert c.metadata()['server_matches']
    assert len(calls) == 1
    (source / 'a.lua').write_text('changed')
    c.metadata()
    assert len(calls) == 2

def test_download_streams_and_closes_handle(release):
    handle, size, name = c.download('exe')
    assert size == len(b'MZ-test-only') and name == c.NAMES['exe']
    assert handle.read() == b'MZ-test-only'
    handle.close()
