#!/usr/bin/env bash
# Shared, sourced only by the PVE entry points.
set -Eeuo pipefail
fail() { printf '错误：%s\n' "$*" >&2; exit 1; }
log() { printf '\n==> %s\n' "$*"; }
load_config() {
  local file=$1
  [[ -f "$file" ]] || fail "配置不存在：$file；先复制 pve/lxc.env.example"
  # shellcheck disable=SC1090
  source "$file"
  : "${CTID:?}" "${CT_HOSTNAME:?}" "${ROOTFS_STORAGE:?}" "${TEMPLATE_STORAGE:?}" "${BRIDGE:?}"
  TEMPLATE=${TEMPLATE:-auto}; IPV4=${IPV4:-dhcp}; GATEWAY=${GATEWAY:-}; DNS=${DNS:-}
  VLAN_TAG=${VLAN_TAG:-}; LAN_CIDRS=${LAN_CIDRS:-auto}; PANEL_PORT=${PANEL_PORT:-8080}
  GAME_PORT=${GAME_PORT:-27015}; TIMEZONE=${TIMEZONE:-Asia/Tokyo}; SWAP_MIB=${SWAP_MIB:-1024}
  SSH_PUBLIC_KEY_FILE=${SSH_PUBLIC_KEY_FILE:-}; STEAMCMD_ARCHIVE_SHA256=${STEAMCMD_ARCHIVE_SHA256:-}
  [[ "$CTID" =~ ^[1-9][0-9]{2,8}$ ]] || fail "CTID 必须为 >=100 的数字"
  [[ "$CT_HOSTNAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]{0,62}$ ]] || fail "主机名无效"
  for v in "$ROOTFS_STORAGE" "$TEMPLATE_STORAGE" "$BRIDGE"; do
    [[ "$v" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || fail "存储或网桥名称无效"
  done
  [[ "$SWAP_MIB" =~ ^[0-9]+$ ]] || fail "SWAP_MIB 无效"
  [[ "$PANEL_PORT" =~ ^[0-9]+$ && "$GAME_PORT" =~ ^[0-9]+$ ]] || fail "端口必须为数字"
  ((PANEL_PORT >= 1024 && PANEL_PORT <= 65535 && GAME_PORT >= 1024 && GAME_PORT <= 65535)) || fail "端口范围 1024..65535"
  [[ -z "$VLAN_TAG" || "$VLAN_TAG" =~ ^[0-9]+$ ]] || fail "VLAN 无效"
  if [[ -n "$VLAN_TAG" ]]; then ((VLAN_TAG >= 1 && VLAN_TAG <= 4094)) || fail "VLAN 范围 1..4094"; fi
  python3 - "$IPV4" "$GATEWAY" "$LAN_CIDRS" "$DNS" <<'PY'
import ipaddress, sys
ip, gw, cidrs, dns = sys.argv[1:]
if ip != 'dhcp':
    assert '/' in ip, '静态 IP 必须含 /前缀长度'
    ipaddress.IPv4Interface(ip)
    assert gw, '静态 IP 须填写 GATEWAY'
    ipaddress.IPv4Address(gw)
elif gw:
    raise SystemExit('DHCP 模式 GATEWAY 应留空')
if cidrs != 'auto':
    for c in cidrs.split(','):
        n = ipaddress.IPv4Network(c.strip(), strict=False)
        assert n.prefixlen >= 8, '拒绝过宽的 LAN 白名单'
if dns:
    ipaddress.IPv4Address(dns)
PY
}
check_pve() {
  [[ $EUID -eq 0 ]] || fail "请以 PVE root 执行"
  [[ $(uname -m) == x86_64 ]] || fail "本部署只支持 x86_64 PVE，不支持 ARM"
  for c in pct pvesm pveam pveversion python3 tar ip; do command -v "$c" >/dev/null || fail "缺少 $c"; done
  [[ -d /etc/pve/lxc && -d "/sys/class/net/$BRIDGE" ]] || fail "不是 PVE 环境，或网桥不存在"
  pvesm status --storage "$ROOTFS_STORAGE" --content rootdir | awk 'NR>1 && $3=="active" {found=1} END {exit !found}' || fail "rootfs 存储不存在、离线或不支持 rootdir"
  pvesm status --storage "$TEMPLATE_STORAGE" --content vztmpl | awk 'NR>1 && $3=="active" {found=1} END {exit !found}' || fail "模板存储不存在、离线或不支持 vztmpl"
}
make_net() {
  NET0="name=eth0,bridge=$BRIDGE,ip=$IPV4,ip6=manual,firewall=1,type=veth"
  [[ -z "$GATEWAY" ]] || NET0+=",gw=$GATEWAY"
  [[ -z "$VLAN_TAG" ]] || NET0+=",tag=$VLAN_TAG"
}
wait_container() {
  log "等待 CT $CTID 启动并取得 IPv4"
  for ((i=0; i<90; i++)); do
    ADDR_JSON=$(pct exec "$CTID" -- ip -j -4 addr show dev eth0 2>/dev/null || true)
    IP_CIDR=$(python3 -c 'import json,sys; a=json.loads(sys.argv[1] or "[]"); print(next((x["local"]+"/"+str(x["prefixlen"]) for z in a for x in z.get("addr_info",[]) if x.get("scope")=="global"),""))' "$ADDR_JSON" 2>/dev/null || true)
    [[ -z "$IP_CIDR" ]] || return 0
    sleep 2
  done
  fail "容器没有取得 IPv4。检查网桥/VLAN/DHCP；CT 保留，不会自动删除。"
}
provision_ct() {
  wait_container
  local tmp archive cfg
  tmp=$(mktemp -d)
  archive="$tmp/source.tar.gz"; cfg="$tmp/bootstrap.json"
  # Temp directory is removed on return; it contains no Steam or panel credentials.
  python3 - "$cfg" "$IP_CIDR" "$LAN_CIDRS" "$CT_HOSTNAME" "$PANEL_PORT" "$GAME_PORT" "$TIMEZONE" "$STEAMCMD_ARCHIVE_SHA256" <<'PY'
import ipaddress,json,sys
path,cidr,lan,host,panel,game,tz,sha=sys.argv[1:]
interface=ipaddress.IPv4Interface(cidr)
networks=[str(interface.network)] if lan=='auto' else [str(ipaddress.IPv4Network(x.strip(),strict=False)) for x in lan.split(',')]
assert all(ipaddress.IPv4Network(x).prefixlen>=8 for x in networks), 'LAN 自动网段过宽，请指定 LAN_CIDRS'
data=dict(ip=str(interface.ip),lan_cidrs=networks,hostname=host,panel_port=int(panel),game_port=int(game),timezone=tz,steamcmd_sha256=sha)
with open(path,'w') as f: json.dump(data,f,indent=2)
PY
  log "只为 CT $CTID 写入 LAN 防火墙规则；不改变数据中心或宿主全局防火墙开关"
  if [[ -f "/etc/pve/firewall/$CTID.fw" ]]; then
    install -d -m 0700 /root/agent.backup
    python3 - "$CTID" <<'PYBACKUP'
import pathlib, shutil, sys, time
ctid = sys.argv[1]
root = pathlib.Path("/root/agent.backup")
prefix = "dota-kit-agent-ct-" + ctid + ".firewall-"
target = root / (prefix + str(time.time_ns()))
shutil.copy2("/etc/pve/firewall/" + ctid + ".fw", target)
target.chmod(0o600)
owned = sorted((p for p in root.glob(prefix + "*")
                if p.is_file() and not p.is_symlink() and p.name[len(prefix):].isdigit()),
               key=lambda p: int(p.name[len(prefix):]), reverse=True)
for old in owned[2:]:
    old.unlink()
PYBACKUP
  fi
  python3 "$REPO/install/render.py" firewall "$cfg" "/etc/pve/firewall/$CTID.fw"
  log "上传源码并配置 LXC 环境（不自动下载 Dota 2）"
  tar --exclude='./.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='./pve/lxc.env' \
      --exclude='./pve/*.backup-*' --exclude='./.venv' -czf "$archive" -C "$REPO" .
  pct push "$CTID" "$archive" /root/dota2-lan-kit-source.tar.gz --perms 0600
  pct push "$CTID" "$cfg" /root/dota2-bootstrap.json --perms 0600
  pct exec "$CTID" -- mkdir -p /root/dota2-lan-kit-src
  pct exec "$CTID" -- tar -xzf /root/dota2-lan-kit-source.tar.gz --no-same-owner -C /root/dota2-lan-kit-src
  pct exec "$CTID" -- bash /root/dota2-lan-kit-src/install/bootstrap.sh --config /root/dota2-bootstrap.json
  rm -rf -- "$tmp"
  log "环境安装完成"
  printf '面板：http://%s:%s\n' "${IP_CIDR%/*}" "$PANEL_PORT"
  printf '进入 LXC：pct enter %s\n游戏连接命令：connect %s:%s\n' "$CTID" "${IP_CIDR%/*}" "$GAME_PORT"
  echo '若数据中心/节点的 PVE 防火墙未启用，CT 规则未必生效。不要将端口转发到公网。'
}
