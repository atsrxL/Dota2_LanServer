#!/usr/bin/env bash
# Run ONLY inside the dedicated Ubuntu 24.04 amd64 LXC, as root.
set -Eeuo pipefail
umask 022
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
CONFIG=/root/dota2-bootstrap.json
while (($#)); do
  case "$1" in
    --config) [[ $# -ge 2 ]] || exit 2; CONFIG=$2; shift 2 ;;
    -h|--help) echo 'bash install/bootstrap.sh --config /root/dota2-bootstrap.json'; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done
[[ $EUID -eq 0 ]] || { echo '须以 LXC root 执行'; exit 1; }
[[ ! -e /etc/pve/local/pve-ssl.pem ]] || { echo '拒绝在 PVE 宿主安装'; exit 1; }
# shellcheck disable=SC1091
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 && $(uname -m) == x86_64 ]] || { echo '仅支持 Ubuntu 24.04 amd64'; exit 1; }
[[ -f "$CONFIG" ]] || { echo '缺少 bootstrap.json，见 install/bootstrap.example.json'; exit 1; }
python3 "$SOURCE/install/render.py" validate "$CONFIG" >/dev/null
if systemctl is-active --quiet dota-agent.service; then
  ( cd /opt/dota2-lan-kit; python3 - <<'PY'
from panel.agent import rpc
s=rpc('status')
if s['running'] or s['active_job']:
    raise SystemExit('游戏/任务仍在运行，先停服并结束任务，再重新安装环境。')
PY
  )
  systemctl stop dota-panel.service dota-agent.service
fi
printf '\n==> 安装 Ubuntu 仓库依赖\n'
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 update
apt-get install -y --no-install-recommends software-properties-common
add-apt-repository -y universe
apt-get -o Acquire::Retries=3 update
apt-get install -y --no-install-recommends \
  ca-certificates curl tar xz-utils unzip locales python3 python3-waitress python3-pexpect \
  nginx lib32gcc-s1 lib32stdc++6 libc6-i386 \
  libcurl4t64 libtinfo6 libncurses6 libsdl2-2.0-0 libvulkan1 libx11-6 libxext6 \
  libxrandr2 libxi6 libxrender1 libasound2t64 libfontconfig1 libfreetype6 libglib2.0-0t64 \
  libbz2-1.0 libnss3 libxss1 zlib1g file procps iproute2 util-linux rsync
TZ_VALUE=$(python3 "$SOURCE/install/render.py" field "$CONFIG" timezone)
timedatectl set-timezone "$TZ_VALUE"
getent group dota-control >/dev/null || groupadd --system dota-control
getent group dotapanel >/dev/null || groupadd --system dotapanel
id steam >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/dota2 --shell /usr/sbin/nologin steam
id dotapanel >/dev/null 2>&1 || useradd --system --gid dotapanel --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin dotapanel
# Refuse to repurpose an unrelated pre-existing Steam account/home.
[[ $(getent passwd steam | cut -d: -f6) == /var/lib/dota2 ]] || { echo '已有 steam 用户 home 不匹配；请使用专用全新 LXC'; exit 1; }
usermod -aG dota-control dotapanel
install -d -o steam -g steam -m 0700 /var/lib/dota2
install -d -o steam -g steam -m 0750 /srv/dota2 /srv/steamcmd
install -d -o root -g root -m 0755 /opt/dota2-lan-kit
install -d -o root -g dotapanel -m 0750 /etc/dota-panel
# Game/cache/state are outside the code tree and are NEVER --delete targets.
rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' "$SOURCE/panel/" /opt/dota2-lan-kit/panel/
for dir in docs config; do rsync -a --delete "$SOURCE/$dir/" "/opt/dota2-lan-kit/$dir/"; done
cp "$SOURCE/README.md" "$SOURCE/AGENTS.md" "$SOURCE/CODEX_HANDOFF.md" /opt/dota2-lan-kit/
chown -R root:root /opt/dota2-lan-kit
find /opt/dota2-lan-kit -type d -exec chmod 0755 {} +
find /opt/dota2-lan-kit -type f -exec chmod 0644 {} +
install -m 0755 "$SOURCE/scripts/dota-cli" /usr/local/bin/dota-cli
if [[ ! -f /srv/steamcmd/steamcmd.sh ]]; then
  printf '\n==> 获取 Valve 官方 SteamCMD 安装器（不以 root 启动 SteamCMD）\n'
  ARCHIVE=$(mktemp /var/lib/dota2/steamcmd-XXXXXX.tar.gz)
  curl --proto '=https' --tlsv1.2 --fail --location --retry 3 \
    https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz -o "$ARCHIVE"
  EXPECTED=$(python3 "$SOURCE/install/render.py" field "$CONFIG" steamcmd_sha256)
  ACTUAL=$(sha256sum "$ARCHIVE" | awk '{print $1}')
  [[ -z "$EXPECTED" || "${EXPECTED,,}" == "$ACTUAL" ]] || { rm -f "$ARCHIVE"; echo 'SteamCMD 安装器校验失败'; exit 1; }
  python3 - "$ARCHIVE" <<'PY'
