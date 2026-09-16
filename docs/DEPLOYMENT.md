# 部署与运维手册

## 1. 部署前检查（PVE）

```bash
pveversion -v
pvesm status
pveam available --section system
ip -br addr
pct list
```

确认 x86_64、目标 CTID 未使用、存储支持 rootdir、模板存储支持 vztmpl、池有足够实际空间、网桥存在且连接目标 LAN。脚本固定 6C/6144MiB/250G；PVE 的 thin provision 不等于池里已准备好同等物理空闲空间，保留更新及快照余量。[S3]

设置 `pve/lxc.env`。它是会以 PVE root source 的 Bash 文件，只使用可信本地内容。不要把 Steam 密码、API token、管理员密码写入此文件，也不要执行陌生人提供的 env。

LAN_CIDRS=auto 仅取 CT eth0 地址对应的 IPv4 子网，不会自动放行其他 VLAN 或 VPN。需要跨网段时明确逗号分隔。管理与游戏共用这组白名单，接口不负责编辑宿主规则。

运行 dry-run，确认打印的命令，再 --apply。dry-run 不创建 CT、不更新模板缓存，但会读取当前 PVE 配置及模板列表；列表尚未更新时可自行执行 pveam update 后重试。

## 2. 自动过程

使用 pveam 获取 Ubuntu 24.04 官方 amd64 模板；pct create 配置非特权、6C、6144 MiB、250 G、nesting=0、onboot。使用桥接 veth，不使用 NAT/Docker 网络或 GPU。

等待 CT 的 eth0 IPv4；生成 `/etc/pve/firewall/<CTID>.fw`，只允许列明 LAN 来源的面板 TCP 与游戏 UDP、ICMP，出站允许。不会改变 `/etc/pve/firewall/cluster.fw` 或宿主全局防火墙开关。

源码上传 `/root/dota2-lan-kit-src`，执行 bootstrap。bootstrap 拒绝直接在 PVE 宿主运行；只接受 Ubuntu 24.04 x86_64，安装 Ubuntu 仓库依赖、官方 SteamCMD 种子、受限用户、服务和 Nginx HTTP。已有游戏配置/数据保留；运行中代理有游戏/任务时拒绝覆盖。

Nginx 默认 welcome site 被移除，新面板仅监听 HTTP 8443；没有新增 HTTP 80、SSH、远程 RCON 服务。第一次安装只部署环境，不运行 SteamCMD 安装游戏。

## 3. 面板地址

使用 `http://CT地址:8443` 打开面板，无需网页账号或密码。HTTP 不提供传输加密，因此只应在受信任 LAN 使用，禁止公网端口转发。

IP/域名变化需要同步 `/etc/dota-panel/web.json` 的 allowed_hosts 与访问入口。LAN 网段变化还需 Nginx allow 与该 CT 的 PVE 防火墙来源规则。重新 provision 会更新 allowed_hosts 与 Nginx 规则。最简单的是从开始使用 DHCP 保留或静态 IP。

## 4. 真实 SteamCMD 登录退路

网页支持普通密码提示、Steam Guard code 提示、常见手机确认文字；上游将来可能改变提示或登录机制。出现网页不识别的验证码/二维码流程时，保留脱敏日志，不向任何第三方提交密码。先停服并取消/结束任务，再使用 PVE Console：

```bash
# LXC root；本命令停止代理，因此会中断其游戏/安装进程！
systemctl stop dota-agent.service
runuser -u steam -- env HOME=/var/lib/dota2 LANG=C.UTF-8 \
  /bin/bash /srv/steamcmd/steamcmd.sh
```

在 SteamCMD 提示符交互输入：

```text
@sSteamCmdForcePlatformType linux
force_install_dir /srv/dota2
login YOUR_STEAM_LOGIN
```

按 SteamCMD 要求输入密码/验证码或手机批准。不要将密码拼入 Shell 历史。成功后输入 `quit`，返回 LXC root Shell：

```bash
systemctl start dota-agent.service
```

