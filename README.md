> 已在真实仓库 88871cb 上合并 1.3.0，并完成已有 LXC 升级。现场进展与未完成项见 docs/DEPLOYMENT_1.3.0.md；上游候选报告保留为历史记录。

# Dota 2 LAN Kit

**本地候选补丁 · v1.3.0 · 2026-09-18（未发布到 GitHub）**

在 PVE 上创建一个 Ubuntu 24.04 amd64 非特权 LXC，以原生 SteamCMD 管理 Dota 2 局域网服务器；通过中文 HTTP 免登录网页面板控制。

固定创建规格：**6 vCPU / 6144 MiB（6 GiB）内存 / `rootfs <storage>:250`（PVE 的 250 G 磁盘参数）**。额外 swap 额度默认 1024 MiB，可设置为 0；不是额外物理内存。不开 nesting、不装 Docker、不直通 GPU，不在 PVE 宿主安装游戏或网页依赖。

> 重要更正：不要把 `login anonymous + app_update 570` 当作已验证安装方案。Valve Developer Community 的服务器列表将 Dota 2 的匿名登录列为 No。[S1] 本项目提供账号、密码、Steam Guard 和手机批准流程。真正的 Steam 授权、当日 App 570 Linux 文件与客户端联机仍须在目标环境验证。模拟测试通过不代表真实 Dota 2 联机通过。

## 1.3.0 新目标：连接后游戏内配置

本版包含三个模块的完整源代码：LXC面板控制、`lan_dota`附加模式的连接/准备界面、天地星1627071163静态及原生Bot运行探针。新路线不读取官方房间，不另建GC，不改Steam授权库。真实编译、连接和AI效果交给本地Codex验证。

**先读 [CODEX_LAN_HANDOFF.md](CODEX_LAN_HANDOFF.md)。**源码中没有已编译Panorama，必须本地Workshop Tools编译并用 `tools/addon_assets.py` 收集/导入；未编译时拒绝启动addon。玩家客户端也要安装同版资源。天地星原始脚本仍由面板从Workshop下载，不随源码再分发。

已有LXC不重建。先无AI验证两端连接/无限等待配置，再启用原生Bot实验。填充路径当前要求显式训练作弊；不自动开、不静默退回默认AI。意向位置尚未映射天地星原生槽位，完整兼容与卡顿改善均待实机验收。

新文档：`docs/LAN_ADDON.md`、`docs/TIANDIXING_VALIDATION.md`、`docs/LAN_TEST_REPORT.md`；`compat/acceptance.template.json` 全部默认NOT_RUN。以下常规SteamCMD/普通地图使用仍可用，但新附加模式以新帮助为准。

## 保留功能：输入 Workshop ID 自动安装机器人

机器人页预填 `1627071163`。保存 Steam 账号并授权后，点“下载并安装”即可查元数据、下载、处理 Lua/ZIP/VPK、保存内容版本并选为下一局。运行中版本不变，结束比赛后手动重启生效，玩家到齐/选边后再填充 Bot。支持更新、版本选择、停用、上次选择回滚与取消。

**未实测真实 1627071163/Linux Dedicated；原生房间同步尚未实现。**不要把下载完成或入口日志当作完整 AI 验收。新帮助：`docs/WORKSHOP_BOTS.md`；新接手：`docs/CODEX_WORKSHOP_HANDOFF.md`；本轮结果：`docs/WORKSHOP_TEST_REPORT.md`。旧 REVIEW 文档是上一轮历史记录。

已有 CT：先合并用户仓库改动，正常结束任务/停服，使用 `pve/provision-existing.sh`；不要按下面的首次创建流程重建现有 CT。

## 1. 最短部署流程

将 ZIP 放到 PVE，解压，在 **PVE root Shell** 执行：

```bash
unzip dota2-lan-kit-1.3.0.zip
cd dota2-lan-kit
cp pve/lxc.env.example pve/lxc.env
nano pve/lxc.env

# 只读检查，打印计划，不创建容器
bash pve/create-lxc.sh --config pve/lxc.env --dry-run

# 明确执行：创建 LXC、设置该 CT 的规则、上传源码并安装运行环境
bash pve/create-lxc.sh --config pve/lxc.env --apply
```

