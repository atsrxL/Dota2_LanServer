#!/usr/bin/env python3
"""Build an offline NSIS installer from validated addon sources and real compiled UI."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from panel.addon_assets import compiled_status
from tools.addon_assets import client_export


def build(source, output, version):
    status = compiled_status(source)
    if not status['ready']:
        raise ValueError(status['reason'])
    output.mkdir(parents=True, exist_ok=True)
    templates = Path(__file__).parent / 'windows-client'
    with tempfile.TemporaryDirectory(prefix='dota-client-build-') as temp:
        root = Path(temp)
        archive = root / 'Dota2-LAN-Client.zip'
        client_export(source, archive)
        shutil.unpack_archive(archive, root / 'payload')
        files = []
        for p in sorted((root / 'payload/game').rglob('*')):
            if p.is_file():
                files.append({'path': p.relative_to(root / 'payload').as_posix(),
                              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        (root / 'payload/files.json').write_text(json.dumps(files), encoding='utf-8')
        # Windows PowerShell 5.1 requires a BOM to recognize Chinese source as UTF-8.
        (root / 'install.ps1').write_text((templates / 'install.ps1').read_text(), encoding='utf-8-sig')
        shutil.copy2(templates / 'installer.nsi', root)
        subprocess.run(['makensis', '-V2', str(root / 'installer.nsi')], cwd=root, check=True)
        entries = {}
        for kind, name in [('exe', 'Dota2-LAN-Client.exe'), ('zip', 'Dota2-LAN-Client.zip')]:
            p = root / name
            data = p.read_bytes()
            if kind == 'exe' and not data.startswith(b'MZ'):
                raise ValueError('NSIS did not produce a Windows executable')
            shutil.copy2(p, output / name)
            entries[kind] = {'name': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        manifest = {'version': version, 'built_at': datetime.now(timezone.utc).isoformat(),
                    'source_sha256': status['source_sha256'], 'ui_source_sha256': status['ui_source_sha256'],
                    'files': entries, 'resource_count': len(files)}
        (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--version', required=True)
    a = p.parse_args()
    print(json.dumps(build(a.source.resolve(), a.output.resolve(), a.version), ensure_ascii=False, indent=2))
