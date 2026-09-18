#!/usr/bin/env python3
"""Fake protocol fixture only. Never connect to Steam or ship game files."""
import os
import sys
import time
from pathlib import Path

def out(s):
    print(s, end='', flush=True)
root = None
out('Steam Console Client — TEST FIXTURE\nSteam>')
while True:
    line=sys.stdin.readline()
    if not line:
        break
    line=line.rstrip('\r\n')
    if line.startswith('force_install_dir '):
        root=Path(line[len('force_install_dir '):].strip('"'))
    elif line.startswith('login '):
        out('password:')
        password=sys.stdin.readline().strip()
        if password=='wrong':
            out('Login Failure: Invalid Password\nSteam>')
            continue
        if password=='needs_guard':
            out('Steam Guard code:')
            guard=sys.stdin.readline().strip()
            if guard!='ABCDE':
                out('Login Failure: Invalid Code\nSteam>')
                continue
        # Intentionally fragment an echoed secret to test streaming redaction.
        out('fixture echo ' + password[:3]); time.sleep(.05); out(password[3:]+'\n')
        out('Logging in user TEST to Steam Public...OK\nWaiting for client config...OK\nWaiting for user info...OK\n')
    elif line.startswith('app_update 570'):
        marker=Path(__file__).parent/'behavior'
        behavior=marker.read_text().strip() if marker.exists() else ''
        if behavior=='slow':
            out('Update state downloading, progress: 1.0\n')
            time.sleep(60)
        elif behavior=='error':
            out("ERROR! Failed to install app '570' (No subscription)\nSteam>")
            continue
        if root is None:
            raise SystemExit(9)
        (root/'game').mkdir(parents=True,exist_ok=True)
        (root/'game/dota.sh').write_text('#!/bin/bash\nexec python3 "'+str(Path(__file__).parent/'fake_dota.py')+'" "$@"\n')
        (root/'steamapps').mkdir(exist_ok=True)
        (root/'steamapps/appmanifest_570.acf').write_text('"AppState" { "appid" "570" "StateFlags" "4" "buildid" "TEST-4242" }')
        out("Update state validating, progress: 100.0\nSuccess! App '570' fully installed.\n")
    elif line.startswith('workshop_download_item 570 '):
        item=line.split()[2]
        marker=Path(__file__).parent/'workshop_behavior'
        behavior=marker.read_text().strip() if marker.exists() else ''
        if behavior=='slow':
            out('Downloading item '+item+' ...\n');time.sleep(60)
        if behavior=='error':
            out('ERROR! Download item failed (Failure).\nSteam>');continue
        target=Path.cwd()/'steamapps/workshop/content/570'/item
        if behavior!='missing':
            target.mkdir(parents=True,exist_ok=True)
            (target/'hero_selection.lua').write_text('-- TEST FIXTURE ONLY\nfunction Think() end\n'+ ('-- changed version\n' if behavior=='changed' else ''))
            (target/'bot_generic.lua').write_text('-- TEST FIXTURE ONLY\nfunction Think() end\n')
            (target/'lib').mkdir(exist_ok=True)
            (target/'lib/data.json').write_text('{"fixture": true}')
        if behavior=='no_success':
            out('Download timed out\nSteam>');continue
        reported='99999' if behavior=='wrong_id' else item
        out('Success. Downloaded item '+reported+' to "'+str(target)+'" (123 bytes)\n')
    elif line=='quit':
        out('Bye\n')
        break
    out('Steam>')
