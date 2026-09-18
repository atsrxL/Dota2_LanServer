"""Source/compiled-UI contracts, also used by the offline asset packaging tool."""
from __future__ import annotations
import hashlib
import json
import os
import stat
import struct
from pathlib import Path
from .common import Fault, read_json

ADDON_NAME = 'lan_dota'
CLIENT_REVISION = 'lanlab-130.1'
COMPILED_FILES = (
    'panorama/layout/custom_game/custom_ui_manifest.vxml_c',
    'panorama/layout/custom_game/lan_setup.vxml_c',
    'panorama/scripts/custom_game/lan_setup.vjs_c',
    'panorama/styles/custom_game/lan_setup.vcss_c',
)
MARKER = '.lan-addon-managed.json'
MAX_ASSET_BYTES = 64 * 1024 * 1024


def tree_inventory(root: Path, exclude_marker: bool = False) -> dict:
    if root.is_symlink() or not root.is_dir() or root.resolve() != root.absolute():
        raise Fault('附加模式资源路径无效或含链接', 409)
    entries = {}; total = 0; folded = set()
    for base, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            p = Path(base) / name
            mode = p.lstat().st_mode
            if not stat.S_ISREG(mode) and not stat.S_ISDIR(mode): raise Fault('资源含链接或特殊文件', 409)
        for name in sorted(names):
            p = Path(base) / name; rel = p.relative_to(root).as_posix()
            if exclude_marker and rel == MARKER: continue
            if any(c in rel for c in ('\\', ':', '\x00')) or any(ord(c) < 32 for c in rel):
                raise Fault('非法资源文件名', 409)
            if rel.casefold() in folded: raise Fault('资源存在大小写冲突', 409)
            folded.add(rel.casefold())
            size = p.stat().st_size; total += size
            if size > 16 * 1024 * 1024 or total > MAX_ASSET_BYTES or len(entries) >= 4096:
                raise Fault('附加模式资源超出大小或数量限制', 409)
            entries[rel] = {'bytes': size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    return dict(sorted(entries.items()))


def manifest_hash(entries: dict) -> str:
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def source_identity(root: Path) -> dict:
    entries = {}
    for folder in ('game', 'content'):
        for name, data in tree_inventory(root / folder).items(): entries[folder + '/' + name] = data
    return {'source_sha256': manifest_hash(entries), 'client_revision': CLIENT_REVISION,
            'ui_source_sha256': manifest_hash(tree_inventory(root / 'content'))}


def compiled_status(root: Path) -> dict:
    identity = source_identity(root)
    path = root / 'compiled'; meta = path / 'asset_manifest.json'
    if not meta.exists():
        return {'ready': False, 'reason': '需要在本地 Workshop Tools 编译 Panorama，再导入 compiled 资源包。', **identity}
    try:
        if path.is_symlink() or path.resolve() != path.absolute(): raise Fault('compiled 路径包含链接', 409)
        doc = read_json(meta)
        if not isinstance(doc, dict) or doc.get('schema') != 1 or doc.get('ui_source_sha256') != identity['ui_source_sha256']:
            raise Fault('编译资源对应的 UI 源码不同，请重建而不是重命名文件', 409)
        if doc.get('client_revision') != CLIENT_REVISION or set(doc.get('files', {})) != set(COMPILED_FILES):
            raise Fault('编译资源清单版本或文件不完整', 409)
        actual = tree_inventory(path)
        if set(actual) != set(COMPILED_FILES) | {'asset_manifest.json'}: raise Fault('编译资源包含未知文件', 409)
        for rel in COMPILED_FILES:
            if actual[rel] != doc['files'][rel] or actual[rel]['bytes'] < 16:
                raise Fault('编译资源文件校验不符', 409)
        for rel in COMPILED_FILES: validate_resource((path/rel).read_bytes())
        return {'ready': True, 'reason': '文件与清单匹配；引擎是否接受仍需实测。', **identity}
    except (Fault,OSError,ValueError,TypeError) as exc: return {'ready': False, 'reason': str(exc), **identity}


def validate_resource(data: bytes) -> None:
    """Bounded Source 2 header/block sanity, NOT a Panorama compiler/verifier.

    Format basis: ValveResourceFormat Resource.cs header v12. Reject unknown
    layouts rather than accepting renamed XML/JS. Engine acceptance is separate.
    """
    if len(data)<28: raise Fault('资源不是完整的 Source 2 编译文件',409)
    size,header,version,offset,count=struct.unpack_from('<IHHII',data)
    start=8+offset
    if size!=len(data) or header!=12 or not 1<=count<=128 or start<16 or start+12*count>len(data):
        raise Fault('未知或损坏的 Source 2 资源头；请核实真实编译结果',409)
    found=False
    for i in range(count):
        pos=start+12*i; kind,relative,length=struct.unpack_from('<4sII',data,pos)
        target=pos+4+relative
        if length and (target<start+12*count or target+length>len(data)):
            raise Fault('编译资源块越界',409)
        if kind==b'DATA' and length: found=True
    if not found: raise Fault('编译资源缺少 DATA 块',409)
