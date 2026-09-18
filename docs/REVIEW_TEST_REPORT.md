# 本轮补丁测试报告 · 1.1.0 本地候选

## 结论与范围

2026-09-16，本轮最后执行：**86 项代码/模拟进程测试通过，12 条已知警告；16 项浏览器界面/模拟服务检查通过，0 个未捕获 JavaScript 异常。**

测试对象是原交付 1.0.0 ZIP 的本地修改，不是 GitHub 仓库当前版本。未取得目标仓库代码与历史，未完成其 diff 审查、合并、远端 commit/push。不能把这份报告表述成用户 PVE 已部署或真实 Dota 2 联机成功。

## 1. 自动测试

```bash
bash scripts/test.sh
```

```text
Python AST / Bash syntax: PASS
86 passed, 12 warnings in 18.23s
```

原始输出（只清理终端 ANSI 控制符）：`review-test-output.txt`。脚本检查全部 Python AST、Bash 语法、各静态 JavaScript 的 Node 语法，然后运行 pytest。不是 ShellCheck 审计。

环境：Linux x86_64；Python 3.13.5、pexpect 4.9.0、pytest 9.0.2；Chromium 144.0.7559.96（Debian）。不是目标 Ubuntu 24.04 LXC。

覆盖免登录读取和无 Cookie、无登录/退出入口、HTTP 同源/CSRF/Host/请求体校验、固定动作、原有维护互斥和 Steam 模拟协议；新增 CPU 配额/累计量差分、每核 guest 防重复计数、LXCFS 编号与 affinity 区分、cgroup 根而非代理子组、内存/缓存/工作集/Swap/OOM、首次采样/重置/热插拔/配额变化、缺失/无限上限、降级来源与共享采样缓存等。

12 条警告来自 Python 多线程调用 forkpty，可能引起子进程死锁。本轮没有观察到死锁，但没有解决或隐藏该风险。目标环境仍需压力测试；不可用 shell=True、特权容器或权限放宽代替修复。

## 2. 浏览器检查

```bash
# 终端 A，只启动本机模拟环境，不连接真实 Steam
python3 tools/demo.py --port 8788
# 终端 B
python3 tools/ui_smoke.py --port 8788 --offline-transport --output /tmp/dota2-ui-review
```

结果：16 checks passed；page_errors=[]。原始 JSON：`review-ui-test-output.json`。截图：`review-panel-preview.png`、`review-panel-mobile-preview.png`。

模式是 Chromium 中离线 DOM + Python 转发的真实回环 HTTP 请求。它验证前端 JavaScript 与模拟服务的交互，但**不是浏览器原生 HTTP 导航、Nginx 代理/ACL/CSP、生产网络或 PVE 的端到端验收**。UI 中页面隐藏事件为合成事件；未宣称操作系统真实后台标签页调度测试。

检查 HTTP 无登录/退出控件、无密码状态 API、总 CPU/每核/内存和来源、趋势累计、监控接口 503 后清空失效读数且自动恢复、页面隐藏暂停/恢复、Steam 输入清空与脱敏、任务历史、日志/固定控制台、配置、备份、诊断、帮助页、390px 移动端无横向溢出及无 JS 未捕获错误。

截图显示的是本次测试运行时的资源配额，不是用户分配的 6 核/6 GiB。Dota 与 SteamCMD 均使用 tests/fakes 的模拟进程。不能把 TEST-4242 或回环端口当作真实游戏 Build/连接信息。

## 3. 尚未执行

| 项目 | 状态 |
|---|---|
| 用户 GitHub 当前修改与历史审查、合并、push | NOT DONE：未取得仓库访问与写入连接 |
| PVE 新建/已有 LXC 部署、Ubuntu apt 依赖 | NOT RUN |
| Nginx 实机 HTTP 无 TLS/跳转、LAN ACL、跨站拒绝 | NOT RUN（只完成代码级测试） |
| 目标 LXC cgroup 根/LXCFS 范围、6 核与 6442450944 字节上限核对 | NOT RUN |
| 实际 Steam 账号/Guard、App 570 安装更新 | NOT RUN |
| 实际 Dota Linux 进程、两客户端完整对局 | NOT RUN |
| 长时间资源采样与 forkpty 压力测试 | NOT RUN |

现场结果必须另写 docs/ACCEPTANCE.local.md（脱敏），不把 NOT RUN 批量改为 PASS。打包 CRC、逐文件 SHA-256 与本地 Git bundle/补丁重放验证由交付包外层 DELIVERY_VERIFICATION.json 记录，不用旧报告冒充。
