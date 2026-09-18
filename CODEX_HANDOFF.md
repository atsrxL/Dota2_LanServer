> 1.3.0 最新接手入口是根目录 CODEX_LAN_HANDOFF.md；以下保留基础运行环境说明。

# Codex 接手文件

## 1.2.0 Workshop 增补（优先阅读）

当前版本增补机器人 ID 下载与下一局部署，详细接手与新测试结果以 docs/CODEX_WORKSHOP_HANDOFF.md、docs/WORKSHOP_TEST_REPORT.md 为准。以下 1.1.0 内容保留为架构背景，历史测试数字不是本轮结果。HTTP 免登录与实时资源监控继续保留。当前未实现原生房间同步，真实机器人加载仍需验收。

## 0. 交付状态与最短阅读路径

这是一份包含实现源码、部署脚本、文档和测试的交付，不是只写 TODO 的脚手架。已在 MS-A2 的 CT 270 完成真实部署、Steam App 570 安装及服务端启动验证；两台真实客户端联机与完整对局仍未执行。实际运行的测试和范围见 `docs/TEST_REPORT.md`；待现场验收见 `docs/ACCEPTANCE.md`。

依次读取 AGENTS.md → 本文件 → REVIEW_TEST_REPORT → DEPLOYMENT。需要改哪个层就只读那个模块，避免反复把所有源码/日志装入上下文。接手者不得根据本文件猜测用户的 storage、vmbr、IP、CTID 或 Steam 凭据。

## 1. 用户硬约束

PVE LXC，Ubuntu 24.04 非特权；6 vCPU / 6 GiB（6144 MiB）内存 / 250 G 磁盘。原生 SteamCMD，无 Docker、无 GPU，不开 nesting。面向局域网其他设备，用中文网页控制安装、启动、停止、更新等，并有完整使用帮助和源码 ZIP。

## 2. 代码导航

| 文件 | 用途 |
|---|---|
| pve/create-lxc.sh + common.sh | 读配置、检查、dry-run、创建、网络规则、上传与调用 bootstrap |
| pve/provision-existing.sh | 修复首次配置中断或安全重部署环境，保留数据 |
| install/bootstrap.sh | Ubuntu 包/用户/SteamCMD种子/HTTP免登录/服务/健康检查 |
| install/render.py | 严格校验部署 JSON，生成 nginx 与 CT 防火墙 |
| panel/common.py | 配置 schema、路径、原子写、启动参数数组、manifest |
| panel/steam.py | pexpect SteamCMD 协议：授权、补交秘密、下载成功判定 |
| panel/process.py | 游戏 PTY、stdout、正常退出/超时进程组终止 |
| panel/agent.py | Unix RPC、单任务锁、持久任务、维护锁、备份、监控 |
| panel/web.py | WSGI、HTTP免登录、CSRF/Origin、固定 HTTP API |
| panel/static/ | 无构建中文前端、帮助页，日志通过 textContent 渲染 |
| panel/cli.py | 本地恢复工具，getpass，不接收密码 argv |
| tests/ | 配置/安全/真实子进程但模拟协议的自动测试 |
| tools/demo.py | 纯本机开发演示，不是真实服务器 |

生产 unit 名称：dota-agent、dota-panel、nginx。游戏不是独立 `dota2.service`；它是 agent 管理的子进程，不要写不存在的 systemctl start dota2 指令。

## 3. 首次现场接手操作

先由本机只读命令获取 PVE 版本、架构、存储能力、网桥、CTID 空闲情况；编辑 lxc.env，再 dry-run。任何实际部署要使用本包明确的 --apply。不要重新询问已有的 6/6GiB/250G 规格；未给出的存储/网络由现场读取解决。

确认 bootstrap 成功、服务权限、HTTP 面板直接进入且不要求密码、无 SSL 监听/跳转、LAN 白名单有效。Steam 授权由用户自己输入；接手者不读取/外发 Steam 密码或缓存。

安装真实 App 570，记录 buildid、StateFlags、平台与依赖（不包含 Steam 凭据）；启动后检查退出、日志、端口、cgroup OOM。两台真实客户端完成建图/选人/对局，才可把对应验收项改为 PASS。

## 4. 已知需要真实环境确认的技术点

