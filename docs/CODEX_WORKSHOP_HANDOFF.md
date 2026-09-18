# Codex 接手：Workshop Bot 下载与下一局启用

## 0. 范围与基线（必须先读）

本轮在原 HTTP 免登录/监控候选提交 `ea66f5bfdf0c5f1b7224750a682156c85f6a36fd` 上开发。该提交来自前次独立本地 Git bundle，不是已确认的用户 origin 祖先。目标仍是 `https://github.com/atsrxL/Dota2_LanServer`。

这次对目标仓库的 Git/web 读取未成功；GitHub 连接未安装/授权。没有取得用户当前代码，没有 push、创建远端分支/PR/tag，没有 PVE 访问。新提交实际 SHA 以交付外层 COMMITS.txt 为准。不要因为代码路径相似就覆盖真实仓库，不使用 force push 或 reset --hard。

用户本轮需求：网页输入机器人 ID（例 1627071163）→ 服务端下载/检查/安装 → 下一局使用。保留 HTTP、无面板密码登录、CPU/每核心/内存监控和 Steam Guard。固定 Ubuntu 24.04 非特权 LXC 6 vCPU / 6144 MiB / 250 G，不启用 Docker、GPU、nesting 或公网入口。

已实现下载器/版本库/启动前部署/网页/CLI/API/归档解析/测试。**未实现原生房间同步、双方不同机器人或自动还原队伍位置。真实 bot 加载仅是待验收策略，不能宣称完成整条房间桥接。**

## 1. 最短阅读路径

AGENTS.md → 本文件 → WORKSHOP_TEST_REPORT.md → WORKSHOP_BOTS.md。代码优先按任务阅读：

| 文件 | 职责 |
|---|---|
| panel/bot_files.py | 安全路径、ZIP、VPK1/2、唯一 Lua 根、内容清单 |
| panel/bots.py | 固定 Valve 元数据、下载位置检查、不可变版本、选择/部署/恢复 |
| panel/steam.py | 现有 Steam/Guard 流程复用；workshop_download_item 的成功判断 |
| panel/agent.py | 单任务锁、取消、API 动作、启动/崩溃复用固定版本 |
| panel/common.py / process.py | local-dev 启动参数和一次性入口日志检测 |
| panel/static/bots.js | 新网页，纯原生 JS；不得加账号登录 |
| tests/test_bots.py | 格式、故障、中断、安全和模拟协议测试 |
| tools/demo.py / ui_smoke.py | 本机模拟环境和浏览器检查，不是真实 Steam |

## 2. 合并到真实仓库

先在已授权开发环境读取实际 origin、默认分支、目录层级、工作区和用户改动。工作区不干净则停下，不自动 stash/reset。取真实最新代码，保留有效变动，建立新的正常功能分支。若目录在子文件夹中，按对应层级移植，不能整包复制压过去。

```bash
git remote -v
git status --short
git branch --show-current
git fetch origin
git log --oneline --decorate -12
# 阅读当前代码之后创建一个未占用的功能分支：
git switch -c feat/workshop-bots
```

外层 bundle 是完整本地证据，里面也含上一轮 HTTP/监控提交。可以先导入远端跟踪式名称，避免改变真实分支：

```bash
DELIVERY=/absolute/path/to/dota2-workshop-bots-review
git bundle verify "$DELIVERY/git/dota2-workshop-bots.bundle"
git fetch "$DELIVERY/git/dota2-workshop-bots.bundle" \
  refs/heads/feat/workshop-bots:refs/remotes/local-workshop/candidate
# 查看候选新改动，而非整体覆盖：
git diff ea66f5bfdf0c5f1b7224750a682156c85f6a36fd refs/remotes/local-workshop/candidate --stat
```

确认用户仓库已含等效 HTTP/监控基线后，可逐个审查外层 patches 并 git am -3 或按 COMMITS.txt cherry-pick。已有相同功能、目录不同或冲突时手工合并。没有上一轮基线时，先合并其等效部分，再移植本轮；不要为了套 patch 撤销用户修改。发生冲突可正常 abort，不能全局选 ours/theirs。

测试通过后正常 commit、push 实际功能分支，并报告真实远端 SHA。当前用户直接 git pull 取不到这份未推送补丁。

## 3. 必须保留的实现约束

- HTTP/no-auth、LAN/Host/Origin/CSRF、root-owned 代码、非 root Steam/Game、固定 RPC 与无任意 Shell。
- Bot 元数据必须 App570 + Bot标签，下载命令参数只接受数字字符串，拒绝任意 URL/路径/合集。不要为“能下载”关闭 TLS 校验或跳过所有身份/格式检查。
- 游戏 install/update/validate 保持停服授权和维护标记；Bot download/check 可以在比赛中运行，因为只写独立缓存/库，不改已部署目录。不同时开两个 SteamCMD。
- 下载/校验失败不能切换当前或下一局脚本；旧缓存不能冒充新下载成功。取消在最后提交边界可能留下已安装但未选中的版本，明确报告。
- 不可变版本/运行快照/下一局选择分开。自动崩溃重试复用旧局版本，不应用 pending selection。
- 不手工覆盖受管文件；哈希发现外部改动则保留并停止，不删掉用户修改。
- Entry probe 只修改部署副本。只声称一个入口被执行，不声称完整 AI、站位、模式或联机正确。
- 原生房间同步尚未实现，不能用预填 ID 或复制 Connect 按钮冒充它。