至少核对 `CTID`、`ROOTFS_STORAGE`、`TEMPLATE_STORAGE`、`BRIDGE`。默认 `CTID=270`、`local-lvm`、`local`、`vmbr0` **只是可编辑示例，不代表已探测你的环境**。建议固定 IP，或在路由器为 DHCP 租约做保留。

静态 IP 示例（必须换成自己的网络）：

```bash
IPV4="192.168.1.70/24"
GATEWAY="192.168.1.1"
LAN_CIDRS="192.168.1.0/24"
```

默认 `IPV4=dhcp`、`LAN_CIDRS=auto` 会使用新 CT 的 eth0 IPv4 子网。跨 VLAN 的管理/游戏设备必须明确加入白名单。脚本不打开数据中心/宿主的全局防火墙开关，也不配置公网端口转发。

脚本最后显示 HTTP 面板地址，例如 `http://192.168.1.70:8080`。直接打开即可使用，没有面板账号、密码、证书或 HTTPS 跳转。

仅允许你信任的 LAN 设备访问。HTTP 不加密 Steam 密码/Guard 输入，面板内已明确提示；LAN 白名单内任何人都可管理此实例。Steam 自身的账号授权仍需完成。

## 2. 首次安装与开服

打开面板，进入 **SteamCMD**，输入 Steam 登录名与密码，点击“测试登录 / 授权”。有 Steam Guard 时在任务输入框补交验证码，或在手机 Steam 客户端批准。应用不保存 Steam 密码/验证码；Valve 的 SteamCMD 自身可能保存登录缓存，后续更新不保证永远无需重新授权。

点击“安装 Dota 2（含校验）”，在日志中确认 App 570 成功完成。安装时会下载 Valve 内容，**ZIP 不含游戏资源**。安装器只初始化 SteamCMD 和面板，不擅自下载游戏、不自动开服。

在服务器配置中填写名称、模式及可选游戏密码；默认标准地图 `dota`、LAN 模式固定开启，`-insecure` 和作弊均默认关闭。点击“启动服务器”。其他设备在 Dota 2 开发者控制台输入：

```text
connect 192.168.1.70:27015
```

实际验收：设备连接 → 地图加载 → 选边/选人 → 开始并完成一次测试对局。**“代理在线”“进程运行中”“端口监听”是不同层次，不等于真实对局验收成功。** LAN 服务器也不等于已实现完全断网运行；安装、更新及 Steam/客户端授权可能仍需联网。

## 3. 已包含的功能

| 范围 | 实现 |
|---|---|
| PVE | CTID 冲突检查、模板选择、非特权 LXC、桥接/VLAN/DHCP/静态 IP、固定资源、dry-run、失败保留 CT |
| 机器人 | Workshop ID 下载、Lua/ZIP/VPK安全处理、SHA版本、下一局部署、停用/回滚、入口探针 |
| SteamCMD | 登录/授权、安装、更新、validate、实时日志、一次性密码/验证码补交、取消、维护互斥 |
| 游戏进程 | 启动、正常停止、超时终止自有进程组、重启、按需开机自启、崩溃有限重试 |
| 配置 | 名称、端口、地图、游戏模式、游戏密码、作弊/VAC 选项、保存账号名 |
| 管理 | 构建号、磁盘/cgroup 内存、UDP 监听检查、任务历史、游戏日志、受限游戏控制台 |
| 备份 | 手动/配置变更/维护前配置快照、保留 20 份、停服恢复、下载、诊断导出 |
| 实时监控 | 总 CPU、可见每核心、内存/工作集/缓存/Swap/OOM、2 分钟趋势、断线与缺失值提示 |
| 安全 | HTTP 免登录、LAN 白名单、Host/Origin/CSRF 与固定动作；无面板密码/会话 |
| 交付 | 中文帮助页、计划书、部署/安全/API 文档、测试、Codex 接手文件、AGENTS.md |

**不是本版本功能：** 原生房间配置同步、队伍/槽位自动还原、双方不同 Bot、机器人 ZIP 上传/在线 Lua 编辑、 Valve 官方匹配/GC 替代、完全离线授权、自定义游廊地图一键全兼容、游戏历史版本回滚、游戏存档恢复、多管理员/多实例、任意 Shell 或文件管理器、公网开放、定时打断比赛的无人值守更新。使用固定动作和受限控制台，不开放 RCON。

## 4. 结构与权限

