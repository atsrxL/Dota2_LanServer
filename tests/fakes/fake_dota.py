#!/usr/bin/env python3
"""Process/PTY integration fixture; not a game server."""
import socket
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
s.close()
