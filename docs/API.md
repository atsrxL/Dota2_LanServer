# API 与本地 CLI

API 仅供面板使用，不提供 bearer/API token 或外部自动化密钥。生产入口为受信任 LAN 上的 HTTP。首次访问 `/api/session` 自动创建 HttpOnly 会话；所有 POST 需要有效 Cookie、同源 Origin、`Content-Type: application/json` 和 `X-CSRF-Token`，请求体最大 16 KiB。

| 方法 | 路径 | 行为 |
|---|---|---|
| GET | /api/session | 自动创建面板会话并返回 CSRF |
| POST | /api/login | 兼容入口；无需密码，轮换 HttpOnly Cookie |
| POST | /api/logout | 注销服务器端会话 |
| GET | /api/status | 运行代理、本地安装、任务、磁盘/内存/UDP状态 |
| GET/POST | /api/config | 读取/完整保存严格 schema 的服务器配置 |
| POST | /api/actions | 提交固定动作；202 表示受理，非完成 |
| GET | /api/jobs | 最近 100 条任务，按新到旧 |
| POST | /api/input | {job_id,value}；向当前等待任务补交一次性秘密 |
| POST | /api/cancel | {job_id}；取消当前 SteamCMD 任务 |
| GET | /api/logs?name=... | server / agent / 合法 job-id 的已脱敏日志 |
| POST | /api/console | status / bots / pause，或 say + text |
| GET | /api/backups | 最近 20 份配置快照 |
| GET | /api/backup?name=... | 下载单个配置快照 |
| GET | /api/diagnostics | 下载已筛选的诊断 JSON |

动作参数：`action` 为 login/install/update/validate/start/stop/restart/backup/restore。Steam 动作可含 username/password/guard；密码与 guard 不持久化。install/update/validate 可含 stop_server 和 restart_after（严格布尔）。restore 需要合法 backup 文件名，且游戏已停。

常见状态码：400 格式/字段非法，401 会话缺失/过期，403 来源/CSRF/Host 不符，409 任务冲突或安装/授权状态不允许，413 体积超限，415 非 JSON，503 代理不可用。

本地代理：`/run/dota-agent/control.sock`，组 dota-control 可连接，协议为一行 UTF-8 JSON `{op,data}`，返回一行 `{ok,result}` 或 `{ok:false,error,code}`。没有 HTTP 用户可提交的任意 RPC 名称透传接口。直接访问该 socket 等价于拥有本实例的管理权限。

CLI 在 LXC root 或允许使用该 socket 的本地账号执行：

```bash
dota-cli status
dota-cli install --username SERVER_STEAM_LOGIN   # 交互 getpass，提交后查询 jobs/logs
dota-cli update --username SERVER_STEAM_LOGIN --stop-server --restart-after
dota-cli jobs
dota-cli logs --name job-YYYYMMDD-HHMMSS-xxxxxxxx
dota-cli input --job-id job-YYYYMMDD-HHMMSS-xxxxxxxx
dota-cli cancel --job-id job-YYYYMMDD-HHMMSS-xxxxxxxx
dota-cli backup
dota-cli restore --name cfg-YYYYMMDD-HHMMSS-xxxxxxxx.json
```

CLI 是异步提交，不要把“返回 job-id”当作安装/停服完成。使用 jobs 确认最终状态；验证码等待也须通过后续 input 或网页提交。