```text
PVE（仅 pct / pveam / pvesm / 每 CT 防火墙）
└── Ubuntu 24.04 非特权 LXC · 6C / 6GiB / 250G
    ├── Nginx :8080 HTTP（免登录） / LAN 白名单
    ├── dota-panel.service (dotapanel 用户)
    │   └── Waitress / 127.0.0.1:8765 / 无登录 HTTP API
    └── /run/dota-agent/control.sock（Unix socket 权限控制）
        └── dota-agent.service (steam 用户)
            ├── SteamCMD PTY 子进程
            └── Dota 2 PTY 子进程 / UDP 27015
```

代码 `/opt/dota2-lan-kit` 归 root 所有、服务不可写。游戏 `/srv/dota2`、SteamCMD `/srv/steamcmd`、状态 `/var/lib/dota2` 归 steam。网页用户只能使用 Unix socket，不直接读取 Steam 缓存。两个服务均不以 root 运行，没有 sudo 放行项。

关闭网页、**仅重启 dota-panel.service** 不会停止下载或游戏。重启 **dota-agent.service 或 LXC** 会终止其子进程，记录中断任务；中断更新后须成功更新/校验才能再次开服。

## 5. 命令行恢复

```bash
# PVE → LXC root Shell
pct enter 270

# 以下在 LXC 内运行
dota-cli status
dota-cli metrics
dota-cli jobs
dota-cli logs --name server
dota-cli diagnostics
dota-cli stop                       # 异步提交，随后查看 jobs

systemctl status dota-agent dota-panel nginx --no-pager
journalctl -u dota-agent -u dota-panel -n 150 --no-pager
```

首次创建后网络/apt 失败的恢复路径（在 PVE）：

```bash
bash pve/provision-existing.sh --config pve/lxc.env --apply
```

该脚本保留游戏配置与 Steam 缓存（移除旧面板认证/TLS 文件）；重做该 CT 的防火墙规则前保存旧文件。若已有任务或游戏在运行，环境安装器会拒绝覆盖运行环境，先主动停服。**不要为修复安装问题删除 CT。**

## 6. 测试与文档

```bash
# 在普通开发环境/测试机；非 PVE 宿主生产环境
python3 -m pip install -r requirements-dev.txt
bash scripts/test.sh
```

运行依赖使用 Ubuntu apt 包 `python3-pexpect`、`python3-waitress`，不依赖 Node/CDN/Python 在线 wheel 才能运行面板；首次环境部署仍需 apt 与 Valve 下载网络。测试使用自建模拟 SteamCMD/游戏进程，不连接真实 Steam。详见 `docs/WORKSHOP_TEST_REPORT.md` 与 `docs/ACCEPTANCE.md`。

优先阅读：`docs/DEPLOYMENT.md`、`docs/HELP.md`、`docs/PLAN.md`、`CODEX_HANDOFF.md`。网页帮助位于面板 `/help`；离线帮助是 `docs/HELP.html`。

外部技术依据、日期和未验证边界见 `docs/SOURCES.md`。本项目不是 Valve、Steam 或 Proxmox 的官方产品，不分发其游戏二进制或第三方破解/授权补丁。

## 界面预览与可复现检查

当前机器人页截图位于 `docs/workshop-panel-preview.png` 与 `docs/workshop-mobile-preview.png`；上一轮概览截图仍保留在 docs/review-panel-preview.png；截图中的 TEST Build、资源数值和连接信息来自模拟环境，不是实际 PVE 实例。独立离线帮助页为 `docs/HELP.html`，浏览器打开即可阅读。

本轮代码/模拟进程和界面检查的实际数量、警告与未执行项，统一见 `docs/WORKSHOP_TEST_REPORT.md`。`docs/REVIEW_TEST_REPORT.md` 与 `docs/TEST_REPORT.md` 仅保留历史 1.1.0 / 1.0.0 证据，不是当前版本的验收记录。

可选开发测试：安装 `requirements-dev.txt` 后运行 `bash scripts/test.sh`；界面测试另装 `requirements-ui.txt` 与 Chromium，先运行 `python3 tools/demo.py`，再运行 `python3 tools/ui_smoke.py`。演示程序只监听回环地址，使用明确标注的假进程，无需面板密码，绝不能替代生产部署。

重新打包：`python3 scripts/package.py --output /path/to/output`。打包器只收集源码/文档白名单目录，不收集 `pve/lxc.env`、缓存和已知本地敏感配置；仍需自行检查新增文档/测试记录中没有秘密。
