"""Bounded bot-content handling. Never execute an archive, a Lua file or a shell.

Workshop items may contain loose Lua, ZIP or Valve VPK v1/v2. VPK v1/v2
entries are uncompressed; unsupported/compressed variants fail closed.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import stat
import struct
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Callable

from .common import Fault

MAX_FILES = 12000
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TREE_BYTES = 8 * 1024 * 1024
RESERVED = '.dota-panel-bot.json'
# Bot Lua and data only. No native binaries, installers or executable config.
SUFFIXES = {'.lua', '.json', '.txt', '.kv', '.vdf', '.csv', '.md', '.xml', '.yaml', '.yml'}
ENTRIES = {'hero_selection.lua', 'bot_generic.lua', 'ability_item_usage_generic.lua', 'item_purchase_generic.lua'}


def safe_name(name: str) -> str:
    if (not isinstance(name, str) or not name or len(name.encode('utf-8')) > 1024
            or '\\' in name or ':' in name or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise Fault('机器人包包含非法路径')
    parts = name.split('/')
    if any(x in {'', '.', '..'} for x in parts) or PurePosixPath(name).is_absolute():
        raise Fault('机器人包存在路径穿越或绝对路径')
    if any(len(x.encode('utf-8')) > 240 for x in parts) or len(parts) > 20:
        raise Fault('机器人包路径过长或嵌套过深')
    if any(x.lower() == RESERVED for x in parts):
        raise Fault('机器人包占用了面板保留文件名')
    return name


def regular_tree(root: Path, check: Callable = lambda: None) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise Fault('机器人内容目录无效或是符号链接')
    found, total = [], 0
    for base, dirs, files in os.walk(root, followlinks=False):
        check()
        for name in dirs + files:
            path = Path(base) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise Fault('机器人目录含符号链接、设备或其他特殊文件')
            safe_name(path.relative_to(root).as_posix())
        for name in files:
            path = Path(base) / name
            size = path.stat().st_size
            if size > MAX_TOTAL_BYTES:
                raise Fault('机器人包单个源文件超过 256 MiB')
            total += size
            found.append(path)
            if len(found) > MAX_FILES or total > MAX_TOTAL_BYTES:
                raise Fault('机器人包超过文件数量或 256 MiB 总量限制')
    return sorted(found)


class Writer:
    def __init__(self, destination: Path, check: Callable):
        self.destination, self.check = destination, check
        self.names: set[str] = set()
        self.total = 0
        destination.mkdir(parents=True, exist_ok=False)

    def write(self, name: str, size: int, stream, expected_crc: int | None = None):
        self.check()
        safe_name(name)
        key = name.casefold()
        if key in self.names:
            raise Fault('机器人包存在重名或大小写冲突文件')
        if size < 0 or size > MAX_FILE_BYTES or self.total + size > MAX_TOTAL_BYTES or len(self.names) >= MAX_FILES:
            raise Fault('解包内容超过安全大小/数量限制')
        self.names.add(key)
        self.total += size
        target = self.destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        remaining, crc = size, 0
        with target.open('xb') as output:
            os.chmod(target, 0o600)
            while remaining:
                self.check()
                part = stream.read(min(65536, remaining))
                if not part:
                    raise Fault('机器人归档被截断')
                output.write(part)
                crc = zlib.crc32(part, crc)
                remaining -= len(part)
        if expected_crc is not None and (crc & 0xffffffff) != expected_crc:
            raise Fault('VPK 文件 CRC 校验失败')


def unpack_zip(path: Path, writer: Writer):
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES * 2:
                raise Fault('ZIP 条目过多')
            for item in entries:
                writer.check()
                name = item.filename.rstrip('/') if item.is_dir() else item.filename
                safe_name(name)
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}):
                    raise Fault('ZIP 中禁止链接及特殊文件')
                if item.flag_bits & 1:
                    raise Fault('不支持加密 ZIP')
                if item.is_dir():
                    continue
                with archive.open(item) as stream:
                    writer.write(name, item.file_size, stream)
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
        raise Fault(f'ZIP 无效或格式不受支持：{type(exc).__name__}') from None


def unpack_vpk(path: Path, writer: Writer):
    with path.open('rb') as main:
        header = main.read(12)
        if len(header) != 12:
            raise Fault('VPK 头被截断')
        magic, version, tree_size = struct.unpack('<III', header)
        if magic != 0x55AA1234 or version not in {1, 2}:
            raise Fault('仅支持标准 VPK v1/v2；不执行第三方解包程序')
        if not 0 < tree_size <= MAX_TREE_BYTES:
            raise Fault('VPK 目录树大小无效')
        header_size, file_data_size = 12, None
        if version == 2:
            extra = main.read(16)
            if len(extra) != 16:
                raise Fault('VPK v2 头被截断')
            file_data_size, _, _, _ = struct.unpack('<IIII', extra)
            header_size = 28
        tree_bytes = main.read(tree_size)
        if len(tree_bytes) != tree_size:
            raise Fault('VPK 目录树被截断')
        tree = io.BytesIO(tree_bytes)
        data_start = header_size + tree_size
        embedded_size = path.stat().st_size - data_start if file_data_size is None else file_data_size
        if embedded_size < 0 or data_start + embedded_size > path.stat().st_size:
            raise Fault('VPK 数据段越界')

        def string():
            data = bytearray()
            while True:
                byte = tree.read(1)
                if not byte or len(data) > 1024:
                    raise Fault('VPK 字符串未终止或过长')
                if byte == b'\0':
                    try:
                        return data.decode('utf-8')
                    except UnicodeError:
                        raise Fault('VPK 文件名不是 UTF-8') from None
                data.extend(byte)

        while True:
            extension = string()
            if not extension:
                break
            if '/' in extension or '\\' in extension:
                raise Fault('VPK 扩展名无效')
            while True:
                folder = string()
                if not folder:
                    break
                while True:
                    name = string()
                    if not name:
                        break
                    if '/' in name or '\\' in name:
                        raise Fault('VPK 文件名无效')
                    entry = tree.read(18)
                    if len(entry) != 18:
                        raise Fault('VPK 条目被截断')
                    crc, preload_size, archive_index, offset, length, terminator = struct.unpack('<IHHIIH', entry)
                    if terminator != 0xffff or preload_size + length > MAX_FILE_BYTES:
                        raise Fault('VPK 条目无效或过大')
                    preload = tree.read(preload_size)
                    if len(preload) != preload_size:
                        raise Fault('VPK 预载数据被截断')
                    relative = ('' if folder == ' ' else folder + '/') + name + ('' if extension == ' ' else '.' + extension)
                    safe_name(relative)
                    if archive_index == 0x7fff:
                        source, start, available = path, data_start + offset, embedded_size
                    else:
                        if not path.name.endswith('_dir.vpk') or archive_index > 999:
                            raise Fault('VPK 分卷名称或编号不受支持')
                        source = path.with_name(path.name[:-8] + f'_{archive_index:03d}.vpk')
                        if source.is_symlink() or not source.is_file():
                            raise Fault('VPK 缺少分卷或分卷是链接')
                        start, available = offset, source.stat().st_size
                    if offset + length > available:
                        raise Fault('VPK 条目数据偏移越界')
                    with source.open('rb') as data:
                        data.seek(start)
                        # Bound to a single bot-file limit. No arbitrary allocation.
                        payload = data.read(length)
                    if len(payload) != length:
                        raise Fault('VPK 数据被截断')
                    writer.write(relative, preload_size + length, io.BytesIO(preload + payload), crc)
        if tree.tell() != tree_size:
            raise Fault('VPK 目录树含未识别尾部内容')


def find_root(root: Path, check: Callable = lambda: None) -> Path:
    files = regular_tree(root, check)
    candidates = {p.parent for p in files if p.name in ENTRIES or re.fullmatch(r'bot_[a-z0-9_]+\.lua', p.name)}
    # A root with an entry plus nested libraries should be unambiguous. Multiple
    # independent bots in a collection are not silently merged into one script.
    candidates = {p for p in candidates if not any(q != p and q in p.parents for q in candidates)}
    if len(candidates) != 1:
        raise Fault('无法唯一识别机器人 Lua 根目录；需要 hero_selection.lua / bot_generic.lua 等入口，不能是合集或纯游廊地图')
    return candidates.pop()


def inventory(root: Path, check: Callable = lambda: None) -> tuple[str, list[dict], int]:
    if root.is_symlink() or not root.is_dir():
        raise Fault('脚本目录不存在或是符号链接')
    entries, total = [], 0
    seen = set()
    # RESERVED is authored by us, excluded from content checksum.
    for base, dirs, names in os.walk(root, followlinks=False):
        for name in dirs:
            p = Path(base) / name
            if p.is_symlink():
                raise Fault('已安装脚本出现链接')
        for name in sorted(names):
            if name == RESERVED and Path(base) == root:
                continue
            check()
            path = Path(base) / name
            if path.is_symlink() or not path.is_file():
                raise Fault('已安装脚本出现特殊文件')
            rel = safe_name(path.relative_to(root).as_posix())
            if rel.casefold() in seen:
                raise Fault('脚本存在大小写冲突路径')
            seen.add(rel.casefold())
            size = path.stat().st_size
            total += size
            if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES or len(entries) >= MAX_FILES:
                raise Fault('脚本文件大小或数量超限')
            digest = hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    check()
                    digest.update(chunk)
            entries.append({'path': rel, 'bytes': size, 'sha256': digest.hexdigest()})
    entries.sort(key=lambda x: x['path'])
    checksum = hashlib.sha256()
    for entry in entries:
        checksum.update(entry['path'].encode() + b'\0' + str(entry['bytes']).encode() + b'\0' + entry['sha256'].encode() + b'\n')
    return checksum.hexdigest(), entries, total


def stage_content(source: Path, work: Path, check: Callable = lambda: None) -> dict:
    files = regular_tree(source, check)
    archives = [p for p in files if p.suffix.lower() == '.zip' or
                (p.suffix.lower() == '.vpk' and not re.search(r'_\d{3}\.vpk$', p.name))]
    expanded = work / 'expanded'
    if archives:
        if len(archives) != 1 or any(p.suffix.lower() == '.lua' for p in files):
            raise Fault('机器人包同时含多个归档或归档与 Lua，拒绝猜测要加载的脚本')
        writer = Writer(expanded, check)
        if archives[0].suffix.lower() == '.zip':
            unpack_zip(archives[0], writer)
        else:
            unpack_vpk(archives[0], writer)
        source = expanded
    root = find_root(source, check)
    target = work / 'scripts'
    target.mkdir(exist_ok=False)
    skipped = []
    for path in regular_tree(root, check):
        relative = path.relative_to(root)
        if path.suffix.lower() not in SUFFIXES:
            skipped.append(relative.as_posix())
            continue
        check()
        if path.stat().st_size > MAX_FILE_BYTES:
            raise Fault('单个脚本/数据文件超过 32 MiB')
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest, follow_symlinks=False)
        os.chmod(dest, 0o600)
    find_root(target, check)
    digest, entries, total = inventory(target, check)
    if not entries:
        raise Fault('机器人包没有可安装的 Lua')
    return {'version': digest, 'files': entries, 'bytes': total, 'skipped': skipped[:100],
            'skipped_count': len(skipped), 'source_format': archives[0].suffix.lower()[1:] if archives else 'loose'}
