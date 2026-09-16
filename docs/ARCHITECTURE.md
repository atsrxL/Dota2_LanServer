# 架构与实现说明

## 请求与权限流

浏览器 → Nginx HTTP/LAN allow → Waitress 127.0.0.1:8765 → WebApp 自动会话/CSRF → Unix socket RPC → Manager 固定动作 → SteamCMD/GameProcess 的 PTY。

PVE 脚本只在宿主以 root 创建 CT、上传文件、配置该 CT 防火墙。容器 bootstrap 以 LXC root 安装包/受限账号/配置服务。正常运行时没有 root 控制代理、sudo 白名单或 Docker socket。

`dotapanel` 只读 root-owned 应用与自己的 auth 配置，能访问 dota-control socket，但不能直接读取 `/var/lib/dota2`（0700）。`steam` 可写下载目录和状态；不可改 root-owned 应用、unit 或 Nginx。两个服务都设置 NoNewPrivileges 和空 CapabilityBoundingSet；因为 SteamCMD 是 32 位组件，不能添加 SystemCallArchitectures=native。

## 进程与重启

独立运行代理管理真实子进程，网页只是控制接口。网页重启不触碰子进程。代理/容器重启时终止子进程并将历史运行任务标为 interrupted。systemd KillMode=mixed 配合代理退出钩子；部署时先正常停服。

GameProcess 优先 `game/dota.sh`，其次根目录 `dota.sh`，两者都缺失才使用 `game/bin/linuxsteamrt64/dota2`。使用参数数组，不用 shell=True，不提供任意执行路径。固定 `-dedicated -console -game dota` 与 `+sv_lan 1`；UI 参数单独验证。Steam 库路径补入 LD_LIBRARY_PATH，不能据此推断未来所有运行库都已满足。

pexpect 创建 PTY 以适配 SteamCMD 与游戏控制台。Steam 密码和 Guard 在提示出现时才经非回显 PTY 发送，不进入命令行、systemd 环境或配置。Python 字符串不承诺可验证的内存擦除；进程内临时保存仍是敏感数据。

## 状态机与锁

动作：login / install / update / validate / start / stop / restart / backup / restore。

单实例只允许一个变更任务。状态：running → waiting（密码/Guard）→ running → success/failed/cancelled。代理意外重启会把未完成状态改为 interrupted；不会根据历史 PID 盲目接管陌生进程。

下载前记录 maintenance.json。SteamCMD 成功标志、App manifest StateFlags=4、支持的 Linux 启动入口都满足才解除。退出码 0、收到 Steam>、目录存在，均单独不足以代表成功。取消/失败不清理保护标记；再次成功更新/校验解锁。

服务器在线时更新须显式 stop_server=true；restart_after=true 仅在原本在线、维护成功时恢复。更改配置在活动任务期间拒绝，并先保存快照；游戏参数在下次启动生效。

## 持久化与配额

server.json：完整启动设置；jobs.json：最近 100 条非敏感任务元数据。使用临时文件、fsync、os.replace、目录 fsync。备份 20 份；日志主片段超过 4 MiB 后轮转为一个 .1。最多保存对应 100 个任务的主/旧日志，限制近似上限，单行输出也限长。

SafeLog 只挂接 logfile_read，不记录发送内容；逐行缓冲后替换已知密码/Guard，防止秘密跨输出块而漏掉。原始 Valve 日志/缓存不通过面板提供，不进入配置备份或诊断。仍不把脱敏当作对任意未知 token 的绝对保证。

## 网页、安全与就绪

单进程 Waitress 多线程，Auth 共享带锁的服务端内存会话。PBKDF2-SHA256 600000 轮，随机盐；随机会话令牌 + CSRF。Cookie 使用 Secure、HttpOnly、SameSite=Strict；POST 要求 JSON、同源 Origin、登录态与 CSRF（登录依靠同源与 JSON 限制）。按 IP 登录限速；会话 30 分钟无请求过期、最长 8 小时，最多 64 个。

资源只有固定 HTML/JS/CSS 路径；API 没有文件浏览、Shell 或任意 RPC 转发。日志用 textContent，禁止执行插入的 HTML。CSP 禁止第三方/内联脚本、嵌入与 frame，Nginx 限制 LAN 来源、大小和时间。HTTP 不提供传输加密。

状态展示 PID、进程存活、本地 build、磁盘、cgroup 内存和 UDP 监听。UDP 检查仅在容器网络命名空间中寻找端口，并不保证该端口属于正确游戏、更不等于 A2S 或客户端连接成功。未实现玩家数统计/完整游戏就绪探测，不伪造在线玩家或百分比。
