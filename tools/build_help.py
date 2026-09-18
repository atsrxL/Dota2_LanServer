#!/usr/bin/env python3
"""Build offline and panel help from controlled project Markdown; stdlib only."""
import html
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def inline(text):
    text=html.escape(text)
    return re.sub(r'`([^`]+)`',r'<code>\1</code>',text)

def convert(text):
    out=[];paragraph=[];code=[];in_code=False;table=[]
    def flush_p():
        if paragraph:
            out.append('<p>'+inline(' '.join(paragraph))+'</p>');paragraph.clear()
    def flush_table():
        if table:
            out.append('<table>')
            for i,row in enumerate(table):
                if all(re.fullmatch(r'[: -]+',c.strip()) for c in row):continue
                tag='th' if i==0 else 'td'
                out.append('<tr>'+''.join(f'<{tag}>{inline(c.strip())}</{tag}>' for c in row)+'</tr>')
            out.append('</table>');table.clear()
    for line in text.splitlines():
        if line.startswith('```'):
            flush_p();flush_table()
            if in_code:out.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>');code=[]
            in_code=not in_code;continue
        if in_code:code.append(line);continue
        if line.startswith('|'):
            flush_p();table.append(line.strip('|').split('|'));continue
        flush_table()
        m=re.match(r'^(#{1,3}) (.*)',line)
        if m:
            flush_p();n=len(m[1]);anchor='section-'+str(len(out));out.append(f'<h{n} id="{anchor}">{inline(m[2])}</h{n}>')
        elif not line.strip():flush_p()
        else:paragraph.append(line)
    flush_p();flush_table()
    return '\n'.join(out)

version=(ROOT/'VERSION').read_text().strip()
body=convert((ROOT/'docs/HELP.md').read_text())
base='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dota 2 LAN · 使用帮助</title>{style}</head><body><main class="help-shell"><p class="eyebrow">DOTA 2 LAN KIT / DOCUMENTATION / V1.1.0</p><a href="/">← 返回控制中心</a>{body}<footer>本地自托管 · 真实联机能力按现场验收确认</footer></main></body></html>'
(ROOT/'panel/static/help.html').write_text(base.replace('V1.1.0', 'V'+version).replace('{style}','<link rel="stylesheet" href="/style.css">').replace('{body}',body))
css=(ROOT/'panel/static/style.css').read_text()
(ROOT/'docs/HELP.html').write_text(base.replace('V1.1.0', 'V'+version).replace('{style}','<style>'+css+'</style>').replace('{body}',body).replace('<a href="/">← 返回控制中心</a>','<p class="muted">离线帮助 · 完整部署步骤见同目录 DEPLOYMENT.md</p>'))
print('Help pages built from docs/HELP.md')
