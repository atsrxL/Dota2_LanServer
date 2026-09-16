# 测试报告 · 1.0.0

日期：2026-09-16。对象：准备发布到 GitHub 的当前源码。

## 1. 自动测试

开发机为 macOS arm64、Python 3.14.7、pexpect 4.9.0、pytest 9.1.1。实际执行：

```text
PATH="$PWD/.venv/bin:$PATH" bash scripts/test.sh
Python AST / Bash syntax: PASS
55 passed, 12 warnings in 31.69s
```

脚本执行 Bash 语法检查、全部 Python 源码 AST 解析、Node JavaScript 语法检查和 pytest。55 项测试覆盖配置与参数校验、HTTP Nginx 渲染、无密码自动会话、CSRF/Origin、可选认证模式、日志秘密脱敏、SteamCMD 模拟交互、任务互斥、维护保护、启动/停止、配置快照和诊断脱敏。

生产平台的 UDP 监听检查读取 Linux `/proc/net/udp`，macOS 开发机不具备该接口，因此非 Linux 测试只跳过该项断言；MS-A2 现场已独立确认真实 CT 的 UDP 27015 监听。

12 条警告来自 Python 在多线程进程中使用 `forkpty()` 的弃用/潜在死锁警告。测试未观察到死锁，但不能据此排除长期风险；未通过隐藏警告、`shell=True` 或无限 systemd 重启来规避。

## 2. MS-A2 现场验证

目标为 CT 270：Ubuntu 24.04、非特权、6 vCPU、6144 MiB、250 G rootfs、`nesting=0`。已完成真实 Steam 登录、App 570 安装和 validate，manifest 为 `StateFlags=4`、buildid `25329722`。

首次启动失败的直接原因是当前 `dota.sh` 强制要求 sniper runtime，而官方 pressure-vessel 在该 LXC 中因 namespace 权限被拒绝。修复后启动器优先执行 Valve 的 `game/bin/linuxsteamrt64/dota2`；现场实际加载 `dota` 地图、进入 `ss_active`、输出 `64 player server started`，并监听 UDP 27015。正式代理启动任务为 success，持续观察超过 10 分钟，未发生 OOM。

面板现场入口为 `http://192.168.123.66:8443`，按用户要求不启用 HTTPS、不校验网页密码；LAN 白名单、Host、Origin、CSRF 和 HttpOnly/SameSite 会话仍保留。公开仓库不包含 Steam 密码、Guard、登录缓存、运行日志、TLS 私钥或现场配置。

## 3. 界面检查边界

仓库中的 `ui-test-output.json` 和预览截图来自更早的离线 DOM/模拟服务检查，不能证明当前无密码流程、生产 Nginx 或真实浏览器端到端行为。本轮已完成 JavaScript 语法检查和 Web API 自动测试，但未重新运行 Playwright 界面检查。

## 4. 尚未执行

| 项目 | 状态 |
|---|---|
| 两台真实 Dota 2 客户端连接、选人并完成一局 | NOT RUN |
| 当前无密码 HTTP 面板的独立浏览器端到端自动化 | NOT RUN |
| 多人/机器人高负载下 6 GiB 长时间稳定性 | NOT RUN |
| Valve 后续构建对直接二进制启动方式的兼容性 | 每次更新后需复验 |

代码测试、服务端真实启动和客户端完整对局是不同层次；未完成的项目不能由端口监听或模拟测试替代。
