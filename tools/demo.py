#!/usr/bin/env python3
"""Loopback-only UI development demo with fake game/SteamCMD fixtures.
No real Steam login/download. Never deploy this script or password as a server.
"""
import argparse
import os
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path
from wsgiref.simple_server import make_server
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from panel.agent import Manager
from panel.auth import password_hash
from panel.common import Paths,DEFAULT_CONFIG,atomic_json
from panel.web import WebApp

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8788);args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='dota-panel-demo-') as root:
        os.environ['DOTA_TEST_ROOT']=root
        paths=Paths.from_env();paths.prepare()
        fixtures=Path(root)/'fixtures';shutil.copytree(ROOT/'tests/fakes',fixtures)
        (paths.steam/'steamcmd.sh').write_text('#!/bin/bash\nexec python3 "'+str(fixtures/'fake_steamcmd.py')+'"\n')
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        atomic_json(paths.config,DEFAULT_CONFIG | {'port':port,'hostname':'开发测试 · Dota 2 LAN','steam_username':'tester'})
        manager=Manager(paths)
        manager.submit({'action':'install','username':'tester','password':'test-fixture-only'})
        while manager.active:time.sleep(.05)
        if manager.jobs[-1]['state']!='success':raise SystemExit(manager.jobs[-1])
        manager.submit({'action':'start'})
        while manager.active:time.sleep(.05)
        auth=Path(root)/'auth.json';atomic_json(auth,{'username':'admin','password_hash':password_hash('demo-local-only-12345')})
        app=WebApp(auth,rpc_call=lambda op,data=None:manager.dispatch({'op':op,'data':data or {}}),secure=False)
        print(f'LOCAL TEST FIXTURE ONLY: http://127.0.0.1:{args.port}\nadmin / demo-local-only-12345',flush=True)
        try:
            make_server('127.0.0.1',args.port,app).serve_forever()
        except KeyboardInterrupt:pass
        finally:manager.close()

if __name__=='__main__':main()
