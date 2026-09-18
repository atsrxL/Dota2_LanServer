# 现场验收清单

状态约定：NOT RUN / PASS / FAIL。请复制本文件生成 `ACCEPTANCE.local.md`，按真实执行填写日期、PVE 版本、CTID、脱敏结果。不要把模拟测试状态套用到本表。

| 检查 | 初始状态 | 现场证据 |
|---|---|---|
| PVE 版本/架构、rootdir/vztmpl 存储、网桥正确 | NOT RUN | pveversion、pvesm、ip |
| dry-run 正确打印 6C/6144MiB/250G/nesting=0 | NOT RUN | 输出存档，不含密码 |
| 创建非特权 LXC，内存/CPU/磁盘正确 | NOT RUN | pct config / df / memory.max |
| Ubuntu 24.04 amd64 apt 环境安装成功 | NOT RUN | bootstrap 日志 |
| 两服务非 root、无 sudo 权限、代码不可写 | NOT RUN | systemctl show / stat |
| HTTP 直接进入、无登录框/证书/HTTPS 跳转 | NOT RUN | 时间/浏览器/地址 |
| 未列入白名单来源不能访问面板 | NOT RUN | 第二网段实际请求 |
| PVE 数据中心/节点/CT 防火墙是否实际启用 | NOT RUN | GUI 与规则检查 |
| 无面板凭据可读配置/日志/诊断，白名单外拒绝 | NOT RUN | 浏览器或 curl 状态码 |
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
| 后端重启后自动获取新 CSRF，无需登录 | NOT RUN | 实际 HTTP 操作测试 |
| 游戏按需开机自启与崩溃有限重试 | NOT RUN | 一次受控重启/测试 |
| 安装中重启代理/LXC的任务标为 interrupted | NOT RUN | 在测试环境执行 |

6 GiB 内存可用性须以用户准备运行的真实模式、人数、机器人配置验证。不要只测空服务器就宣布“十人对战稳定”。完全断网、跨 VLAN、Workshop 地图应单列验收范围，未测不承诺支持。

## HTTP / 实时监控新增验收（全部待现场执行）

| 项目 | 状态 | 证据要求 |
|---|---|---|
| 明确 http 地址直接打开，无面板密码/SSL 跳转 | NOT RUN | 实际浏览器与 nginx -t / ss |
| LAN 白名单外拒绝，同源 POST 成功、跨站 POST 拒绝 | NOT RUN | 脱敏响应状态 |
| cgroup 挂载根确属该 CT，非宿主或单个 agent 子组 | NOT RUN | PVE/CT 配置和只读文件对照 |
| 实际 6 核/6 GiB 正确读取；每核来源说明准确 | NOT RUN | API 与同窗口 PVE 指标对照 |
| 单核/多核负载、内存占用/缓存回收可观察 | NOT RUN | 明确授权的短时受控测试 |
| 多浏览器、隐藏/恢复、代理重启、断网恢复 | NOT RUN | 浏览器实际操作，不用模拟测试代替 |


## 1.2.0 Workshop 现场验收（全部待执行）

- [ ] 真实 SteamCMD 下载 1627071163，元数据/实际路径/包格式/内容 SHA 有记录，未泄露授权信息。
- [ ] 当前 Linux Dedicated 接受加载参数，目标 Lua 真正执行，不是默认 Bot 回退。
- [ ] 两台真实客户端连接、选边、填充 Bot；阵营、选人、难度和位置行为核对。
- [ ] 完成一场普通 All Pick，结束后重开；脚本更新/版本回滚/停用均通过。
- [ ] 同版本脚本和模式对比 Local Host，观察实际帧时间与 CPU/内存，核对原卡顿是否改善。
- [ ] 非特权 LXC / HTTP 无面板登录 / 实时资源监控无回退。
- [ ] 生产 Nginx HTTP 路由、LAN/跨站防护、Steam Guard 等待流程实际通过。

未勾选项不因模拟测试自动变成 PASS。原生房间同步未实现，不属于本版可声称完成的验收项。
