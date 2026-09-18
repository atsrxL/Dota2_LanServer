#!/usr/bin/env bash
set -Eeuo pipefail
REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=common.sh
source "$REPO/pve/common.sh"
CONFIG="$REPO/pve/lxc.env"; APPLY=0
while (($#)); do
  case "$1" in
    --config) [[ $# -ge 2 ]] || fail "缺少配置参数"; CONFIG=$2; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    -h|--help) echo 'bash pve/provision-existing.sh --config pve/lxc.env --apply'; exit 0 ;;
    *) fail "未知参数：$1" ;;
  esac
done
load_config "$CONFIG"; check_pve
pct config "$CTID" | grep -q '^unprivileged: 1$' || fail "只支持非特权 LXC"
pct config "$CTID" | grep -q '^ostype: ubuntu$' || fail "目标须为 Ubuntu LXC"
log "将重新配置指定 CT $CTID 的环境，保留游戏数据与 Steam 账号缓存；移除本项目旧面板密码和 TLS 配置"
echo '会更新该 CT 的防火墙文件（先备份旧文件），但不会自动扩容/更改现有 CT CPU 与内存。'
((APPLY)) || { echo '加 --apply 执行。'; exit 0; }
pct status "$CTID" | grep -q running || pct start "$CTID"
provision_ct
