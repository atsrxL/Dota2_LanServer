#!/usr/bin/env python3
"""One-command server release: stage -> Wine compile -> collect -> import -> client package.

Every step must succeed before the next starts, so the server source, compiled UI and the
downloadable Windows package always come from the same source identity. With --restart the
game server is restarted, which deploys the current source (lan_addon deploys on launch).

Run as root on the server. Staging and compiling run as --tools-user because the Workshop
Tools root and Wine prefix belong to that user.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from panel.addon_assets import compiled_status
from panel.common import Fault
from tools import addon_assets, compile_panorama_wine
from tools.build_windows_client import build

CLIENT_OUTPUT = Path('/opt/dota2-lan-kit/client-downloads')
ARTIFACTS = Path('/var/lib/dota2/artifacts')
RELEASE_MARKER = 'release.json'


def prune(paths: list[Path], keep: int) -> list[Path]:
    """Delete all but the newest `keep` paths (by mtime); returns what was removed."""
    ordered = sorted(paths, key=lambda p: p.stat().st_mtime)
    removed = ordered[:-keep] if keep > 0 else ordered
    for p in removed:
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    return removed


def archive_release(artifacts: Path, version: str, compiled_zip: Path, client_output: Path,
                    result: dict, keep: int) -> Path:
    """Keep this release's compiled UI and client package for rollback; rotate our own releases only."""
    target = artifacts / version
    if target.exists():
        raise Fault(f'发布目录已存在：{target}；换一个版本号', 409)
    target.mkdir(parents=True)
    shutil.copy2(compiled_zip, target / compiled_zip.name)
    for name in ('Dota2-LAN-Client.exe', 'Dota2-LAN-Client.zip', 'manifest.json'):
        if (client_output / name).is_file():
            shutil.copy2(client_output / name, target / name)
    (target / RELEASE_MARKER).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    # Directories without the marker (e.g. hand-made ones) are never touched.
    prune([p for p in artifacts.iterdir() if (p / RELEASE_MARKER).is_file()], keep)
    return target


def as_user(user: str | None, args: list[str]) -> None:
    if user and os.geteuid() == 0:
        args = ['runuser', '-u', user, '--'] + args
    subprocess.run(args, check=True)


def release(version: str, source: Path, tools_root: Path, client_output: Path,
            tools_user: str | None, restart: bool, log=print,
            artifacts: Path | None = None, keep: int = 3) -> dict:
    py = sys.executable
    if artifacts and (artifacts / version).exists():
        raise Fault(f'版本 {version} 已发布过；换一个版本号', 409)
    log('1/5 stage UI sources into Workshop Tools root')
    as_user(tools_user, [py, str(ROOT / 'tools/addon_assets.py'), '--source', str(source), 'stage',
                         '--dota-root', str(tools_root), '--apply', '--replace-managed'])
    # stage() keeps the previous copy beside the target; it only held verified release sources.
    as_user(tools_user, ['find', str(tools_root / 'game/dota_addons'), str(tools_root / 'content/dota_addons'),
                         '-maxdepth', '1', '-name', addon_assets.ADDON_NAME + '.source-backup-*',
                         '-exec', 'rm', '-rf', '{}', '+'])
    log('2/5 compile Panorama with resourcecompiler (Wine)')
    as_user(tools_user, [py, str(ROOT / 'tools/compile_panorama_wine.py'), '--tools-root', str(tools_root)])
    with tempfile.TemporaryDirectory(prefix='dota-release-') as temp:
        archive = Path(temp) / f'lan-dota-{version}-compiled.zip'
        log('3/5 collect and validate compiled resources')
        addon_assets.collect(source, tools_root, archive)
        log('4/5 import compiled resources into server source')
        addon_assets.import_assets(source, archive, apply=True, replace_invalid=True)
        status = compiled_status(source)
        if not status['ready']:
            raise Fault(status['reason'], 409)
        log('5/5 build Windows client installer')
        manifest = build(source, client_output, version)
        result = {'version': version, 'source_sha256': status['source_sha256'], 'client': manifest['files'],
                  'restarted': False}
        if artifacts:
            result['artifacts'] = str(archive_release(artifacts, version, archive, client_output, result, keep))
    # import_assets keeps the replaced compiled set beside the source; keep only the newest few.
    prune(list(source.parent.glob(source.name + '.compiled-backup-*')), keep)
    if restart:
        from panel.agent import rpc
        job = rpc('submit', {'action': 'restart'})
        result.update(restarted=True, restart_job=job.get('id'))
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', required=True, help='release label shown in the panel, e.g. r25')
    p.add_argument('--source', type=Path, default=addon_assets.SOURCE)
    p.add_argument('--tools-root', type=Path, default=compile_panorama_wine.TOOLS_ROOT)
    p.add_argument('--client-output', type=Path, default=CLIENT_OUTPUT)
    p.add_argument('--tools-user', default='steam')
    p.add_argument('--restart', action='store_true', help='restart the game server to deploy this source')
    p.add_argument('--artifacts', type=Path, default=ARTIFACTS, help='per-release copies for rollback')
    p.add_argument('--keep', type=int, default=3, help='releases and compiled backups to keep')
    a = p.parse_args()
    try:
        result = release(a.version, a.source.resolve(), a.tools_root, a.client_output.resolve(),
                         a.tools_user, a.restart, artifacts=a.artifacts, keep=a.keep)
    except (Fault, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not a.restart:
        print('服务器尚未重启：重启游戏服务器后才会部署本次源码。', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
