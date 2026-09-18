> 本地部署更新：已合并真实仓库并升级 CT 270；最新现场结果见 docs/DEPLOYMENT_1.3.0.md。以下是原候选交付说明，历史“未访问”不代表当前状态。

# Codex 接手：LAN 附加模式 + 准备阶段 + 天地星验证（1.3.0）

## 0. 交付性质与必须保留的要求

这是实际源代码、离线测试、资源工具和验证模块的候选交付，不是已在 Dota/PVE 跑通的发行版。基于本地 1.2.0 提交 `a0504f614931fae9498f65e6fa2347fc49a0e361`，不是已确认的用户 GitHub 分支祖先。本轮未取得 `atsrxL/Dota2_LanServer` 最新工作区，未 push、未创建远端分支/PR/tag，未访问用户 PVE。

固定 Ubuntu 24.04 amd64 非特权 LXC：6 vCPU、6144 MiB、250 G。HTTP、无面板密码登录。保留 CPU/每核/内存监控、Steam Guard、Workshop 下载/版本管理、LAN ACL/Host/Origin/CSRF、原子持久化、单变更任务和非 root 游戏进程。不新增 Docker、GPU、nesting、特权容器、公网入口或任意 Shell。

**未随包提供：Valve 游戏资源、天地星原始脚本、Valve 编译器、已编译 Panorama、真实账号/凭据。**没有用改后缀或合成二进制冒充可用 UI。测试中的 `synthetic_resource()` 只能做格式边界测试，禁止复制进交付/生产 compiled 目录。

新体验是：面板启动 `lan_dota` → 原版客户端 connect → 自制 Panorama 准备界面 → 选边/意向位置/参数/准备 → 配置者开始 → 可选实验补 AI。不是官方主菜单 Lobby，也不包含私人 GC 或客户端 Steam API 补丁。

## 1. 阅读顺序与模块位置

AGENTS.md → 本文件 → docs/LAN_TEST_REPORT.md → docs/LAN_ADDON.md → docs/TIANDIXING_VALIDATION.md。

| 模块 | 关键文件 |
|---|---|
| 1 LXC 面板/启动/部署 | panel/lan_addon.py、addon_assets.py、addon_runtime.py；agent/common/process/web 集成；static/addon.js |
| 2 连接后准备阶段 | addon/lan_dota/game/scripts/vscripts/lan/{room,identity,engine,json}.lua；addon_game_mode.lua；content/panorama |
| 3 天地星验证 | panel/bot_audit.py；bots.py 的 observer；原生 Bot 部署副本探针；compat/acceptance.template.json |
| 双端构建工具 | tools/addon_assets.py：stage / collect / import / client-package / status |
| 本地测试 | tests/test_lan_addon.py、tests/lua、tests/js；tools/run_lua_tests.py |

`docs/WORKSHOP_*`、`docs/CODEX_WORKSHOP_HANDOFF.md` 是 1.2.0 历史/共用流程。新附加模式不用普通模式的“填充当前比赛空位”，更不再同步官方房间。

## 2. 先合并真实仓库，不要整包覆盖

在已授权开发环境读取真实 origin、当前分支、HEAD、目录结构、工作区和用户修改。工作区不干净先保留现状，不自动 stash/reset。不要问用户重复提供已有 CT 参数；先读取环境。

```bash
git remote -v
git status --short
git fetch origin
git log --oneline --decorate -12
# 阅读真实差异后创建一个未占用的正常功能分支：
git switch -c feat/lan-addon-lab
```

外层交付有 Git bundle、相对于准确 1.2.0 基线的 format-patch 和完整源码 ZIP。导入只供对比，不重写真实默认分支：

```bash
DELIVERY=/absolute/path/to/dota2-lan-addon-review
git bundle verify "$DELIVERY/git/dota2-lan-addon.bundle"
git fetch "$DELIVERY/git/dota2-lan-addon.bundle" \
  refs/heads/feat/lan-addon:refs/remotes/local-lan-addon/candidate
git diff a0504f614931fae9498f65e6fa2347fc49a0e361 \
  refs/remotes/local-lan-addon/candidate --stat
```

