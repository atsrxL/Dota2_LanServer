# API 与本地 CLI

API 对白名单内 LAN 设备免登录开放。生产入口为 HTTP。所有 POST 需要同源 Origin、`Content-Type: application/json` 和 `X-CSRF-Token`；请求体最大 16 KiB。不使用登录 Cookie、管理员密码或登录会话。

`GET /api/session` 自动返回 `{auth_required:false,mode:"lan-no-auth",transport:"http",csrf,version}`。csrf 是防跨站操作令牌，不是密码或认证凭据；白名单内任何客户端都可取得。后端重启会更换令牌，网页自动重新获取；失败的变更请求不会自动重放。

| 方法 | 路径 | 行为 |
|---|---|---|
| GET | /api/session | 免登录读取版本与自动 CSRF 令牌 |
| GET | /api/metrics | CPU/每核心/内存只读快照；来源、采样时间与缺失值说明见 MONITORING.md |
| GET | /api/bots | 机器人元数据/安装版本/下一局与部署状态，不包含 Lua 文件正文 |
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

常见状态码：400 格式/字段非法，403 来源/CSRF/Host 不符，409 任务冲突或安装/授权状态不允许，413 体积超限，415 非 JSON，503 代理不可用。

本地代理：`/run/dota-agent/control.sock`，组 dota-control 可连接，协议为一行 UTF-8 JSON `{op,data}`，返回一行 `{ok,result}` 或 `{ok:false,error,code}`。没有 HTTP 用户可提交的任意 RPC 名称透传接口。直接访问该 socket 等价于拥有本实例的管理权限。

CLI 在 LXC root 或允许使用该 socket 的本地账号执行：

```bash
dota-cli status
dota-cli metrics
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


## Workshop 动作（1.2.0）

所有动作继续 POST /api/actions，返回 202 + job-id 仅代表受理。bot_download / bot_check 可取消；只允许一个活动变更任务。Bot 下载可与正在运行的比赛并存，但不能与第二个 SteamCMD 并存。

```json
{"action":"bot_check","item_id":"1627071163"}
```

```json
{"action":"bot_download","item_id":"1627071163","select_after":true,"difficulty":2,"entry_probe":true}
```

下载账号可复用服务器配置的 steam_username；也可在请求中带 username/password/guard，秘密只交给 SteamCMD、不持久化。缓存失效则使用已有 /api/input 补交。原始体不要记录在网关/调试日志。ID **必须是字符串**，不能用 JSON number 传 uint64。

| action | 参数 | 效果 |
|---|---|---|
| bot_check | item_id | 固定 Valve 元数据接口，结果在 job.workshop |
| bot_download | item_id、可选授权、select_after、difficulty、entry_probe | 下载、检验、安装；可选设为下一局 |
| bot_select | item_id、可选完整 version SHA、difficulty、entry_probe | 没给版本则选该条目最新安装内容；下次启动部署 |
| bot_default | 无 | 下一局停用面板脚本，恢复接管前目录 |
| bot_rollback | 无 | 恢复上次选择，不中断当前局 |
| bot_remove | item_id、完整 version SHA | 删除未被下一局/上次选择/运行/部署引用的版本 |

难度整数 0..3，entry_probe 默认 true；下载 select_after API 默认 false（网页复选框默认 true）。只接受严格布尔，不把字符串 "false" 当作 false。拒绝合集、非 App570、非 Bot标签及自定义下载 URL。

GET /api/bots 包含 items[].versions[]、selected、previous、deployment、recovery_required/error 和 limits。GET /api/status 新增 bot_runtime.selection、entry_seen、acceptance。not_verified 和 entry_executed_not_full_ai_verified 均不等价于完整比赛验收成功。

```bash
dota-cli bots
dota-cli bot_check --item-id 1627071163
dota-cli bot_download --item-id 1627071163 --username SERVER_STEAM_LOGIN --select-after
dota-cli bot_select --item-id 1627071163 --difficulty 2
dota-cli bot_default
dota-cli bot_rollback
```

CLI 仍为异步任务。任意 shell、工作目录参数和文件上传并未开放。完整功能/限制见 WORKSHOP_BOTS.md。