import sys, tarfile
from pathlib import PurePosixPath
with tarfile.open(sys.argv[1]) as t:
    for m in t.getmembers():
        p=PurePosixPath(m.name)
        if p.is_absolute() or '..' in p.parts or m.issym() or m.islnk() or m.isdev():
            raise SystemExit('拒绝包含不安全路径/链接/设备的安装器归档')
PY
  chown steam:steam "$ARCHIVE"; chmod 0600 "$ARCHIVE"
  runuser -u steam -- tar -xzf "$ARCHIVE" --no-same-owner -C /srv/steamcmd
  rm -f "$ARCHIVE"
  printf '%s  steamcmd_linux.tar.gz\n' "$ACTUAL" > /etc/dota-panel/steamcmd-installer.sha256
fi
install -d -o steam -g steam -m 0700 /var/lib/dota2/.steam /var/lib/dota2/.steam/sdk32 /var/lib/dota2/.steam/sdk64
ln -sfn /srv/steamcmd/linux64/steamclient.so /var/lib/dota2/.steam/sdk64/steamclient.so
ln -sfn /srv/steamcmd/linux32/steamclient.so /var/lib/dota2/.steam/sdk32/steamclient.so
chown -h steam:steam /var/lib/dota2/.steam/sdk{32,64}/steamclient.so
printf '\n==> 初始化游戏配置与受信任 LAN HTTP 面板\n'
cd /opt/dota2-lan-kit
python3 - "$CONFIG" <<'PY'
import grp,json,os,pwd,sys
from pathlib import Path
from panel.common import DEFAULT_CONFIG,atomic_json,validate_config
c=json.loads(Path(sys.argv[1]).read_text())
p=Path('/var/lib/dota2/server.json')
if not p.exists():
    atomic_json(p,validate_config(DEFAULT_CONFIG | {'port':c['game_port']}))
    u=pwd.getpwnam('steam'); os.chown(p,u.pw_uid,u.pw_gid)
web=Path('/etc/dota-panel/web.json')
atomic_json(web,{'allowed_hosts':[c['ip'],c['hostname'],'localhost','127.0.0.1']},0o640)
os.chown(web,0,grp.getgrnam('dotapanel').gr_gid)
PY
# Remove credentials and certificates created by releases before trusted-LAN mode.
rm -f /root/dota-panel-credentials.txt /etc/dota-panel/auth.json \
  /etc/dota-panel/tls/server.key /etc/dota-panel/tls/server.crt
rmdir /etc/dota-panel/tls 2>/dev/null || true
cat > /etc/nginx/snippets/dota-proxy.conf <<'NGINX'
proxy_http_version 1.1;
proxy_set_header Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto http;
proxy_set_header Forwarded "";
proxy_set_header Connection "";
proxy_read_timeout 30s;
proxy_send_timeout 30s;
NGINX
python3 "$SOURCE/install/render.py" nginx "$CONFIG" /etc/nginx/sites-available/dota-panel
# Dedicated fresh guest only: remove the stock welcome site, do not touch other named sites.
rm -f /etc/nginx/sites-enabled/default
ln -sfn /etc/nginx/sites-available/dota-panel /etc/nginx/sites-enabled/dota-panel
install -m 0644 "$SOURCE/systemd/"*.service /etc/systemd/system/
nginx -t
systemctl daemon-reload
systemctl enable --now dota-agent.service dota-panel.service nginx.service
systemctl reload nginx.service
python3 - <<'PY'
import json,time,urllib.request
for i in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/session',timeout=2) as r:
            session=json.load(r)
            assert session['authenticated'] is True and session['no_auth'] is True
        print('面板本机健康检查通过。游戏尚未安装/启动，不代表客户端已能联机。')
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('面板未就绪：检查 systemctl status dota-panel dota-agent 与 journalctl')
PY
PANEL_IP=$(python3 "$SOURCE/install/render.py" field "$CONFIG" ip)
PANEL_PORT=$(python3 "$SOURCE/install/render.py" field "$CONFIG" panel_port)
printf '\n面板地址：http://%s:%s（无网页密码，仅限受信任 LAN；禁止公网转发）\n' "$PANEL_IP" "$PANEL_PORT"
