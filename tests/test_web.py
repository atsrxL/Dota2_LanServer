import io
import json
import time
from pathlib import Path
import pytest
from panel.auth import Auth,password_hash,password_matches
from panel.common import Fault,atomic_json
from panel.web import WebApp

@pytest.fixture
def app(tmp_path):
    auth=tmp_path/'auth.json';atomic_json(auth,{'username':'admin','password_hash':password_hash('test-password-12345')})
    def rpc(op,data=None):
        return {'op':op,'data':data}
    return WebApp(auth,rpc_call=rpc)

def request(app,path='/',method='GET',data=None,cookie='',csrf='',origin='https://lan.test',host='lan.test',ip='127.0.0.1',ctype='application/json'):
    body=json.dumps(data).encode() if data is not None else b''
    env={'REQUEST_METHOD':method,'PATH_INFO':path.split('?')[0],'QUERY_STRING':path.split('?',1)[1] if '?' in path else '',
         'HTTP_HOST':host,'HTTP_ORIGIN':origin,'HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf,'REMOTE_ADDR':ip,
         'CONTENT_TYPE':ctype,'CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)}
    captured={}
    def start(status,headers):captured.update(status=int(status[:3]),headers=dict(headers))
    raw=b''.join(app(env,start));captured['raw']=raw
    try:captured['body']=json.loads(raw)
    except ValueError:captured['body']=None
    return captured

def login(app):
    r=request(app,'/api/login','POST',{'username':'admin','password':'test-password-12345'})
    assert r['status']==200
    return r['headers']['Set-Cookie'].split(';')[0],r['body']['csrf']

def test_hashes_and_salts():
    a=password_hash('abc');b=password_hash('abc')
    assert a!=b and password_matches('abc',a) and not password_matches('xyz',a)

@pytest.mark.parametrize('path',['/api/status','/api/config','/api/jobs','/api/logs','/api/backups','/api/diagnostics','/api/backup'])
def test_no_unauthenticated_reads(app,path):
    assert request(app,path)['status']==401

def test_secure_cookie_and_csrf(app):
    r=request(app,'/api/login','POST',{'username':'admin','password':'test-password-12345'})
    flags=r['headers']['Set-Cookie']
    assert all(x in flags for x in ['Secure','HttpOnly','SameSite=Strict'])
    cookie=flags.split(';')[0];csrf=r['body']['csrf']
    assert request(app,'/api/actions','POST',{'action':'start'},cookie)['status']==403
    assert request(app,'/api/actions','POST',{'action':'start'},cookie,csrf)['status']==202
    assert request(app,'/api/actions','POST',{'action':'start'},cookie,csrf,origin='https://evil.example')['status']==403
    assert request(app,'/api/status',cookie=cookie)['status']==200

def test_trusted_lan_mode_creates_http_session_without_password(tmp_path):
    app=WebApp(tmp_path/'missing-auth.json',rpc_call=lambda op,data=None:{'op':op},secure=False,no_auth=True)
    r=request(app,'/api/session',origin='http://lan.test')
    assert r['status']==200 and r['body']['authenticated'] is True and r['body']['no_auth'] is True
    flags=r['headers']['Set-Cookie']
    assert 'HttpOnly' in flags and 'SameSite=Strict' in flags and 'Secure' not in flags
    cookie=flags.split(';')[0];csrf=r['body']['csrf']
    assert request(app,'/api/actions','POST',{'action':'start'},cookie,csrf,origin='http://lan.test')['status']==202
    assert request(app,'/api/actions','POST',{'action':'start'},cookie,csrf,origin='http://evil.example')['status']==403

def test_logout_invalidates_session(app):
    cookie,csrf=login(app)
    assert request(app,'/api/logout','POST',{},cookie,csrf)['status']==200
    assert request(app,'/api/status',cookie=cookie)['status']==401

def test_session_rotation(app):
    old,_=login(app)
    r=request(app,'/api/login','POST',{'username':'admin','password':'test-password-12345'},old)
    assert r['status']==200
    assert request(app,'/api/status',cookie=old)['status']==401

def test_json_and_body_limits(app):
    assert request(app,'/api/login','POST',{'username':'admin','password':'x'},ctype='text/plain')['status']==415
    assert request(app,'/api/login','POST',{'x':'x'*20000})['status']==413
    assert request(app,'/api/login','POST',[])['status']==400

def test_failed_login_rate_limit(app):
    for i in range(8):
        assert request(app,'/api/login','POST',{'username':'admin','password':'wrong'})['status']==401
    assert request(app,'/api/login','POST',{'username':'admin','password':'wrong'})['status']==429

def test_static_no_path_traversal(app):
    cookie,_=login(app)
    assert request(app,'/../../etc/passwd',cookie=cookie)['status']==404
    assert request(app,'/')['status']==200
    assert "frame-ancestors 'none'" in request(app,'/')['headers']['Content-Security-Policy']
    assert b'test-password-12345' not in request(app,'/')['raw']

def test_allowed_hosts(app,tmp_path):
    p=tmp_path/'web.json';atomic_json(p,{'allowed_hosts':['lan.test']});app.settings_file=p
    assert request(app,host='evil.example')['status']==403
    assert request(app,host='lan.test:8443')['status']==200

def test_idle_session_expiry(app):
    cookie,csrf=login(app)
    token=app.auth.token(cookie);app.auth.sessions[token]['last']=time.time()-2000
    assert request(app,'/api/status',cookie=cookie)['status']==401


def test_unicode_login_and_csrf_rejected_cleanly(app):
    assert request(app,'/api/login','POST',{'username':'用户','password':'wrong'})['status']==401
    cookie,csrf=login(app)
    assert request(app,'/api/actions','POST',{'action':'start'},cookie,'非ASCII')['status']==403
