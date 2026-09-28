# LAN 附加模式与天地星验证：本地测试报告

版本：1.3.0 本地候选版。日期：2026-09-18。开发基线：`a0504f614931fae9498f65e6fa2347fc49a0e361`。该基线是前次交付的独立本地历史，未与用户 GitHub 最新代码合并；无远端 push、无实际 PVE 访问。

## 结果总览

| 检查 | 实际结果 | 范围 |
|---|---|---|
| `bash scripts/test.sh` | **201 passed，29 warnings** | Python/Bash/JavaScript 语法、完整回归和模拟进程；含本轮 Lua/JS mock 测试。 |
| `python3 tools/run_lua_tests.py` | **3 个 Lua mock suite 通过** | 所有新 Lua 源码经本地 liblua5.4 加载；engine/identity/room 在模拟引擎中执行。不是 Dota VM。 |
| 网页面板 | **27 项检查通过，0 个未捕获 JS 异常** | 实际 Chromium DOM，Python 转发到真实回环 HTTP 的演示接口；假 SteamCMD/假 Dota，非 PVE。 |
| 浏览器直接 HTTP 导航 | **未通过，环境阻止** | 原尝试 `net::ERR_BLOCKED_BY_ADMINISTRATOR`；随后才使用明确标识的 `--offline-transport`。不把降级模式称作浏览器 HTTP 端到端。 |
| 资源状态检查 | **ready=false（预期）** | 未编译的真实源码，面板拒绝附加模式启动。没有伪造 vxml_c/vjs_c/vcss_c。 |
| XML/JS 接口 | 语法与 mock 契约通过 | 标识、事件负载、视图更新；没有真实 Panorama 渲染。 |
| Git bundle、补丁重放、ZIP | 见外层 `DELIVERY_VERIFICATION.json` | 最终打包后记录实际验证结果，不能从单元测试推断。 |

上述计数不能相加成额外的独立测试数量：3 个 Lua suite 和 Panorama mock 已包含在 201 项 pytest 中。网页 27 项为另一次浏览器检查。

## 环境与原始记录

开发环境：Linux，Python 3.13，Node 22，本地 liblua5.4，通过 Playwright 使用 Chromium。生产依赖 waitress 在此环境未部署，演示使用标准库 WSGI。没有 Dota 2 游戏二进制、Steam 账号、Workshop Tools 编译器或目标 LXC。

原始输出随外层交付放在 `review/`：

- `full-tests-release.txt`：最后一次完整测试，不是截取通过片段。
- `lua-tests-release.txt`：本地 Lua 运行输出，事件中的 fixture/session 不是实机证据。
- `ui-test-output.json`：27 项逐项检查与测试传输方式。
- `full-tests-intermittent-failure.txt` / `subprocess-intermittent-failure.log`：上述一次间歇故障，未隐藏。
- `browser-http-blocked.txt`：实际浏览器直接访问失败的原始原因。
- `assets-status.json`：交付源码未包含编译资源的状态。
- `lan-addon-panel-preview.png` / `lan-addon-mobile-preview.png`：真实网页截图，内含模拟数据，不是游戏内截图。

## 已覆盖的本轮边界

**部署与启动。**配置严格校验；只能选择两个固定启动候选；不把普通 map/模式参数混进 addon 路线；只有停服时可改 addon 配置/部署；先验证真实编译资源，再部署 Bot；外部修改、不受管目录、哈希不符、source 变更、进程重试固定版本和部署中断恢复均有测试。

**资源构建。**stage 默认 dry-run、保留旧受管副本；拒绝用户手工修改覆盖；收集固定四个输出并核对对应源码；ZIP 固定白名单/大小/链接/重复/路径穿越限制；Source2 v12 头与块范围检查；客户端包不带真实 Bot 代码或服务器会话。synthetic_resource 只存在测试函数和临时测试目录，没有作为资源交付。

**准备阶段。**服务器身份来自事件来源实体，不采用客户端声称的 PlayerID；版本握手、断线重连、主持权、队伍/意向位置冲突、参数版本、修改后清除 ready、全部到齐、主机开始权限、单次推进和断线主机再选举。客户端游戏状态不可冒充服务器判定。

**开局与错误。**原生 Bot 模式的能力/实验确认/作弊前置检查；BotPopulate 只调用一次，实际人数不足会失败；引擎未经主持人推进会记录错误；准备阶段不会用超时假装有等待机制；错误会保留心跳并尽力暂停/关闭思考以便排错，不声称暂停必定成功。

**天地星验证。**静态扫描不执行下载 Lua；保持文件偏移的字符串/注释遮蔽；字面依赖与动态路径明确区分；仅部署副本增加探针；原函数返回/错误不被吞掉；探针不伪造 GetBot；当前进程 session 过滤、历史日志拒绝、错误上下文区分、计数和缓冲有界，超长数字不终止日志读取线程。

**HTTP/既有功能。**保留免面板登录、Host/Origin/CSRF、受限动作、日志脱敏、串行工作、监控、Workshop 版本库及普通服务器路线。网页版缺资源/无心跳/仅静态扫描时不会显示完整 AI 通过。

最后复核还将 `custom_net_tables.txt` 从不适用的 KV1 字典改为带文本头的 KV3 数组，并新增结构回归测试。此测试不是引擎 KV3 解析器；当前二进制仍要现场确认。

## 未消除的 29 条警告

**复跑曾出现一次真实测试失败**：`test_bot_download_guard_cancel_and_task_mutex` 的模拟 SteamCMD 在显示提示前退出，子进程日志为 `Unexpected error 9 on netlink descriptor 3.`。没有将该测试跳过、重试标为通过或隐藏异常。补充了失败断言中的任务诊断，保留原始失败报告及日志；后续完整复跑结果单独记录。根因没有定位，不将其归为已修复；它与线程中 fork/PTY 的已知风险需要本地进一步排查。

28 条是 Python 3.13 在多线程进程调用 pexpect/forkpty 的 DeprecationWarning（test_agent 12、test_bots 16），提示子进程潜在死锁风险。本轮不隐藏、不宣称解决；后续应单列子进程启动架构修复。

1 条是故意重复 ZIP 文件名测试触发的 UserWarning，用来确认归档拒绝行为。

## 尚未执行，不能写成 PASS

真实 origin 合并；Ubuntu 24.04/PVE 安装升级；Nginx 生产入口；Workshop Tools 编译与玩家安装；当前 Linux dedicated 识别启动候选；原版客户端进入准备阶段；真实事件身份与 NetTable/manifest 装载；1627071163 真下载/选人/思考；天地星位置/难度适配；两台玩家完整对局与下一场；Local Host 卡顿对比。

**本轮没有实现“把天地星所有 Bot API 转为游廊 API”的完整兼容层。**交付的是保留原生 Bot 路线的验证工具和有边界的开局控制。位置只记录意向；若需要天地星槽位映射须据实机结果适配，不能用界面可选择冒充已生效。

本地 Codex 按 `CODEX_LAN_HANDOFF.md` 的 Gate A（无 AI 连接/准备）→ Gate B（实际脚本探针）→ Gate C（行为/卡顿）推进，将真实证据写入 `compat/acceptance.template.json` 的工作副本。默认所有现场项目 NOT_RUN。
