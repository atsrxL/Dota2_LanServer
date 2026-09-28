# 1.2.0 Workshop 测试报告

日期：2026-09-16。本地候选，未 push。实现提交 `6a14da985d0de1c49dd47c37a4d3810e842c550d`；文档及交付提交见外层 COMMITS.txt。基线为前次独立本地 `ea66f5bfdf0c5f1b7224750a682156c85f6a36fd`，不是已核实的用户远端当前代码。

## 实际运行结果

| 检查 | 结果 | 范围 |
|---|---|---|
| Python AST / Bash 语法 | PASS | scripts/test.sh 的完整扫描 |
| pytest | **161 passed / 29 warnings** | 真实临时文件与 PTY/进程、模拟 Steam/Dota，40.61 秒 |
| 浏览器交互 | **22 项通过** | Chromium，离线 DOM + Python 转发至真实回环 WSGI 的请求桥接 |
| 未捕获 JavaScript 异常 | **0** | 上述 UI 检查范围内 |
| 手机布局 | PASS | 390px，无页面横向溢出 |
| git diff --check | PASS | 本轮源码/文档空白检查 |

环境 Python：3.13.5。原有 86 项与本轮新增 75 项一起通过。没有添加运行时 Python 依赖；测试依赖见 requirements-dev.txt / requirements-ui.txt。

29 条警告中，28 条是现有 pexpect 使用多线程 forkpty 的 Python 3.13 警告（潜在死锁风险，未修复），另 1 条来自特意构造重名 ZIP 的拒绝测试。未屏蔽警告。并不因为这次通过就保证目标 Ubuntu 上无并发风险。

证据原文：`workshop-evidence/code-test-output.txt`、`workshop-evidence/ui-test-output.json`。截图为 `workshop-panel-preview.png` 和 `workshop-mobile-preview.png`。

## 覆盖的关键行为

ID 字符串/uint64/注入拒绝，App/类型/Bot标签校验，固定 Valve 元数据请求；受管目录与指定ID下载成功判断；Lua根/依赖保留；ZIP 路径穿越、链接、重名和大小写冲突；VPK1/2嵌入/分卷、CRC和越界；大小/数量限制；下载失败、空目录、错误ID、缺少成功标记、Guard补交、取消与任务互斥。

不可变内容版本、安装不等于部署、手动选下局、线上下载不换当前脚本、崩溃重试固定旧版、手动重启应用新版、原bots备份/停用恢复、手工改动拒绝覆盖、模拟重命名中断的journal恢复、损坏journal保留原数据，以及入口标记与完整AI验收区分。

网页核对/下载/秘密清除与脱敏、下一局/当前局区分、默认/回滚、填充按钮、HTTP免登录、原有CPU/内存监控与断线恢复均在检查范围。

## 浏览器限制

尝试真实浏览器导航 `http://127.0.0.1:8788/` 被当前工具环境策略拒绝：`ERR_BLOCKED_BY_ADMINISTRATOR`。之后使用明确的 --offline-transport 路径：浏览器加载本地 HTML/CSS/JS，fetch 经 Python 转发到本机真实 WSGI 服务，返回真实 API/模拟进程结果。

所以这 22 项不能证明生产 Nginx、真实浏览器 HTTP 导航/下载、局域网防火墙、PVE部署或Steam联机可用。它不是生产环境端到端测试。截图里的“天地星AI · 测试元数据（非实际下载）”明确来自 fixture，不是上游内容；探针的测试输出由模拟程序产生，没有执行真正 Lua。

## 未执行的真实验收

- 未取得用户 GitHub 当前仓库、未合并用户已提交改动，未远端 push/PR/tag。
- 未访问或部署 PVE/LXC，未实测 Ubuntu24.04 的 Nginx/Waitress/Steam运行库。
- 未用真实 Steam 账号下载 1627071163，未获取/审计其真实 Lua 或包格式。
- 未在当前 Dota Linux -dedicated 中验证 local-dev目录、script0/difficulty/等待玩家控制变量。
- 未验证真实客户端连接、目标机器人AI、选人/站位/难度、完整对局或原LocalHost卡顿改善。
- 原生房间读取/同步不在本版实现中，不能作为测试通过项。

完整现场清单在 ACCEPTANCE.md / CODEX_WORKSHOP_HANDOFF.md。后续真实验证应另建本地验收记录，不改写本报告为“已实测”。

## 打包和 Git 证据

打包器检查源码ZIP CRC与逐文件SHA。外层交付另包含patch与完整bundle，最终commit、bundle导入、patch重放树一致性、ZIP结果在外层 DELIVERY_VERIFICATION.json。不要只以本段描述代替运行证据。