## 4. 开发测试

在开发环境安装 requirements-dev.txt，再运行 `bash scripts/test.sh`；本地可能有 pexpect/forkpty 多线程警告，不忽略其风险。UI 测试依赖 requirements-ui.txt 与 Chromium：

```bash
python3 tools/demo.py --port 8788
# 另一终端：
python3 tools/ui_smoke.py --port 8788 --output /tmp/dota-workshop-ui
# 若当前浏览器环境明确拦截回环导航，仅做降级 DOM/请求桥接测试：
python3 tools/ui_smoke.py --port 8788 --offline-transport --output /tmp/dota-workshop-ui
```

每次跑 UI 使用全新 demo（它会新建临时 fixture 目录）。`--offline-transport` 不等于真实 HTTP 浏览器导航，更不等于 PVE/Nginx 验收。截图中的资源/脚本/日期来自测试环境。不要在生产设置 DOTA_TEST_ROOT 或使用 fake_steamcmd/fake_dota。

改文档后运行 `python3 tools/build_help.py`；打包 `python3 scripts/package.py --output /absolute/path/outside/source` 并重新验证 SHA256SUMS。

## 5. 已有 LXC 升级

先核实真实 CTID、存储和 IP；保留已有 lxc.env，不猜资源、不重新建 CT。正常结束下载/游戏后，在 PVE 上的**合并后源码目录**执行：

```bash
bash pve/provision-existing.sh --config pve/lxc.env --dry-run
# 用户授权且检查输出后：
bash pve/provision-existing.sh --config pve/lxc.env --apply
```

该步骤重启代理会中断比赛。源码升级不删除 /var/lib/dota2、/srv/dota2、/srv/steamcmd；新的 bot-library 在 steam HOME 下建立，不必改服务权限白名单。检查 nginx -t、dota-agent/dota-panel/nginx 状态，HTTP 入口仍直接进入；GET /api/bots 和 bots.js 均已部署，6/6GiB/250G 资源未变。

`dota2.service` 并不存在。Dota 游戏进程由 dota-agent 管理；使用面板或 dota-cli start/stop，不另起一个后台游戏进程。

## 6. 真实验收——最重要的未完成部分

用用户实际账号下载 `1627071163`，记录当前 Dota buildid、条目标题/更新信息、缓存实际目录和格式、归一化 SHA、完整任务结果，不能记录密码/Guard。对真实缓存包确认入口与依赖目录是否正确；如果格式超出当前支持，先保留包并添加最小脱敏 fixture 和解析测试，不关闭路径/大小检查。

在普通 All Pick 上先测试同一套脚本、单一难度。确认启动参数不报未知变量；local-dev 路径和 `dota_bot_practice_script 0` 是本版候选策略，不是实测结论。两台真实客户端连接、选队后再填充机器人，检查入口日志与游戏行为。没有入口可依次检查 probe 开关/入口名称、是否生成 Bot、Lua 错误/路径大小写、游戏载入脚本方式，而不是把页上的版本信息当作已执行。

验收要单独记录：AI 行为/目标脚本特征、双方阵营、英雄选择、房间槽位依赖、难度是否有效、完整对局、下一局、Bot 更新/回滚，以及用户原来 Local Host 的卡顿是否改善。当前未读取原生房间，因此不能承诺其位置已恢复；不得为了这项指标伪造一个 Lobby 快照。

## 7. 部署中断处理

机器人部署同文件系统暂存 + journal。下次启动前尝试恢复原 bots；恢复日志损坏、外部目录替换或备份缺失则拒绝自动覆盖。UI 显示 recovery_error。

人工排查先停游戏和代理，备份 bot-library 全目录、bots、同级 .dota-panel-bots-old/new；读取 journal 的事务号、previous_deployment、old/new 与标记，比较内容 SHA 后选择恢复。不要直接删除 journal/marker 让系统以为已恢复，也不要无条件 rm -rf 原始备份。恢复成功还要再次校验并小规模开局。

## 8. 未来的原生房间桥接

下一阶段应验证真实 GC 的房间配置读取、Workshop标识/LocalDev映射、队伍/槽位还原，再调用本版固定 Bot 选择接口。不要默认“点原生开始”会分配到私人 LXC。下载器和版本库已经独立完成，但不是这套 GC 桥接器。
