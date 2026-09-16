# 现场验收清单

状态约定：NOT RUN / PASS / FAIL。请复制本文件生成 `ACCEPTANCE.local.md`，按真实执行填写日期、PVE 版本、CTID、脱敏结果。不要把模拟测试状态套用到本表。

| 检查 | 初始状态 | 现场证据 |
|---|---|---|
| PVE 版本/架构、rootdir/vztmpl 存储、网桥正确 | NOT RUN | pveversion、pvesm、ip |
| dry-run 正确打印 6C/6144MiB/250G/nesting=0 | NOT RUN | 输出存档，不含密码 |
| 创建非特权 LXC，内存/CPU/磁盘正确 | NOT RUN | pct config / df / memory.max |
| Ubuntu 24.04 amd64 apt 环境安装成功 | NOT RUN | bootstrap 日志 |
| 两服务非 root、无 sudo 权限、代码不可写 | NOT RUN | systemctl show / stat |
| HTTP 8443 仅允许指定 LAN 打开面板 | NOT RUN | 时间/浏览器/地址 |
| 未列入白名单来源不能访问面板 | NOT RUN | 第二网段实际请求 |
| PVE 数据中心/节点/CT 防火墙是否实际启用 | NOT RUN | GUI 与规则检查 |
| 自动会话可读配置，跨站 POST 与无 CSRF 请求被拒绝 | NOT RUN | 浏览器或 curl 状态码 |
| Steam 账号授权/Guard/手机批准成功 | NOT RUN | 只记录结果，不录入秘密 |
| 真实 App 570 安装成功、buildid/StateFlags 正常 | NOT RUN | manifest 摘要 |
| Linux wrapper/二进制依赖齐全且无显示/GPU依赖错误 | NOT RUN | 脱敏诊断 |
| 启动后至少观察 10 分钟无崩溃/OOM | NOT RUN | 日志、memory.events |
| 两台设备连接、加载地图、选人、开始实际对局 | NOT RUN | 客户端版本与结果 |
| 两台设备完成一局测试并可开始下一局 | NOT RUN | 时间与结果 |
| 重启网页服务不会终止游戏/下载 | NOT RUN | 前后 PID/任务状态 |
| 正常停服不留下游戏进程或端口 | NOT RUN | 日志、ss、进程树 |
| 更新时禁止启动/重复更新 | NOT RUN | 409 / UI 提示 |
| 更新取消后阻止开服，重新成功校验解锁 | NOT RUN | 任务状态与维护标记 |
| 运行中维护需明确授权；失败不盲目开服 | NOT RUN | 任务记录 |
| 配置备份/停服恢复成功，快照不含 Steam 凭据 | NOT RUN | 文件范围，不公开内容 |
| 重启网页后端使旧会话失效并可自动建立新会话 | NOT RUN | 浏览器实际测试 |
| 游戏按需开机自启与崩溃有限重试 | NOT RUN | 一次受控重启/测试 |
| 安装中重启代理/LXC的任务标为 interrupted | NOT RUN | 在测试环境执行 |

6 GiB 内存可用性须以用户准备运行的真实模式、人数、机器人配置验证。不要只测空服务器就宣布“十人对战稳定”。完全断网、跨 VLAN、Workshop 地图应单列验收范围，未测不承诺支持。