核对是否已含等价 1.2.0 功能，按 COMMITS.txt 逐个审查/cherry-pick，或手工移植。目录不同、已有等价修复、冲突时保留用户有效改动，不强制 ours/theirs，不 force push。完整源码是可读快照，不是替换真实仓库的指令。

## 3. 开发环境先测试

依赖：Python 3.10+、requirements-dev.txt、Node（语法/Panorama mock）；Lua 测试使用本地 liblua5.4，仅开发环境需要。Ubuntu 开发机可安装 `liblua5.4-0`，不要因此向 PVE 宿主增装开发依赖。浏览器测试另需 requirements-ui.txt 和 Chromium。

```bash
bash scripts/test.sh
python3 tools/run_lua_tests.py
# 可选完整网页演示测试，仅临时 fixture，不指向生产地址：
python3 tools/demo.py --port 8788
# 另一终端
python3 tools/ui_smoke.py --port 8788 --output /tmp/lan-ui-test
```

只有实际浏览器回环导航失败时，才使用 `--offline-transport`；报告必须标注 DOM/HTTP 桥接而不是浏览器端到端。Lua 测试是 Lua 5.4 + mock 引擎，不能写成 Dota 的 Lua VM 已通过。

阅读测试报告中的间歇子进程故障：一次模拟 SteamCMD 启动前退出并报 `Unexpected error 9 on netlink descriptor 3.`，尚未定位根因。不能只引用最后通过的计数而忽略原始失败和 forkpty 多线程警告；本地连续运行启动/取消/授权测试，复现时单独修复子进程架构，不靠跳过测试。

## 4. 在有 Workshop Tools 的 Windows 电脑编译 UI

进入**本次源码根目录**。以下 `D:\SteamLibrary\steamapps\common\dota 2 beta` 只是示例。工具不安装 Steam、不修改授权库、不启动官方匹配。

```powershell
$Dota = "D:\SteamLibrary\steamapps\common\dota 2 beta"
python tools/addon_assets.py stage --dota-root "$Dota"
python tools/addon_assets.py stage --dota-root "$Dota" --apply
```

如果同名附加模式目录已存在，先检查/保存，不强制覆盖。工具自己创建且原源码未编辑的目录可加 `--replace-managed`，旧目录会保留为 source-backup；不会自动删除。源码变更后重新 stage 会隔离旧编译输出，避免无意收集旧版本。

在 Workshop Tools 中打开 `lan_dota`，使用本地 Asset Browser/资源编译功能编译 `content/.../custom_ui_manifest.xml`、`lan_setup.xml`、`lan_setup.js`、`lan_setup.css`，检查真实编译错误。需要 CLI 时先读本地 `resourcecompiler` 帮助，不把未经核验的参数写成已成功命令。

必须实际产生这四个文件（相对 game/dota_addons/lan_dota）：

```text
panorama/layout/custom_game/custom_ui_manifest.vxml_c
panorama/layout/custom_game/lan_setup.vxml_c
panorama/scripts/custom_game/lan_setup.vjs_c
panorama/styles/custom_game/lan_setup.vcss_c
```

```powershell
python tools/addon_assets.py collect --dota-root "$Dota" --output D:\lanlab-ui-assets.zip
python tools/addon_assets.py import --archive D:\lanlab-ui-assets.zip
python tools/addon_assets.py import --archive D:\lanlab-ui-assets.zip --apply
python tools/addon_assets.py client-package --output D:\lanlab-client.zip
python tools/addon_assets.py status
```

collect 核对 Tools 的源文件与交付源码相同，并检查编译资源头/块范围；这不是对编译内容语义的证明。修改 UI 后必须重新编译/收集；若修改协议，更新两端 CLIENT_REVISION 并重测。

