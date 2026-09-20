#!/usr/bin/env python3
"""Browser smoke test ONLY against tools/demo.py on loopback. Requires playwright.
Start demo.py in another terminal. Never point this at a production instance.
"""
import argparse
import json
import shutil
import http.cookiejar
import urllib.request
import urllib.error
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8788)
    parser.add_argument('--offline-transport', action='store_true', help='Render DOM offline and bridge fetch through Python to the loopback demo; not browser HTTP/TLS E2E')
    parser.add_argument('--output', type=Path, default=Path('docs'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results, errors = [], []
    base = f'http://127.0.0.1:{args.port}'
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    static = Path(__file__).resolve().parents[1]/'panel/static'
    def http_call(path, options=None):
        options = options or {}
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('Only fixed loopback demo paths are allowed')
        headers = dict(options.get('headers', {}))
        headers['Origin'] = base
        data = options.get('body')
        req = urllib.request.Request(base+path, data=data.encode() if isinstance(data,str) else None,
                                     method=options.get('method','GET'), headers=headers)
        try:
            response = opener.open(req, timeout=20)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return {'body': response.read().decode('utf-8'), 'status': response.status, 'headers': dict(response.headers)}
    def offline_html(page, name):
        html = (static/name).read_text().replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/app.js" defer></script>','').replace('<script src="/metrics.js" defer></script>','').replace('<script src="/bots.js" defer></script>','').replace('<script src="/addon.js" defer></script>','')
        page.set_content(html)
        page.add_style_tag(content=(static/'style.css').read_text())

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which('chromium') or None,
                                     headless=True, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1440, 'height': 1080})
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        if args.offline_transport:
            page.expose_binding('__demoHttp', lambda source,path,options=None: http_call(path,options))
            offline_html(page, 'index.html')
            page.evaluate('''() => { window.fetch = async (url, options={}) => {
              const r=await window.__demoHttp(url,options);
              return new Response(r.body,{status:r.status,headers:r.headers});
            }; }''')
            page.add_script_tag(content=(static/'app.js').read_text())
            page.add_script_tag(content=(static/'metrics.js').read_text())
            page.add_script_tag(content=(static/'addon.js').read_text())
        else:
            page.goto(base, wait_until='networkidle')
        assert page.locator('#loginScreen').count() == 0
        assert page.locator('#loginForm').count() == 0
        assert page.locator('#logout').count() == 0
        results.append('HTTP dashboard has no panel login or logout controls')
        expect(page.locator('#application')).to_be_visible()
        expect(page.locator('#serverName')).to_contain_text('开发测试')
        expect(page.locator('#buildId')).to_have_text('TEST-4242')
        expect(page.locator('#serverState')).to_contain_text('游戏进程运行中')
        results.append('Passwordless dashboard shows real fake-process status / test Build ID')
        expect(page.locator('#resourceMonitor')).to_be_visible()
        expect(page.locator('#resourceState')).to_contain_text('实时',timeout=10000)
        expect(page.locator('#cpuPercent')).not_to_have_text('—')
        expect(page.locator('#memoryBytes')).to_contain_text('GiB')
        visible_metrics = json.loads(http_call('/api/metrics')['body'])
        assert page.locator('.cpu-core').count() == len(visible_metrics['cpu']['per_core'])
        expect(page.locator('#cpuScope')).to_contain_text('cgroup')
        results.append('Live total CPU, visible per-core bars, memory, sources and quota render')
        page.wait_for_function("document.getElementById('cpuHistory').getAttribute('d').includes('L')",timeout=12000)
        results.append('Two-minute resource history accumulates real samples in the browser')
        page.evaluate("""() => {
          window.__realMetricsFetch = window.fetch;
          window.fetch = (url,options) => url === '/api/metrics'
            ? Promise.resolve(new Response('{"error":"test fixture outage"}',{status:503}))
            : window.__realMetricsFetch(url,options);
        }""")
        expect(page.locator('#resourceState')).to_contain_text('暂不可用',timeout=10000)
        expect(page.locator('#cpuPercent')).to_have_text('—')
        expect(page.locator('#memoryPercent')).to_have_text('—')
        expect(page.locator('#cpuCores')).to_contain_text('数据已失效')
        page.evaluate('() => { window.fetch = window.__realMetricsFetch; }')
        expect(page.locator('#resourceState')).to_contain_text('实时',timeout=10000)
        results.append('Metrics outage clears stale live numbers and reconnects automatically')
        page.evaluate("""() => {
          Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
        expect(page.locator('#resourceState')).to_have_text('已暂停')
        page.evaluate("""() => {
          delete document.hidden;
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
        expect(page.locator('#resourceState')).to_contain_text('实时',timeout=10000)
        results.append('Synthetic page-visibility event pauses and resumes resource polling')
        if args.offline_transport:
            page.locator('#connectCommand').evaluate("e=>e.textContent='connect 127.0.0.1:测试端口（模拟）'")
        page.screenshot(path=str(args.output/'panel-preview.png'), full_page=True)
        page.locator('[data-page="steam"]').click()
        expect(page.locator('#steam')).to_be_visible()
        page.locator('#steamPass').fill('browser-fixture-secret')
        page.locator('[data-action="login"]').click()
        expect(page.locator('#steamPass')).to_have_value('')
        expect(page.locator('#steamLog')).to_contain_text('Waiting for user info...OK', timeout=15000)
        assert 'browser-fixture-secret' not in page.locator('#steamLog').inner_text()
        results.append('Steam action submitted; secret cleared and redacted from output')
        page.locator('[data-page="jobs"]').click()
        expect(page.locator('#jobTable')).to_contain_text('Steam 登录')
        results.append('Task history updates')
        page.locator('[data-page="logs"]').click()
        expect(page.locator('#mainLog')).to_contain_text('TEST FIXTURE')
        page.locator('[data-command="status"]').click()
        expect(page.locator('#mainLog')).to_contain_text('status', timeout=10000)
        results.append('Server logs and restricted console preset operate')
        page.locator('[data-page="settings"]').click()
        expect(page.locator('[name="hostname"]')).to_have_value('开发测试 · Dota 2 LAN')
        results.append('Settings form loads stored values')
        page.locator('[data-page="backups"]').click()
        page.locator('[data-action="backup"]').click()
        expect(page.locator('#backupList')).to_contain_text('cfg-', timeout=10000)
        results.append('Configuration backup appears in UI')
        if args.offline_transport:
            response = http_call(page.locator('a[href="/api/diagnostics"]').get_attribute('href'))
            assert response['status']==200 and 'attachment' in response['headers']['Content-Disposition']
            diagnostic = json.loads(response['body'])
        else:
            with page.expect_download() as download:
                page.locator('a[href="/api/diagnostics"]').click()
            diagnostic = json.loads(Path(download.value.path()).read_text())
        assert diagnostic['status']['running'] is True
        results.append('Passwordless diagnostics download is valid JSON')
        assert page.locator('[data-page="bots"]').count() == 0
        assert page.locator('[data-command="bots"]').count() == 0
        results.append('Archived Bot controls are absent')
        assert page.locator('#addonForm').count() == 0
        help_page = context.new_page()
        if args.offline_transport:
            assert http_call('/help')['status']==200
            offline_html(help_page, 'help.html')
        else:
            help_page.goto(base+'/help', wait_until='networkidle')
        expect(help_page.locator('body')).to_contain_text('Steam Guard')
        assert help_page.locator('h1').count() >= 1
        results.append('Served help page renders with Steam Guard guidance')
        help_page.close()
        page.locator('[data-page="overview"]').click()
        page.set_viewport_size({'width': 390, 'height': 844})
        expect(page.locator('#serverName')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        results.append('390px mobile viewport has no horizontal page overflow')
        page.screenshot(path=str(args.output/'panel-mobile-preview.png'), full_page=True)
        assert (http_call('/api/status')['status'] if args.offline_transport else page.request.get(base+'/api/status').status) == 200
        results.append('State API does not require a password or cookie')
        assert not errors, errors
        results.append('No uncaught JavaScript page errors')
        browser.close()
    report = {'scope': 'Loopback development demo with fake SteamCMD and fake Dota only; not PVE or actual multiplayer',
              'transport': 'Offline DOM + real loopback HTTP via Python; browser navigation/TLS NOT TESTED' if args.offline_transport else 'Browser loopback HTTP',
              'checks_passed': len(results), 'checks': results, 'page_errors': errors}
    (args.output/'ui-test-output.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