- SteamCMD 认证文字/手机批准行为可能随版本改变。本代码根据常见英文提示匹配，未宣称覆盖任何未来二维码/语言组合。下载过程强制 LANG=C.UTF-8；如出现未识别登录，使用 DEPLOYMENT 中控制台首次授权退路，然后针对实际脱敏提示加测试。
- 2026-09-16 目标 CT 实测：当前 App 570 的 `game/dota.sh` 强制要求 Steam Linux Runtime 3.0 (sniper)，而官方 pressure-vessel/bwrap 在本方案固定的非特权 `nesting=0` LXC 中无法创建 namespace。当前 `game/bin/linuxsteamrt64/dota2` 使用随游戏附带的库路径可直接启动；已实际加载 `dota` 地图、进入 `ss_active` 并监听 UDP 27015。因此 `build_command()` 优先使用该二进制，仅把 wrapper 留作旧版布局回退。Valve 后续构建仍须重新现场验证，不从社区下载替换授权/反作弊库。
- `+dota_force_gamemode`、bots/pause/say 的支持须看实际游戏响应。PTY 写入成功不是游戏命令执行成功。默认模式是普通 dota 地图，不是自动 Workshop 部署。
- UDP 监听状态只是命名空间端口检查；不提供伪造的 A2S 就绪/在线人数。后续增加玩家数/空服自动更新需先可靠协议实测。
- 6 GiB 可能对某些地图/机器人负载紧张；固定用户资源不默默更改。检查 memory.events 和 PVE 指标后如实记录。
- 部署依赖使用 Ubuntu 包版本而非 pip 全量锁版本。当前代码层测试不能证明目标 Ubuntu 镜像里的 Waitress/Nginx/所有游戏库组合都已实测。

pexpect 在本地 Python 多线程环境产生 forkpty 弃用/潜在死锁警告；完整测试结果见 TEST_REPORT。网页离线 DOM/本机请求桥接检查不是生产 Nginx 端到端验证。

## 5. 应保留的不变量

一个活动变更任务；服务器在线时游戏 install/update/validate 需要明确停服授权；Bot download/check 只写独立库，可与运行中的比赛并存；更新前 maintenance.json，成功后才移除；失败与取消不自动开服；日志写盘前脱敏；请求体和 pexpect 异常 buffer 不进日志；不重复运行两个 SteamCMD。

root-owned 代码与独立用户数据目录；游戏/SteamCMD 不以 root 跑；网页和代理分离；仅固定 CLI/API/RPC 动作；纯 LAN。不要用 eval/exec user input、shell=True、chmod777、NOPASSWD ALL、lxc.apparmor.profile=unconfined 或 privileged=1 “快速修好”。

## 6. 故障定位顺序

网络/DNS/仓库 → PVE配置与权限 → nginx/Waitress → Unix socket/agent → SteamCMD授权/许可 → 下载/manifest → Linux依赖/启动参数 → 游戏控制台 → 客户端版本/路由/实际模式。

通过面板导出诊断只含选定状态和脱敏日志，不应发出整个 `/var/lib/dota2`。原始 Valve 日志要由用户在本机先审阅。修改日志处理时重点增加“跨块回显密码”和 Guard 测试。

## 7. 建议的验收与交付结语格式

写明版本/修改文件/实际测试命令/通过数量/尚未实测项。附更新后的源码 ZIP、SHA256SUMS、REVIEW_TEST_REPORT、ACCEPTANCE.local（脱敏）。现场没跑到的项目保持 NOT RUN，不用“应该没问题”替代结果。

可直接给后续 Codex 的起始指令：

> 接手这个 dota2-lan-kit。先读 AGENTS.md 和 CODEX_HANDOFF.md，保持 6 vCPU/6GiB/250G 非特权原生 LXC 方案。先检查真实 PVE 存储/网桥/CTID，审查 dry-run，再执行部署。Steam 凭据由我本人在可信 LAN 的 HTTP 免登录面板输入。按 docs/ACCEPTANCE.md 区分模拟测试与真实安装/两客户端联机证据。不要为了开服绕过 maintenance 保护、Steam 授权或改特权容器。完成后更新测试与现场验收记录并重新打包。

## 8. 本轮 HTTP / 监控补丁接手

先读 docs/REVIEW_NOTES.md、docs/REVIEW_TEST_REPORT.md、docs/MONITORING.md。新模块 panel/resources.py 与 panel/static/metrics.js；/api/metrics 和 dota-cli metrics 提供同一只读采样。

交付包内有独立本地 Git bundle 与两个变更 patch。先从真实仓库确认默认分支、HEAD、已改文件和路径映射，审查用户更改，再在新分支逐个 cherry-pick/手工合并。不能以源码快照覆盖仓库，不能 reset --hard 或 force push，不能把本地基线 SHA 当作 GitHub 的历史。完成真实审查、测试并推送后记录实际远端 SHA，再让部署端拉取。

HTTP/no-login 是用户确定要求：不得因原文历史说明恢复 TLS/管理员认证。Steam 授权必须保留。资源统计不得硬编码 6 核/6 GiB；实际目标仍是这些规格。修改运行代理后必须正常结束任务/停服再重新部署；不能只更新静态页面就宣称已完成后端升级。
