#!/usr/bin/env python3
"""Validate deployment JSON and generate narrowly scoped nginx/PVE configuration."""
import ipaddress
import json
import re
import sys
from pathlib import Path


def validate(raw):
    d = dict(raw)
    d['ip'] = str(ipaddress.IPv4Address(d['ip']))
    d['lan_cidrs'] = [str(ipaddress.IPv4Network(c, strict=False)) for c in d['lan_cidrs']]
    if not d['lan_cidrs'] or any(ipaddress.IPv4Network(c).prefixlen < 8 for c in d['lan_cidrs']):
        raise ValueError('LAN 白名单不能为空或过宽')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,62}', d['hostname']):
        raise ValueError('hostname 无效')
    for key in ('panel_port', 'game_port'):
        if type(d[key]) is not int or not 1024 <= d[key] <= 65535:
            raise ValueError('端口范围无效')
    if not re.fullmatch(r'[A-Za-z0-9_+/-]+', d['timezone']) or '..' in d['timezone']:
        raise ValueError('timezone 无效')
    digest = d.get('steamcmd_sha256', '')
    if digest and not re.fullmatch(r'[a-fA-F0-9]{64}', digest):
        raise ValueError('SteamCMD sha256 无效')
    return d


def firewall(d):
    lines = ['# Managed by dota2-lan-kit. Only this CT; no cluster-wide switches.', '[OPTIONS]',
             'enable: 1', 'policy_in: DROP', 'policy_out: ACCEPT', 'dhcp: 1', '', '[RULES]']
    for cidr in d['lan_cidrs']:
        lines += [f'IN ACCEPT -source {cidr} -p tcp -dport {d["panel_port"]}',
                  f'IN ACCEPT -source {cidr} -p udp -dport {d["game_port"]}',
                  f'IN ACCEPT -source {cidr} -p icmp']
    return '\n'.join(lines) + '\n'


def nginx(d):
    allow = '\n'.join(f'    allow {c};' for c in d['lan_cidrs'])
    return f'''# Local management endpoint; trusted-LAN HTTP, no public listener.
server {{
    listen {d['panel_port']};
    server_name _;
    server_tokens off;
    client_max_body_size 16k;
    client_body_timeout 15s;
    client_header_timeout 15s;
    keepalive_timeout 20s;
{allow}
    allow 127.0.0.1;
    deny all;
    access_log /var/log/nginx/dota-panel.access.log;
    error_log /var/log/nginx/dota-panel.error.log warn;
    location / {{
        proxy_pass http://127.0.0.1:8765;
        include /etc/nginx/snippets/dota-proxy.conf;
    }}
}}
'''


def main():
    mode, src, *rest = sys.argv[1:]
    d = validate(json.loads(Path(src).read_text()))
    if mode == 'validate':
        print(json.dumps(d, ensure_ascii=False))
        return
    if mode == 'field':
        value = d[rest[0]]
        print(value if not isinstance(value, (dict, list)) else json.dumps(value))
        return
    text = firewall(d) if mode == 'firewall' else nginx(d) if mode == 'nginx' else None
    if text is None:
        raise SystemExit('mode must be validate/field/firewall/nginx')
    Path(rest[0]).write_text(text)

if __name__ == '__main__':
    main()
