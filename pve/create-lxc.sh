#!/usr/bin/env bash
set -Eeuo pipefail
REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=common.sh
source "$REPO/pve/common.sh"
CONFIG="$REPO/pve/lxc.env"; APPLY=0
while (($#)); do
  case "$1" in
    --config) [[ $# -ge 2 ]] || fail "--config 缺少参数"; CONFIG=$2; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    -h|--help) echo 'bash pve/create-lxc.sh --config pve/lxc.env [--dry-run|--apply]'; exit 0 ;;
    *) fail "未知参数：$1" ;;
  esac
done
load_config "$CONFIG"; check_pve; make_net
[[ ! -e "/etc/pve/lxc/$CTID.conf" && ! -e "/etc/pve/qemu-server/$CTID.conf" ]] || fail "CTID/VMID $CTID 已被占用，不覆盖现有机器"
if ((APPLY)); then
  pveam update
fi
if [[ "$TEMPLATE" == auto ]]; then
  TEMPLATE=$(pveam available --section system | awk '$2 ~ /^ubuntu-24\.04-standard_.*_amd64\.tar\.(zst|xz|gz)$/ {print $2}' | sort -V | tail -n 1)
  [[ -n "$TEMPLATE" ]] || fail "未找到 Ubuntu 24.04 amd64 模板；执行 pveam update 并检查 pveam available"
fi
[[ "$TEMPLATE" =~ ^ubuntu-24\.04-standard_.*_amd64\.tar\.(zst|xz|gz)$ ]] || fail "仅接受 Ubuntu 24.04 amd64 官方模板名称"
CREATE=(pct create "$CTID" "$TEMPLATE_STORAGE:vztmpl/$TEMPLATE"
  --hostname "$CT_HOSTNAME" --ostype ubuntu --arch amd64 --unprivileged 1
  --features nesting=0 --cores 6 --memory 6144 --swap "$SWAP_MIB"
  --rootfs "$ROOTFS_STORAGE:250" --net0 "$NET0" --onboot 1 --startup order=30,up=15,down=60)
[[ -z "$DNS" ]] || CREATE+=(--nameserver "$DNS")
if [[ -n "$SSH_PUBLIC_KEY_FILE" ]]; then
  [[ -f "$SSH_PUBLIC_KEY_FILE" ]] || fail "SSH 公钥文件不存在"
  CREATE+=(--ssh-public-keys "$SSH_PUBLIC_KEY_FILE")
fi
log "创建计划：6 vCPU / 6144 MiB 内存 / $ROOTFS_STORAGE:250 / 非特权 / 不启用 nesting"
printf '%q ' "${CREATE[@]}"; printf '\n'
printf '模板存储：%s\nLAN 白名单：%s\nHTTPS：%s/TCP；游戏：%s/UDP\n' "$TEMPLATE_STORAGE" "$LAN_CIDRS" "$PANEL_PORT" "$GAME_PORT"
if ((!APPLY)); then
  echo '以上只读检查；没有创建容器。确认配置后加 --apply。'
  exit 0
fi
trap 'rc=$?; echo "执行失败（$rc）。已创建的 CT 和数据保留；修复原因后运行 provision-existing.sh，切勿盲目删除。" >&2; exit "$rc"' ERR
log "下载/检查模板"
pveam download "$TEMPLATE_STORAGE" "$TEMPLATE"
log "创建并启动 LXC"
"${CREATE[@]}"
pct start "$CTID"
provision_ct
