#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
for script in pve/*.sh install/*.sh scripts/*.sh; do bash -n "$script"; done
python3 - <<'PY'
import ast
from pathlib import Path
for p in Path('.').rglob('*.py'):
    ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('Python AST / Bash syntax: PASS')
PY
if command -v node >/dev/null; then for js in panel/static/*.js addon/lan_dota/content/panorama/scripts/custom_game/*.js; do node --check "$js"; done; fi
python3 -m pytest -q tests
