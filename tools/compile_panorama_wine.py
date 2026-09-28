#!/usr/bin/env python3
"""Compile the staged Panorama sources with the official Windows resourcecompiler under Wine.

Setup and verified depots are recorded in docs/LINUX_PANORAMA_BUILD.md. Run as the steam
user after `tools/addon_assets.py stage --dota-root <tools-root> --apply`; this tool
only compiles what is already staged and never edits repository files.
"""
from __future__ import annotations
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from panel.addon_assets import ADDON_NAME

TOOLS_ROOT = Path('/srv/steamcmd/linux32/steamapps/content/app_570/depot_381450')
WINEPREFIX = Path('/var/lib/dota2/wine-tools')
WINE = Path('/usr/lib/wine/wine64')
LOG_DIR = Path('/var/lib/dota2')
INPUTS = (
    'layout/custom_game/custom_ui_manifest.xml',
    'layout/custom_game/lan_setup.xml',
    'scripts/custom_game/lan_setup.js',
    'styles/custom_game/lan_setup.css',
)


def command(tools_root: Path, wine: Path, name: str) -> list[str]:
    panorama = tools_root / 'content/dota_addons' / ADDON_NAME / 'panorama'
    return ['xvfb-run', '-a', str(wine), str(tools_root / 'game/bin/win64/resourcecompiler.exe'),
            '-nop4', '-f', '-game', 'Z:' + str(tools_root / 'game/dota'), '-i', 'Z:' + str(panorama / name)]


def compile_all(tools_root: Path = TOOLS_ROOT, wineprefix: Path = WINEPREFIX, wine: Path = WINE,
                log_dir: Path = LOG_DIR, timeout: int = 120) -> list[dict]:
    env = dict(os.environ, WINEPREFIX=str(wineprefix), WINEDEBUG='-all')
    results = []
    for name in INPUTS:
        p = subprocess.run(command(tools_root, wine, name), cwd=tools_root / 'game/bin/win64', env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        log = log_dir / ('compile-' + Path(name).name + '.log')
        log.write_text(p.stdout)
        results.append({'input': name, 'exit': p.returncode, 'log': str(log)})
        # resourcecompiler can exit 0 while reporting failed resources.
        if p.returncode or not re.search(r'OK: [1-9]\d* compiled, 0 failed', p.stdout):
            raise RuntimeError(f'{name} 编译失败（exit {p.returncode}），日志：{log}\n{p.stdout[-2000:]}')
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools-root', type=Path, default=TOOLS_ROOT)
    parser.add_argument('--wineprefix', type=Path, default=WINEPREFIX)
    parser.add_argument('--wine', type=Path, default=WINE)
    parser.add_argument('--log-dir', type=Path, default=LOG_DIR)
    a = parser.parse_args()
    try:
        for r in compile_all(a.tools_root, a.wineprefix, a.wine, a.log_dir):
            print(f"{r['input']}: OK ({r['log']})")
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
