import io
import json
import pytest
from panel.common import atomic_json
from panel.web import WebApp

@pytest.fixture
def app():
    return WebApp(rpc_call=lambda op,data=None: {'op':op,'data':data})

def request(app,path='/',method='GET',data=None,csrf='',origin='http://lan.test',host='lan.test',ctype='application/json',extra=None):
    body=json.dumps(data).encode() if data is not None else b''
    env={'REQUEST_METHOD':method,'PATH_INFO':path.split('?')[0],
         'QUERY_STRING':path.split('?',1)[1] if '?' in path else '',
         'HTTP_HOST':host,'HTTP_ORIGIN':origin,'HTTP_X_CSRF_TOKEN':csrf,
         'CONTENT_TYPE':ctype,'CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)}
    env.update(extra or {})
    captured={}
    def start(status,headers): captured.update(status=int(status[:3]),headers=dict(headers))
    captured['raw']=b''.join(app(env,start))
    try: captured['body']=json.loads(captured['raw'])
    except ValueError: captured['body']=None
    return captured

@pytest.mark.parametrize('path',['/api/metrics','/api/status','/api/config','/api/jobs','/api/logs','/api/backups','/api/diagnostics','/api/backup'])
def test_reads_do_not_need_password_cookie_or_session(app,path):
    r=request(app,path)
    assert r['status']==200
    assert 'Set-Cookie' not in r['headers']

def test_no_login_ui_or_password_initialization(app):
    r=request(app)
    assert r['status']==200
    assert b'loginScreen' not in r['raw'] and b'loginForm' not in r['raw']
    assert b'id="logout"' not in r['raw']
    s=request(app,'/api/session')
    assert s['body']['auth_required'] is False and s['body']['transport']=='http'
    assert len(s['body']['csrf'])>32
    assert 'Set-Cookie' not in s['headers']
    for path in ('/api/login','/api/logout'):
        assert request(app,path,'POST',{})['status']==404

def test_csrf_and_origin_still_required_without_login(app):
    token=request(app,'/api/session')['body']['csrf']
    assert request(app,'/api/actions','POST',{'action':'start'})['status']==403
    assert request(app,'/api/actions','POST',{'action':'start'},token)['status']==202
    for origin in ('http://evil.test','https://lan.test','null','','http://lan.test.evil'):
        assert request(app,'/api/actions','POST',{'action':'start'},token,origin=origin)['status']==403
    assert request(app,'/api/actions','POST',{},token,extra={'HTTP_SEC_FETCH_SITE':'cross-site'})['status']==403
    assert request(app,'/api/actions','POST',{},'非ASCII')['status']==403

def test_json_and_body_limits(app):
    token=app.csrf
    assert request(app,'/api/actions','POST',{},token,ctype='text/plain')['status']==415
    assert request(app,'/api/actions','POST',{'x':'x'*20000},token)['status']==413
    assert request(app,'/api/actions','POST',[],token)['status']==400
    assert request(app,'/api/actions','POST',None,token)['status']==413

def test_no_arbitrary_files_or_methods(app):
    assert request(app,'/../../etc/passwd')['status']==404
    assert request(app,'/auth.json')['status']==404
    assert request(app,'/api/status',method='OPTIONS')['status']==405
    assert "frame-ancestors 'none'" in request(app)['headers']['Content-Security-Policy']
    assert 'Access-Control-Allow-Origin' not in request(app)['headers']

@pytest.mark.parametrize('host',['evil@example','lan.test/path','lan.test?x','lan.test#x','lan.test\\evil','lan.test\n','lan.test:bad','lan.test:65536',''])
def test_malformed_hosts_rejected(app,host):
    assert request(app,host=host)['status']==400

def test_allowed_hosts_rebinding_and_forwarded_headers(app,tmp_path):
    p=tmp_path/'web.json';atomic_json(p,{'allowed_hosts':['lan.test','192.168.1.70']});app.settings_file=p
    assert request(app,host='evil.example')['status']==403
    assert request(app,host='lan.test:8080')['status']==200
    assert request(app,host='lan.test:8443')['status']==200  # port does not imply TLS
    assert request(app,'/api/actions','POST',{},app.csrf,origin='http://lan.test:8080',host='lan.test:8080')['status']==202
    assert request(app,'/api/actions','POST',{},app.csrf,origin='https://lan.test',extra={'HTTP_X_FORWARDED_PROTO':'https'})['status']==403

def test_tokens_rotate_only_on_backend_restart():
    a=WebApp();b=WebApp()
    assert a.csrf!=b.csrf
    assert request(b,'/api/actions','POST',{},a.csrf)['status']==403


def test_workshop_api_and_static_asset_no_auth(app):
    r=request(app,'/api/bots')
    assert r['status']==200 and r['body']['op']=='bots'
    asset=request(app,'/bots.js');assert asset['status']==200
    assert 'textContent' in asset['raw'].decode() and 'innerHTML' not in asset['raw'].decode()
    data={'action':'bot_download','item_id':'1627071163','select_after':True}
    assert request(app,'/api/actions','POST',data,app.csrf)['status']==202
    assert request(app,'/api/actions','POST',data,app.csrf,origin='http://evil.test')['status']==403
    assert request(app,'/api/actions','POST',data)['status']==403


def test_addon_api_http_noauth_and_csrf(app):
    r=request(app,'/api/addon');assert r['status']==200 and r['body']['op']=='addon'
    r=request(app,'/api/addon/report');assert r['status']==200 and 'attachment' in r['headers']['Content-Disposition']
    assert request(app,'/addon.js')['status']==200
    assert request(app,'/api/addon','POST',{'enabled':True})['status']==403
    assert request(app,'/api/addon','POST',{'enabled':True},app.csrf)['status']==200
    assert request(app,'/api/addon','POST',{'enabled':True},app.csrf,origin='http://evil.test')['status']==403
