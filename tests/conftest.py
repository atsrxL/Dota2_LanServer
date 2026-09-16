from pathlib import Path
import shutil
import socket
import pytest
from panel.common import Paths, DEFAULT_CONFIG, atomic_json

@pytest.fixture
def paths(tmp_path,monkeypatch):
    monkeypatch.setenv('DOTA_TEST_ROOT',str(tmp_path))
    p=Paths.from_env();p.prepare()
    fake_dir=tmp_path/'fixtures';fake_dir.mkdir()
    for f in (Path(__file__).parent/'fakes').glob('*.py'):
        shutil.copy(f,fake_dir/f.name)
    (p.steam/'steamcmd.sh').write_text('#!/bin/bash\nexec python3 "'+str(fake_dir/'fake_steamcmd.py')+'"\n')
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    atomic_json(p.config,DEFAULT_CONFIG | {'port':port})
    return p
