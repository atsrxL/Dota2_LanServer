import hashlib
import json
import pytest
from panel import client_downloads as c
from panel.common import Fault
from test_web import request
from panel.web import WebApp

@pytest.fixture
def release(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'ROOT', tmp_path)
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
    with pytest.raises(Fault) as e: c.download('exe')
    assert e.value.code == 409
    monkeypatch.setattr(c, 'source_identity', lambda _: {'source_sha256': 'same'})
    p = release[0] / c.NAMES['exe'];p.unlink();p.symlink_to('/etc/passwd')
    with pytest.raises(Fault) as e: c.download('exe')
    assert e.value.code == 503

def test_unpublished(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    assert c.metadata()['available'] is False
