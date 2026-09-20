"""Fixed, public client artifacts only. Never expose Steam or server state directories."""
import hashlib
import json
from pathlib import Path
from .common import Fault
from .addon_assets import source_identity

ROOT = Path('/opt/dota2-lan-kit/client-downloads')
SOURCE = Path('/opt/dota2-lan-kit/addon/lan_dota')
NAMES = {'exe': 'Dota2-LAN-Client.exe', 'zip': 'Dota2-LAN-Client.zip'}


def metadata():
    path = ROOT / 'manifest.json'
    if not path.is_file():
        return {'available': False, 'message': '客户端安装包尚未发布。'}
    doc = json.loads(path.read_text())
    matches = doc['source_sha256'] == source_identity(SOURCE)['source_sha256']
    return {'available': True, **doc, 'server_matches': matches}


def download(kind):
    if kind not in NAMES:
        raise Fault('下载项目不存在', 404)
    doc = metadata()
    if not doc['available']:
        raise Fault('客户端安装包尚未发布', 404)
    if not doc['server_matches']:
        raise Fault('服务器资源已变化，客户端包等待重新发布', 409)
    path = ROOT / NAMES[kind]
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise Fault('客户端安装包不可用', 503)
    data = path.read_bytes()
    expected = doc['files'][kind]
    if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
        raise Fault('客户端安装包校验失败', 503)
    return data, NAMES[kind]
