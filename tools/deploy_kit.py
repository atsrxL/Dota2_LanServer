#!/usr/bin/env python3
"""Install a packaged kit ZIP (scripts/package.py) on the server, traceably.

Run as root on the server. Standalone on purpose: the first run may use a copy taken out
of the archive itself:

    unzip -p dota2-lan-kit-1.3.0.zip dota2-lan-kit/tools/deploy_kit.py > /tmp/deploy_kit.py
    python3 /tmp/deploy_kit.py --archive dota2-lan-kit-1.3.0.zip

Steps: verify every file against SHA256SUMS -> refuse while humans are connected (restarting
the agent ends the match) -> back up the managed paths (newest --keep kept) -> swap managed
directories -> write DEPLOYED.json -> restart panel and agent -> start the game again if it
was running and the compiled UI still matches. Server config, client downloads and the
compiled UI are never touched; a UI source change needs tools/release.py afterwards.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

PREFIX = 'dota2-lan-kit/'
MANAGED_DIRS = ('panel', 'tools', 'docs', 'scripts', 'addon/lan_dota/game', 'addon/lan_dota/content')
MANAGED_FILES = ('README.md', 'VERSION', 'BUILD.json', 'SHA256SUMS', 'AGENTS.md')
SERVICES = ('dota-agent', 'dota-panel')


class DeployError(Exception):
    pass


def read_archive(archive: Path) -> tuple[dict[str, bytes], dict]:
    """Return {relative path: bytes} for verified files plus the BUILD.json record."""
    files = {}
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            rel = PurePosixPath(name[len(PREFIX):]) if name.startswith(PREFIX) else None
            if rel is None or rel.is_absolute() or '..' in rel.parts or not rel.parts:
                raise DeployError('压缩包路径无效: ' + name)
            files[rel.as_posix()] = z.read(info)
    if 'SHA256SUMS' not in files or 'BUILD.json' not in files:
        raise DeployError('压缩包缺少 SHA256SUMS 或 BUILD.json；请用 scripts/package.py 打包')
    listed = {}
    for line in files['SHA256SUMS'].decode().splitlines():
        digest, rel = line.split('  ', 1)
        listed[rel] = digest
    for rel, digest in listed.items():
        if rel not in files or hashlib.sha256(files[rel]).hexdigest() != digest:
            raise DeployError('文件校验失败: ' + rel)
    # BUILD.json is metadata written at packaging time and only parsed as JSON.
    unlisted = set(files) - set(listed) - {'SHA256SUMS', 'BUILD.json'}
    if unlisted:
        raise DeployError('压缩包含未列入 SHA256SUMS 的文件: ' + ', '.join(sorted(unlisted)[:5]))
    build = json.loads(files['BUILD.json'])
    if not isinstance(build.get('commit'), str):
        raise DeployError('BUILD.json 缺少提交号')
    return files, build


def connected_humans(kit: Path) -> int | None:
    """Human players the running game reports; None when it cannot be determined."""
    sys.path.insert(0, str(kit))
    try:
        from panel.agent import rpc
        addon = rpc('addon')
    except Exception:
        return None
    finally:
        sys.path.remove(str(kit))
    state = ((addon or {}).get('runtime') or {}).get('state') or {}
    return sum(1 for p in state.get('players', []) if p.get('connected'))


def game_running(kit: Path) -> bool:
    sys.path.insert(0, str(kit))
    try:
        from panel.agent import rpc
        return bool(rpc('status').get('running'))
    except Exception:
        return False
    finally:
        sys.path.remove(str(kit))


def backup(kit: Path, backups: Path, keep: int, label: str) -> Path:
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    target = backups / f'kit-{stamp}-{label}.tgz'
    with tarfile.open(target, 'w:gz') as tar:
        for rel in MANAGED_DIRS + MANAGED_FILES + ('DEPLOYED.json',):
            if (kit / rel).exists():
                tar.add(kit / rel, arcname=rel, filter=lambda t: None if '__pycache__' in t.name else t)
    # Only files this tool created (kit-*.tgz) are rotated.
    for old in sorted(backups.glob('kit-*.tgz'))[:-keep]:
        old.unlink()
    return target


def install(kit: Path, files: dict[str, bytes]) -> None:
    stamp = str(time.time_ns())
    staging = kit / f'.deploy-{stamp}'
    staging.mkdir()
    try:
        for rel, data in files.items():
            p = staging / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            p.chmod(0o755 if p.suffix == '.sh' or p.name == 'dota-cli' else 0o644)
        for rel in MANAGED_DIRS:
            if not (staging / rel).is_dir():
                raise DeployError('压缩包缺少目录: ' + rel)
        retired, placed = [], []
        try:
            for rel in MANAGED_DIRS:
                new, live = staging / rel, kit / rel
                if live.exists():
                    old = kit / f'.retired-{stamp}' / rel
                    old.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(live, old)
                    retired.append((old, live))
                live.parent.mkdir(parents=True, exist_ok=True)
                os.replace(new, live)
                placed.append(live)
        except BaseException:
            # Put every previous directory back before reporting the failure.
            for live in placed:
                shutil.rmtree(live, ignore_errors=True)
            for old, live in retired:
                os.replace(old, live)
            raise
        for rel in MANAGED_FILES:
            if (staging / rel).is_file():
                os.replace(staging / rel, kit / rel)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(kit / f'.retired-{stamp}', ignore_errors=True)


def ui_ready(kit: Path) -> bool:
    code = 'from panel.addon_assets import compiled_status; from pathlib import Path; import sys; ' \
           'sys.exit(0 if compiled_status(Path("addon/lan_dota"))["ready"] else 1)'
    return subprocess.run([sys.executable, '-c', code], cwd=kit).returncode == 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--kit', type=Path, default=Path('/opt/dota2-lan-kit'))
    p.add_argument('--backups', type=Path, default=Path('/var/lib/dota2/kit-backups'))
    p.add_argument('--keep', type=int, default=3)
    p.add_argument('--force', action='store_true', help='deploy even while players are connected')
    p.add_argument('--no-restart', action='store_true', help='do not restart services or the game')
    a = p.parse_args()
    try:
        archive_bytes = a.archive.read_bytes()
        files, build = read_archive(io.BytesIO(archive_bytes))
        humans = connected_humans(a.kit)
        if humans and not a.force and not a.no_restart:
            raise DeployError(f'有 {humans} 名玩家在线；重启代理会结束对局。结束后再部署，或加 --force')
        was_running = game_running(a.kit)
        saved = backup(a.kit, a.backups, a.keep, build['commit'][:12])
        install(a.kit, files)
        deployed = {**build, 'deployed_at': datetime.now(timezone.utc).isoformat(),
                    'archive_sha256': hashlib.sha256(archive_bytes).hexdigest()}
        (a.kit / 'DEPLOYED.json').write_text(json.dumps(deployed, ensure_ascii=False, indent=2))
        print(f'已部署 {build["commit"][:12]}{"（含未提交改动）" if build.get("dirty") else ""}；备份 {saved}')
        if a.no_restart:
            print('未重启服务：面板和代理仍在运行旧代码。')
            return 0
        subprocess.run(['systemctl', 'restart', *SERVICES], check=True)
        time.sleep(3)
        if not ui_ready(a.kit):
            print('UI 源码已变化，编译资源不再匹配：运行 tools/release.py --version <版本> --restart。')
        elif was_running:
            sys.path.insert(0, str(a.kit))
            from panel.agent import rpc
            job = rpc('submit', {'action': 'start'})
            print('游戏服务器已重新启动，任务 ' + job['id'])
    except (DeployError, OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