将 UI 资源 ZIP 复制到最终合并源码环境后再 import；`addon/lan_dota/compiled` 默认 gitignore，通过构建产物传递，不依赖 git pull 自动出现。source package 脚本会包含已导入资源，记录清单。备份目录不应进入发布包。

每台玩家电脑关闭 Dota，先备份现有同名 addon，再将客户端 ZIP 中 `game/dota_addons/lan_dota` 放到其 Dota 根目录对应位置。不要假定 connect 自动下载游廊或 UI。客户端包不含天地星，AI 在服务器运行。

## 5. 升级现有 LXC，再进行 Gate A（先不启用 AI）

保持现有 pve/lxc.env、CT 和存储。正常停止比赛、完成/取消 SteamCMD 工作，备份 CT/数据后，在 PVE 的合并源码目录：

```bash
bash pve/provision-existing.sh --config pve/lxc.env --dry-run
# 核对目标实例与编译资源已进入源码之后才执行：
bash pve/provision-existing.sh --config pve/lxc.env --apply
```

不要新建或删除 CT，不猜 rootfs，不把已有 6/6GiB/250G 改掉。正常检查 nginx -t、dota-agent/dota-panel/nginx 服务。Dota 由 agent 管理，不存在单独的 `dota2.service`。本次 bootstrap 已包含 addon 目录。

面板新页“LAN 附加模式”：启用附加模式，关闭“天地星原生 Bot 实验”，停服保存。检查 compiled 文件状态。先部署模块，再启动。主配置 map/game_mode 在 addon 路线不生效；标准 dota 地图固定。

两个候选启动策略互斥：首选 `+dota_launch_custom_game lan_dota dota`；备用 `-addon lan_dota +map dota`。均保留 dedicated、LAN、allow_no_lobby_connect。命令结构已测试，但当前 Dota Linux 引擎是否接受须现场核实。不要在同一 argv 同时先 map dota 再 launch addon；不要把官方 Lobby 当作桥接退路。

记录真实进程 argv、buildid、首次新 session BOOT/STATE，随后两台原版客户端 `connect IP:27015`。要求两端 UI 可见、版本握手成功、可选队伍/位置、状态同步、无自动开局；参数变化清除准备；非配置者不能开局；重复点击只推进一次；断线配置者 30 秒后可重新选举。

### Gate A 的停止条件与排查

- ServerNoLobby/握手拒绝发生在 UI 之前：保留客户端+服务器连接日志，先解决原版连接/附加模式启动，不继续假装房间可用。
- 无 BOOT：确认 addon_game_mode.lua 是否被引擎载入、launch 策略、addoninfo 和日志；不是网页轮询故障。
- BOOT 但无 STATE/界面：核实本地 `custom_net_tables.txt` 语法、SetTableValue 返回值、生成文件路径、GameSetup/Hud manifest、四个真实编译资源和客户端版本。仅靠 mock 不证明这些格式被当前引擎接受。
- `event_identity_unresolved`：现场记录 CustomGameEventManager 的真实 callback 第一个参数及实体来源，核对当前版本。当前代码只接受能通过 EntIndexToHScript 映射到 PlayerResource:GetPlayer 的来源，**不得回退信任客户端 payload.PlayerID**。必要时只按当前引擎有凭据的来源映射修正，并增加伪造测试。
- 引擎未进 CUSTOM_GAME_SETUP 或在点击前已进选人：本局失败，不能用“多等 180 秒”假冒准备阶段。源码会发 ERROR，尝试关闭 BotThinking/暂停，保留进程供排错；面板可停服。
- UI 无按钮/样式：检查真实 Panorama 日志和编译错误，不用浏览器截图替代游戏内截图。

Gate A 不通过，不进入 AI 实验，不改“full_ai_verified”。

## 6. Gate B：天地星原生 Bot 验证

仅从服务器 Workshop 管理下载 1627071163，由用户本人完成 Steam 授权。记录条目内容 SHA 和实际标题；不得把 fixture 当成真实下载。选择一个固定版本，在 addon 页执行静态扫描。报告说明全局候选 API、入口、字面依赖及动态路径；不是 AST 类型检查或完整依赖证明。

