"""Fixed, public client artifacts only. Never expose Steam or server state directories."""
import hashlib
import json
import os
import stat
import threading
from pathlib import Path
from .common import Fault
from .addon_assets import source_identity

ROOT = Path('/opt/dota2-lan-kit/client-downloads')
SOURCE = Path('/opt/dota2-lan-kit/addon/lan_dota')
NAMES = {'exe': 'Dota2-LAN-Client.exe', 'zip': 'Dota2-LAN-Client.zip'}
MAX_BYTES = 64 * 1024 * 1024
CHUNK = 256 * 1024

_lock = threading.Lock()
_source_cache = {}  # stat signature -> source_sha256
_verified = {}      # kind -> ((dev, inode, size, mtime_ns), sha256)


def _source_signature(root):
    """Cheap stat-only fingerprint; the full content hash is recomputed only when it changes."""
    sig = []
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs.sort()
        for name in sorted(names):
            st = os.lstat(os.path.join(base, name))
            sig.append((os.path.relpath(os.path.join(base, name), root), st.st_size, st.st_mtime_ns, st.st_ino))
    return tuple(sig)


def _source_sha256():
    key = (str(SOURCE), _source_signature(SOURCE))
    with _lock:
        if key in _source_cache:
            return _source_cache[key]
    value = source_identity(SOURCE)['source_sha256']
    with _lock:
        _source_cache.clear()
        _source_cache[key] = value
    return value


def _manifest():
    path = ROOT / 'manifest.json'
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(doc.get('source_sha256'), str):
            raise ValueError('source_sha256')
        for kind, entry in doc['files'].items():
            if kind not in NAMES or type(entry['bytes']) is not int or not isinstance(entry['sha256'], str):
                raise ValueError(kind)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise Fault('客户端安装包清单损坏，请重新发布', 503) from exc
    return doc


def metadata():
    try:
        doc = _manifest()
    except Fault as exc:
        return {'available': False, 'message': str(exc)}
    if doc is None:
        return {'available': False, 'message': '客户端安装包尚未发布。'}
    try:
        matches = doc['source_sha256'] == _source_sha256()
    except (Fault, OSError):
        matches = False
    return {'available': True, **doc, 'server_matches': matches}


def _hash_open_file(handle):
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(CHUNK), b''):
        digest.update(block)
    handle.seek(0)
    return digest.hexdigest()


def download(kind):
    """Return (open binary handle, size, filename). The caller must close the handle."""
    if kind not in NAMES:
        raise Fault('下载项目不存在', 404)
    doc = _manifest()
    if doc is None:
        raise Fault('客户端安装包尚未发布', 404)
    if doc['source_sha256'] != _source_sha256():
        raise Fault('服务器资源已变化，客户端包等待重新发布', 409)
    expected = doc['files'].get(kind)
    path = ROOT / NAMES[kind]
    if expected is None or path.is_symlink():
        raise Fault('客户端安装包不可用', 503)
    try:
        handle = open(path, 'rb')
    except OSError as exc:
        raise Fault('客户端安装包不可用', 503) from exc
    try:
        st = os.fstat(handle.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES or st.st_size != expected['bytes']:
            raise Fault('客户端安装包校验失败', 503)
        # Verify the exact inode being streamed; re-hash only when the file changes.
        sig = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        with _lock:
            cached = _verified.get(kind)
        known = cached[1] if cached and cached[0] == sig else None
        if known is None:
            known = _hash_open_file(handle)
            with _lock:
                _verified[kind] = (sig, known)
        if known != expected['sha256']:
            raise Fault('客户端安装包校验失败', 503)
        return handle, st.st_size, NAMES[kind]
    except BaseException:
        handle.close()
        raise
