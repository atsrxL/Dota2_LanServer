#!/usr/bin/env python3
"""Package reviewed source/docs only. Never collect production game/cache/config."""
from __future__ import annotations
import argparse
import hashlib
import re
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'.gitignore', 'AGENTS.md', 'CODEX_HANDOFF.md', 'CODEX_LAN_HANDOFF.md', 'LICENSE', 'README.md', 'VERSION',
              'requirements-dev.txt', 'requirements-ui.txt'}
DIRECTORIES = {'config', 'docs', 'install', 'panel', 'pve', 'scripts', 'systemd', 'tests', 'tools', 'addon', 'compat'}


def allowed(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in {'.git', '.venv', '__pycache__', '.pytest_cache', 'node_modules'} for part in rel.parts):
        return False
    if rel.as_posix() == 'pve/lxc.env' or any(any(tag in part for tag in ('.backup-', 'source-backup-', 'compiled-backup-')) for part in rel.parts):
        return False
    if path.suffix in {'.pyc', '.pyo', '.zip', '.key', '.pem'} or '.local.' in path.name:
        return False
    if path.name in {'.env', 'auth.json', 'web.json', 'dota-panel-credentials.txt', 'server.json'}:
        return False
    return (len(rel.parts) == 1 and path.name in ROOT_FILES) or rel.parts[0] in DIRECTORIES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent)
    args = parser.parse_args()
    out = args.output.resolve()
    if out == ROOT or ROOT in out.parents:
        raise SystemExit('Output must be outside the source tree')
    out.mkdir(parents=True, exist_ok=True)
    version = (ROOT/'VERSION').read_text().strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise SystemExit('Invalid VERSION')
    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and allowed(p))
    if any(p.is_symlink() for p in files):
        raise SystemExit('Refusing source symlinks; review the tree first')
    manifest = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n' for p in files)
    manifest_path = ROOT/'SHA256SUMS'
    manifest_path.write_text(manifest, encoding='utf-8')
    target = out/f'dota2-lan-kit-{version}.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files + [manifest_path]:
            name = 'dota2-lan-kit/'+path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 16, 0, 0, 0))
            info.create_system = 3
            executable = path.suffix == '.sh' or path.name == 'dota-cli'
            info.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise SystemExit('ZIP CRC verification failed')
        for line in manifest.splitlines():
            expected, rel = line.split('  ', 1)
            actual = hashlib.sha256(archive.read('dota2-lan-kit/'+rel)).hexdigest()
            if actual != expected:
                raise SystemExit(f'ZIP file hash mismatch: {rel}')
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    Path(str(target)+'.sha256').write_text(f'{digest}  {target.name}\n')
    print(f'{target}\nSource files: {len(files)} + SHA256SUMS\nBytes: {target.stat().st_size}\nSHA256: {digest}\nZIP CRC + every source file SHA-256: PASS')


if __name__ == '__main__':
    main()