停服开启“天地星原生 Bot 实验”，保存并启动。probe 只作用于 `game/dota/scripts/vscripts/bots` 的部署副本，不改不可变版本库，不把下载的 Bot 脚本 `require` 进游廊 VM，不伪造 GetBot、GetTeam 等。

先检查本局 generated.lua/last-launch.json/源 SHA/脚本 SHA/session 一致。游戏内选择天地星实验，明确确认未验收风险，所有人选边/准备。需要自动补 AI 时：**当前 BotPopulate API 注明需要作弊模式**。在面板主配置显式开启训练用 cheats，重启后核实 GameRules:IsCheatMode；不自动开启、不把失败隐藏掉。保持普通匹配客户端环境与私人测试分开。

开始后补 AI 只调用一次，检查实际 bot player 数量，不接受“命令已发出”即成功。观察面板的 BOT_ENTRY、BOT_API、BOT_CONTEXT、BOT_CALLBACK；每个事件必须属于本次新 session。GetBot 在 hero_selection 入口无句柄可能正常，继续检查真正思考入口，而不是只看一次 nil 就判全部失败。

缺少原生 Bot 入口或核心 API 时，在当前引擎检查真正加载路径、Workshop 原包入口、标准 dota 地图/default hero限制。若引擎根本不提供这条原生路线，报告 BLOCKED/FAIL 与证据；需要真正实现兼容层时单列代码工作，禁止插入固定返回值让测试变绿。不会回退成默认机器人冒充天地星。

## 7. Gate C：真实行为与卡顿对比

见 docs/TIANDIXING_VALIDATION.md。至少核对真实脚本选择/英雄、购买与技能、对线/支援、双方人数、难度、游戏结束和重开。**当前意向一到五号位只是房间配置，不保证对应天地星原生槽位；这个映射尚未实现，必须报告实测结果/新增适配。**不支持双边不同脚本、Turbo/CM/多地图或中途替换 AI 的承诺。

同版 Dota+同版 AI+同机器人数量下，对比玩家电脑 Local Host、其他电脑 Local Host、LXC 的帧时间尖峰与核心负载。不能只凭平均 FPS 或空载 CPU 宣称卡顿解决。

```bash
# LXC 内，输出含名称/路径，分享前审阅；不包含 Steam 密码输入。
dota-cli addon_report > /tmp/lan-addon-evidence.local.json
dota-cli status
dota-cli metrics
dota-cli logs --name server
journalctl -u dota-agent -u dota-panel -n 200 --no-pager
```

复制 compat/acceptance.template.json 到源码树外的本地验收文件。默认全部 NOT_RUN。PASS 必须写版本、环境、证据文件、观测；自动日志不签发完整 AI PASS。

## 8. 回滚、数据和真正提交

附加模式目录存在哈希清单和部署 journal。发现手工修改就拒绝覆盖。崩溃重试固定原局 bot 与 addon配置，源码变更拒绝静默换版；重试生成新 session。发生部署中断先停服并备份目标、同级 .lan-dota-old/new 及 state/lan-addon，再阅读日志恢复；不删除 journal 来绕过保护。

停服、在 addon 页关闭 enabled，保存后恢复普通启动路线。不会删除原模块或机器人库；下一次普通启动使用普通模式当前选择。移除 probe_bots 后，addon 路线会恢复面板接管前 bots（可能是用户自有脚本，并不保证就是 Valve 默认），并且本局禁用自定义 Bot 实验。

源码升级不自动迁移/还原全部状态；普通“配置备份”仍只备份 server.json，不包含 addon 配置、机器人库、Workshop缓存或对局。完整恢复用停服 PVE 备份并保护 Steam 缓存。

最终正常 commit/push 真实分支，不 force push，报告实际远端 SHA；区别“合并完成”“源码测试”“编译/客户端安装”“真实连接”“AI 行为”“卡顿对比”。只完成前几项就准确报告对应项，不虚构现场成功。