回到面板，以相同账号尝试缓存登录/安装；Valve 缓存失效时仍会要求重新授权。不要承诺一次授权永远有效。若之前已中断安装而留下维护标记，仍须在面板成功更新/校验，不能直接删除保护文件再强行开服。

## 5. 更新策略

默认没有自动定时更新。比赛结束后，点停止并等待任务完成，再点更新；也可以在 SteamCMD 页面明确勾选“允许本次维护停服”。“成功后恢复原先运行中的服务器”只适用于本次任务开始时服务器已运行的情况，失败不恢复。

“校验/修复”执行 app_update 570 validate，可能覆盖 Valve 原始文件的手工修改。[S2] 配置存放在独立 JSON，不直接依赖改写 Valve 文件。更新成功只代表本地安装完整，不代表与客户端的实际版本、地图与认证已经联机测试。

更新取消/错误会保留维护标记。先检查错误：磁盘不足、DNS/CDN、No subscription、会话失效或校验失败，再重试更新/校验。不要盲目无限循环登录或下载。

## 6. 备份与完整恢复

配置备份：位于 `/var/lib/dota2/backups`，最多 20 份；只包含 server.json（可能含游戏连接密码和账号名），不含 Steam 登录缓存、管理员密码或游戏资源。停服才能通过面板恢复。

完整恢复：使用 PVE 现有备份体系备份整个 CT。推荐停止游戏和任务后执行 stop-mode 备份，以便获得一致的应用状态：

```bash
# PVE：BACKUP_STORAGE 必须替换成自己的、支持 backup 的存储
vzdump 270 --mode stop --compress zstd --storage BACKUP_STORAGE
```

不要把该命令中的占位存储名原样执行。PVE 完整备份可能携带 Steam 登录缓存及日志；按敏感凭据保护。恢复到另一 CT/IP 后需重新核对网络与 allowed_hosts。

## 7. 服务操作边界

| 操作 | 影响 |
|---|---|
| 关闭浏览器 / 注销 | 不影响游戏与 SteamCMD |
| systemctl restart dota-panel | 仅网页后端，旧网页会话失效 |
| systemctl restart nginx | 仅 HTTP 入口短暂不可用 |
| systemctl restart dota-agent | 会停止其子进程；维护可能中断 |
| PVE 重启/停止 CT | 面板、代理、游戏与 SteamCMD 全受影响 |
| 修改 server.json | 需经代理 API/CLI 或停代理后修改，运行中游戏参数不立即变化 |

正常停服先向游戏 PTY 发送 quit，超时再对该代理拥有的进程组 TERM/KILL。不得用 `pkill steam`、`killall dota2` 误伤同一系统其他实例。

## 8. 常见排查

- 网页不能打开：确认访问的是 CT 地址与 HTTP 8443，不是 PVE 8006；检查 LAN 白名单、VLAN 路由与 Nginx；后端 8765 只监听回环，外部不能直接访问属正常。
- 面板代理断开：`systemctl status dota-agent`；检查 `/run/dota-agent/control.sock` 与 dota-control 组，而不是 chmod 777。
- 游戏启动后退出：导出诊断；看 `ldd` 缺失库、Valve wrapper、依赖/CPU 指令与 memory.events。没有真实报错前不改 privileged/nesting 或禁用沙箱。
- 安装成功但不能连接：确认客户端与服务端已更新，检查 UDP、客户端控制台报错、`sv_lan` 的跨网段限制、无线 AP 隔离、防火墙；进程状态不是完整游戏就绪检查。
- 模式/机器人命令无效：查看游戏输出，当前版本可能不支持该 cvar/模式或需要特定条件。不要把“写入 PTY 成功”当作游戏执行成功。
- 内存不足：用户规格固定 6 GiB，先缩小工作负载并读取 OOM 证据，再决定是否调整；代码不自行增加分配。

更多现场验收项见 `ACCEPTANCE.md`；引用 [S1]～[S7] 在 `SOURCES.md`。
