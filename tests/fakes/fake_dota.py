#!/usr/bin/env python3
"""Process/PTY integration fixture; not a game server."""
import socket
import re
from pathlib import Path
import sys
args=sys.argv[1:]
port=int(args[args.index('-port')+1]) if '-port' in args else 27999
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.bind(('127.0.0.1',port))
print('TEST FIXTURE: game process alive, not a real Dota 2 server',flush=True)
for line in sys.stdin:
    if line.strip()=='quit':
        print('TEST FIXTURE: clean shutdown',flush=True)
        break
    print('TEST FIXTURE console: '+line.strip(),flush=True)
    if line.strip()=='dota_bot_populate':
        entry=Path.cwd()/'dota/scripts/vscripts/bots/hero_selection.lua'
        if entry.is_file():
            match=re.match(r'print\("(DOTA_PANEL_BOT_ENTRY:[a-f0-9]+:hero_selection)"\)',entry.read_text())
            if match:
                print(match[1],flush=True)  # Test fixture marker, not Lua execution.

s.close()
