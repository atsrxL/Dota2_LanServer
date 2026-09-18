"""Workshop metadata, immutable versions and crash-recoverable deployment.

Only Manager's serialized mutation worker may call mutating methods. Selection
is next-launch state; a running game uses its own pinned launch snapshot.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Any

from .bot_files import MAX_TOTAL_BYTES, RESERVED, inventory, stage_content
from .common import Fault, Paths, atomic_json, now, read_json

METADATA_URL = 'https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/'
MAX_ITEMS = 50
MAX_VERSIONS = 12


def workshop_id(value: Any) -> str:
    if not isinstance(value, str):
        raise Fault('Workshop ID 必须以字符串提交，避免浏览器丢失大整数精度')
    value = value.strip()
    if not re.fullmatch(r'[1-9][0-9]{0,19}', value) or int(value) > 2**64 - 1:
        raise Fault('请输入单个有效 Workshop 数字 ID，例如 1627071163；不接受 URL、合集或命令')
    return value


def version_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
        raise Fault('脚本版本必须是库中已有的完整 SHA-256')
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Fault('Steam 元数据接口发生重定向，已拒绝；不会跟随到任意 URL', 502)


def lookup_item(value: str) -> dict:
    item = workshop_id(value)
    body = urllib.parse.urlencode({'itemcount': '1', 'publishedfileids[0]': item}).encode()
    request = urllib.request.Request(METADATA_URL, data=body, method='POST', headers={
        'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Dota2-LAN-Panel/1.2'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise Fault('Steam 元数据响应过大', 502)
        result = json.loads(raw)
        entries = result['response']['publishedfiledetails']
        if not isinstance(entries, list) or len(entries) != 1:
            raise ValueError()
        return validate_metadata(item, entries[0])
    except Fault:
        raise
    except (urllib.error.URLError, OSError):
        raise Fault('无法读取 Steam Workshop 元数据；检查 LXC 的 DNS、出站网络或条目可见性。没有更改现用脚本。', 502) from None
    except (ValueError, UnicodeError, KeyError, TypeError):
        raise Fault('Steam 元数据格式变化或不完整，已停止安装', 502) from None


def validate_metadata(item: str, raw: dict) -> dict:
    if not isinstance(raw, dict) or str(raw.get('publishedfileid')) != item or raw.get('result') != 1:
        raise Fault('Workshop 条目不存在、私有或无权访问', 409)
    if raw.get('consumer_app_id') != 570:
        raise Fault('该条目不属于 Dota 2（App 570）', 409)
    # Some older GetPublishedFileDetails responses omit file_type. App, bot
    # tags and the actual Lua-entry validation remain mandatory.
    if raw.get('file_type') is not None and raw['file_type'] != 0:
        raise Fault('仅接受单个 Workshop 社区条目，不支持合集、指南或其他类型', 409)
    if raw.get('banned'):
        raise Fault('该 Workshop 条目已被封禁，不能安装', 409)
    tags = [str(x.get('tag', ''))[:100] for x in raw.get('tags', []) if isinstance(x, dict)]
    if not any(tag.strip().casefold() in {'bot scripts', 'bot script', 'bots', 'bot', '机器人脚本'} for tag in tags):
        raise Fault('该条目未标记为机器人脚本（Bot Scripts），不会把地图/皮肤当作机器人安装', 409)
    try:
        size = int(raw.get('file_size', 0))
    except (ValueError, TypeError):
        raise Fault('Workshop 条目大小无效', 502) from None
    if not 0 <= size <= MAX_TOTAL_BYTES:
        raise Fault('该条目超过 256 MiB 机器人包限制', 409)
    title = str(raw.get('title') or ('Workshop ' + item))[:160]
    title = ''.join(c for c in title if ord(c) >= 32 and ord(c) != 127)
    return {'item_id': item, 'title': title, 'tags': tags[:40], 'bytes': size,
            'upstream_updated': raw.get('time_updated'), 'checked_at': now(),
            'workshop_url': 'https://steamcommunity.com/sharedfiles/filedetails/?id=' + item}


def locate_download(paths: Paths, item: str, output: str) -> Path:
    """Never trust a SteamCMD-reported arbitrary path or an arbitrary old cache."""
    item = workshop_id(item)
    # force_install_dir need not control Workshop location. These are our only
    # managed roots; a different layout fails with a diagnostic, not a glob of /.
    candidates = [base / 'steamapps/workshop/content/570' / item for base in
                  (paths.steam, paths.game, paths.state / 'Steam', paths.state / '.local/share/Steam')]
    reported = re.findall(r'(?im)Success\.\s+Downloaded item\s+' + re.escape(item) + r'\s+to\s+"([^"\r\n]+)"', output)
    if reported:
        if len(set(reported)) != 1:
            raise Fault('SteamCMD 报告了多个下载目录，已停止', 409)
        supplied = Path(reported[0])
        if not supplied.is_absolute() or '..' in supplied.parts:
            raise Fault('SteamCMD 返回非法下载目录', 409)
        candidates = [p for p in candidates if p.absolute() == supplied]
    valid = []
    for path in candidates:
        if not path.is_dir():
            continue
        # Refuse a symlink in all descendant components of one of our base roots.
        if path.resolve() != path.absolute():
            raise Fault('Workshop 缓存路径包含符号链接；请使用标准受管目录', 409)
        valid.append(path)
    if len(valid) != 1:
        raise Fault('下载返回成功，但未找到唯一的受管 Workshop 内容目录；检查任务日志中的实际路径，不会使用其他旧缓存', 409)
    return valid[0]


class BotLibrary:
    def __init__(self, paths: Paths):
        self.paths = paths
        self.root = paths.state / 'bot-library'
        self.root.mkdir(mode=0o700, exist_ok=True)
        for name in ('items', 'incoming'):
            (self.root / name).mkdir(mode=0o700, exist_ok=True)
        self.selection_path = self.root / 'selection.json'
        self.deployment_path = self.root / 'deployment.json'
        self.journal = self.root / 'deployment-journal.json'
        self.parent = paths.game / 'game/dota/scripts/vscripts'
        self.target = self.parent / 'bots'
        self.recovery_error = None
        try:
            self.recover()
        except Fault as exc:
            self.recovery_error = str(exc)

    def _safe_parent(self):
        cursor = self.paths.game
        if cursor.is_symlink():
            raise Fault('游戏根目录不得是符号链接', 409)
        for component in self.parent.relative_to(self.paths.game).parts:
            cursor = cursor / component
            if cursor.is_symlink():
                raise Fault('游戏脚本路径含符号链接，已拒绝部署', 409)
            cursor.mkdir(exist_ok=True)
        if self.target.is_symlink():
            raise Fault('现有 bots 是符号链接，已拒绝接管', 409)

    def _backup_path(self, name: str) -> Path:
        if not isinstance(name, str) or not re.fullmatch(r'\.dota-panel-bots-(?:old|new)-[a-f0-9]{24}', name):
            raise Fault('机器人部署日志中的目录名无效', 500)
        path = self.parent / name
        if path.is_symlink():
            raise Fault('机器人部署备份是符号链接', 409)
        return path

    def _selection(self) -> dict:
        value = read_json(self.selection_path, {'selected': None, 'previous': None})
        if not isinstance(value, dict):
            raise Fault('机器人选择记录损坏', 500)
        return value

    def _version_path(self, item, version) -> Path:
        root = self.root / 'items' / workshop_id(item) / 'versions' / version_id(version)
        if root.is_symlink() or root.resolve() != root.absolute() or not (root / 'scripts').is_dir():
            raise Fault('机器人版本不存在或路径无效', 409)
        return root

    def validate_selection(self, selected: dict | None, verify: bool = True) -> dict | None:
        if selected is None:
            return None
        if not isinstance(selected, dict):
            raise Fault('机器人选择格式无效')
        item, version = workshop_id(selected.get('item_id')), version_id(selected.get('version'))
        path = self._version_path(item, version)
        info = read_json(path / 'version.json')
        if not isinstance(info, dict) or info.get('version') != version or info.get('item_id') != item:
            raise Fault('机器人版本元数据损坏', 409)
        difficulty = selected.get('difficulty', 2)
        probe = selected.get('entry_probe', True)
        if type(difficulty) is not int or not 0 <= difficulty <= 3 or type(probe) is not bool:
            raise Fault('机器人难度必须为 0～3，入口日志开关必须为布尔值')
        if verify and inventory(path / 'scripts')[0] != version:
            raise Fault('机器人库文件已改变或损坏；请重新下载，不能按原版本开局', 409)
        return {'item_id': item, 'version': version, 'title': info['title'],
                'difficulty': difficulty, 'entry_probe': probe}

    def install(self, source: Path, metadata: dict, check: Callable = lambda: None) -> dict:
        item = workshop_id(metadata['item_id'])
        item_root = self.root / 'items' / item
        if not item_root.exists() and len(list((self.root / 'items').iterdir())) >= MAX_ITEMS:
            raise Fault('机器人库最多保留 50 个条目；请先移除不用的条目版本', 409)
        versions = item_root / 'versions'
        versions.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix='bot-', dir=self.root / 'incoming'))
        try:
            info = stage_content(source, work, check)
            check()
            info.update(item_id=item, title=metadata['title'], installed_at=now(),
                        upstream_updated=metadata.get('upstream_updated'), load_status='not_tested')
            destination = versions / info['version']
            if not destination.exists():
                if len(list(versions.iterdir())) >= MAX_VERSIONS:
                    raise Fault('单个机器人最多保留 12 个版本；请先移除不再使用的版本', 409)
                atomic_json(work / 'version.json', info)
                # expanded archive is only a scratch copy; keep normalized scripts.
                if (work / 'expanded').exists():
                    shutil.rmtree(work / 'expanded')
                check()
                os.replace(work, destination)
            elif inventory(destination / 'scripts', check)[0] != info['version']:
                raise Fault('同 SHA 的已有机器人版本损坏；先移除损坏版本再下载', 409)
            atomic_json(item_root / 'metadata.json', metadata | {'latest_version': info['version']})
            return info
        finally:
            if work.exists():
                shutil.rmtree(work)

    def select(self, data: dict) -> dict:
        current = self._selection()
        if data.get('item_id') is None:
            selected = None
        else:
            item = workshop_id(data['item_id'])
            latest = read_json(self.root / 'items' / item / 'metadata.json', {}).get('latest_version')
            selected = self.validate_selection(data | {'item_id': item, 'version': data.get('version') or latest})
        if selected != current.get('selected'):
            atomic_json(self.selection_path, {'selected': selected, 'previous': current.get('selected'), 'saved_at': now()})
        return selected

    def rollback_selection(self) -> dict | None:
        state = self._selection()
        previous = self.validate_selection(state.get('previous'))
        atomic_json(self.selection_path, {'selected': previous, 'previous': state.get('selected'), 'saved_at': now()})
        return previous

    def list(self) -> dict:
        items = []
        for path in sorted((self.root / 'items').iterdir()):
            if not re.fullmatch(r'[1-9][0-9]{0,19}', path.name) or path.is_symlink():
                continue
            meta = read_json(path / 'metadata.json', {'item_id': path.name, 'title': '未完成安装'})
            versions = []
            for v in (path / 'versions').glob('*/version.json'):
                info = read_json(v, {})
                versions.append({k: info.get(k) for k in ('version', 'bytes', 'installed_at', 'upstream_updated', 'source_format', 'skipped_count')})
            items.append(meta | {'versions': sorted(versions, key=lambda x: x['installed_at'] or '', reverse=True)})
        return {'items': items, **self._selection(), 'deployment': read_json(self.deployment_path),
                'recovery_required': self.journal.exists(), 'recovery_error': self.recovery_error,
                'limits': {'items': MAX_ITEMS, 'versions_per_item': MAX_VERSIONS, 'package_bytes': MAX_TOTAL_BYTES},
                'notice': '保存选择仅影响下次手动开局；入口日志只能证明入口执行，不能证明 AI、槽位或对局正确。原生房间同步尚未实现。'}

    def remove(self, data: dict, running_selection: dict | None):
        item, version = workshop_id(data.get('item_id')), version_id(data.get('version'))
        state = self._selection()
        deployed = (read_json(self.deployment_path, {}) or {}).get('selection')
        for reference in (state.get('selected'), state.get('previous'), running_selection, deployed):
            if reference and reference.get('item_id') == item and reference.get('version') == version:
                raise Fault('此版本仍被下局、上次选择、已部署目录或当前对局引用；不能删除', 409)
        path = self._version_path(item, version)
        shutil.rmtree(path)
        parent = path.parent.parent
        remaining = list((parent / 'versions').iterdir())
        if not remaining:
            shutil.rmtree(parent)
        else:
            meta = read_json(parent / 'metadata.json', {})
            if meta.get('latest_version') == version:
                info = max((read_json(v / 'version.json') for v in remaining), key=lambda x: x['installed_at'])
                atomic_json(parent / 'metadata.json', meta | {'latest_version': info['version']})

    def recover(self):
        journal = read_json(self.journal)
        if journal is None:
            deployed = read_json(self.deployment_path) or {}
            if deployed and deployed.get('selection') is None and self.target.is_dir() and not self.target.is_symlink():
                marker = read_json(self.target / RESERVED, {})
                if marker.get('transaction') == deployed.get('transaction'):
                    if inventory(self.target)[0] != deployed.get('deployed_sha256'):
                        raise Fault('恢复目录的提交后清理发现外部修改，保留标记等待检查', 409)
                    (self.target / RESERVED).unlink(missing_ok=True)
            self.recovery_error = None
            return
        if (not isinstance(journal, dict) or
                not isinstance(journal.get('transaction'), str) or
                not re.fullmatch(r'[a-f0-9]{24}', journal['transaction']) or
                type(journal.get('had_target')) is not bool or
                journal.get('old') != '.dota-panel-bots-old-' + journal['transaction'] or
                journal.get('new') != '.dota-panel-bots-new-' + journal['transaction'] or
                (journal.get('previous_deployment') is not None and not isinstance(journal['previous_deployment'], dict))):
            raise Fault('机器人部署恢复日志损坏；保留原目录和备份，禁止自动覆盖', 409)
        self._safe_parent()
        old, new = self._backup_path(journal['old']), self._backup_path(journal['new'])
        # An existing target with our transaction marker is the new incomplete
        # deployment. Never delete an unrelated/unmanaged target during recovery.
        if old.exists():
            if self.target.exists():
                marker = read_json(self.target / RESERVED, {})
                if marker.get('transaction') != journal['transaction']:
                    raise Fault('部署中断且 bots 目录已被外部修改；保留所有备份，请按接手文件人工处理', 409)
                shutil.rmtree(self.target)
            os.replace(old, self.target)
        elif journal['had_target']:
            if not self.target.exists() or read_json(self.target / RESERVED, {}).get('transaction') == journal['transaction']:
                raise Fault('部署恢复缺少原目录；禁止自动开服，请保留备份排查', 409)
        elif self.target.exists():
            if read_json(self.target / RESERVED, {}).get('transaction') != journal['transaction']:
                raise Fault('部署恢复发现未知 bots 目录，已停止', 409)
            shutil.rmtree(self.target)
        if new.exists():
            shutil.rmtree(new)
        atomic_json(self.deployment_path, journal.get('previous_deployment'))
        self.journal.unlink()
        self.recovery_error = None

    def prepare_launch(self, override: dict | None = None, use_override: bool = False, observer=None) -> dict | None:
        self.recover()
        selected = self.validate_selection(override if use_override else self._selection().get('selected'))
        deployed = read_json(self.deployment_path) or {}
        if selected is None and not deployed.get('selection'):
            # No managed bot deployment: leave unrelated installations alone.
            return None
        self._safe_parent()
        if self.target.exists() and not self.target.is_dir():
            raise Fault('bots 路径不是目录', 409)
        current_marker = read_json(self.target / RESERVED, {}) if self.target.exists() else {}
        if deployed.get('selection'):
            if not self.target.exists() or current_marker.get('transaction') != deployed.get('transaction'):
                raise Fault('已部署 bots 被替换或删除；禁止覆盖外部改动，请先恢复部署记录', 409)
            if inventory(self.target)[0] != deployed.get('deployed_sha256'):
                raise Fault('已部署 bots 内容被手工修改；请先保存修改，不会静默覆盖', 409)
        elif current_marker:
            raise Fault('bots 含未知的面板部署标记，不能接管', 409)
        if selected is None and not deployed.get('selection'):
            return None
        transaction = secrets.token_hex(12)
        old = self.parent / ('.dota-panel-bots-old-' + transaction)
        new = self.parent / ('.dota-panel-bots-new-' + transaction)
        restore_backup = deployed.get('restore_backup') if deployed.get('selection') else None
        spec = dict(selected) if selected else None
        try:
            if selected:
                source = self._version_path(selected['item_id'], selected['version']) / 'scripts'
                shutil.copytree(source, new)
                spec['probe_token'] = secrets.token_hex(16) if selected['entry_probe'] and (new / 'hero_selection.lua').is_file() else None
                if spec['probe_token']:
                    entry = new / 'hero_selection.lua'
                    data = entry.read_bytes()
                    if data.startswith(b'\xef\xbb\xbf'):
                        data = data[3:]
                    entry.write_bytes(('print("DOTA_PANEL_BOT_ENTRY:' + spec['probe_token'] + ':hero_selection")\n').encode() + data)
                if observer is not None:
                    observer(new, spec)
                if not deployed.get('selection') and self.target.exists():
                    # Preserve the pre-panel directory on its original filesystem.
                    inventory(self.target)
                    restore_backup = old.name
            elif restore_backup:
                backup = self._backup_path(restore_backup)
                if not backup.is_dir():
                    raise Fault('缺少接管前的机器人目录备份，不能恢复', 409)
                inventory(backup)
                shutil.copytree(backup, new)
            # A marker is also written for a restore transaction. It is removed
            # after commit when the restored original becomes unmanaged again.
            if new.exists():
                atomic_json(new / RESERVED, {'transaction': transaction, 'selection': selected})
            result = {'selection': selected, 'transaction': transaction, 'restore_backup': restore_backup,
                      'deployed_at': now(), 'probe_token': spec.get('probe_token') if spec else None,
                      'deployed_sha256': inventory(new)[0] if new.exists() else None}
            journal = {'transaction': transaction, 'old': old.name, 'new': new.name,
                       'had_target': self.target.exists(), 'previous_deployment': deployed or None}
            atomic_json(self.journal, journal)
            if self.target.exists():
                os.replace(self.target, old)
            if new.exists():
                os.replace(new, self.target)
            atomic_json(self.deployment_path, result)
            self.journal.unlink()
            if selected is None and self.target.exists():
                (self.target / RESERVED).unlink(missing_ok=True)
            # Delete only a replaced managed version after committing. Original
            # user directories are retained as restore backups, never erased.
            if old.exists() and deployed.get('selection') and old.name != restore_backup:
                shutil.rmtree(old)
            self.recovery_error = None
            return spec
        except Exception:
            if not self.journal.exists() and new.exists():
                shutil.rmtree(new)
            raise
