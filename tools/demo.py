#!/usr/bin/env python3
"""Loopback-only UI development demo with fake game/SteamCMD fixtures.
No real Steam login/download. Never deploy this script as a server.
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
from panel.common import Paths,DEFAULT_CONFIG,atomic_json
from panel.web import WebApp
from panel.bots import validate_metadata

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
        def fake_metadata(item):
            return validate_metadata(item, {'publishedfileid': item, 'result': 1, 'consumer_app_id': 570,
                'file_type': 0, 'title': '天地星AI · 测试元数据（非实际下载）', 'tags': [{'tag': 'Bot Scripts'}],
                'file_size': 512, 'time_updated': 1700000000, 'banned': False})
        manager=Manager(paths, workshop_lookup=fake_metadata)
        manager.submit({'action':'install','username':'tester','password':'test-fixture-only'})
        while manager.active:time.sleep(.05)
        if manager.jobs[-1]['state']!='success':raise SystemExit(manager.jobs[-1])
        manager.submit({'action':'start'})
        while manager.active:time.sleep(.05)
        app=WebApp(rpc_call=lambda op,data=None:manager.dispatch({'op':op,'data':data or {}}))
        print(f'LOCAL TEST FIXTURE ONLY: http://127.0.0.1:{args.port} (no panel login)',flush=True)
        try:
            make_server('127.0.0.1',args.port,app).serve_forever()
        except KeyboardInterrupt:pass
        finally:manager.close()

if __name__=='__main__':main()
