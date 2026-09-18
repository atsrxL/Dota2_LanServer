# 接手规则（先读）

用户要 PVE 的单实例 Dota 2 LAN 服务器完整交付，不是 Docker/VM 改造。固定：Ubuntu 24.04 amd64 **非特权 LXC、6 vCPU、6144 MiB、rootfs 250 G、nesting=0**。不要自行增配、引入 Docker、GPU、特权容器或公网暴露。

先读 `CODEX_HANDOFF.md`、`docs/TEST_REPORT.md`、`docs/ACCEPTANCE.md`，再进入相关源码。模拟协议/浏览器测试不能写成真实 Valve/PVE 联机验证。不要为了完成“成功”状态删维护保护文件或忽略 SteamCMD 的失败。

不得向用户索取或把 Steam 密码、Guard、管理员密码、私钥写入源码、env、命令行、日志、提交记录或接手文件。网页有一次性输入通道；真实授权由用户本人输入。Valve 自身缓存另按敏感目录管理。

没有 `shell=True`、任意命令/路径入口、sudo 代理或 Docker socket。新功能维持固定动作白名单、CSRF、Origin 校验、Unix socket 权限、JSON 原子写、任务互斥与停服更新。

宿主脚本只操作明确 CT，不调整全局防火墙/内核、不自动删除 CT。现场先 dry-run。升级运行代理前先正常结束任务/停服；只升级网页后端可保留游戏/下载。

开发验证：`bash scripts/test.sh`。测试依赖在 requirements-dev.txt。每次修改真实 Steam 交互或游戏启动参数时，增加对应模拟测试并明确仍需上游现场验证。交付结论注明哪些是代码测试、哪些是真实硬件与客户端测试。

用户最新硬约束：面板仅 HTTP，免登录，不保留管理员密码/认证或 HTTPS 要求。Steam/Guard 授权必须保留；LAN 白名单与防跨站校验不是登录功能，不可随意删掉。


1.2.0 Workshop：先读 docs/CODEX_WORKSHOP_HANDOFF.md 与 WORKSHOP_TEST_REPORT.md。只在受管目录下载/解包机器人，先验证固定 App570 与 Bot 标签，拒绝任意路径/URL/可执行安装器。下一局选择、部署副本、运行快照必须分开；绝不在线覆盖 bots。游戏维护动作仍停服，Bot 下载不需要停服。哈希不符保留外部修改，部署恢复 journal 不能随手删除。入口日志不等于完整 AI 验收；原生房间同步未实现，不得伪造 Lobby 状态或真实 Workshop 下载。


1.3.0 优先读根目录 CODEX_LAN_HANDOFF.md。新路线是 connect 后自制 Panorama 准备阶段，不是官方GC大厅同步。UI必须真实Workshop Tools编译；不得把tests合成资源放入compiled。先无AI联机，再天地星原生Bot探针；不模拟API骗过验证，不静默开启作弊/切默认AI。保留引擎来源身份校验，不信任payload.PlayerID。意向位置未映射天地星原生槽位，不能谎称已实现。所有真实验收默认NOT_RUN。
