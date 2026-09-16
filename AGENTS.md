# 接手规则（先读）

用户要 PVE 的单实例 Dota 2 LAN 服务器完整交付，不是 Docker/VM 改造。固定：Ubuntu 24.04 amd64 **非特权 LXC、6 vCPU、6144 MiB、rootfs 250 G、nesting=0**。不要自行增配、引入 Docker、GPU、特权容器或公网暴露。

先读 `CODEX_HANDOFF.md`、`docs/TEST_REPORT.md`、`docs/ACCEPTANCE.md`，再进入相关源码。模拟协议/浏览器测试不能写成真实 Valve/PVE 联机验证。不要为了完成“成功”状态删维护保护文件或忽略 SteamCMD 的失败。

不得向用户索取或把 Steam 密码、Guard、管理员密码、私钥写入源码、env、命令行、日志、提交记录或接手文件。网页有一次性输入通道；真实授权由用户本人输入。Valve 自身缓存另按敏感目录管理。

没有 `shell=True`、任意命令/路径入口、sudo 代理或 Docker socket。新功能维持固定动作白名单、CSRF、Origin 校验、Unix socket 权限、JSON 原子写、任务互斥与停服更新。

宿主脚本只操作明确 CT，不调整全局防火墙/内核、不自动删除 CT。现场先 dry-run。升级运行代理前先正常结束任务/停服；只升级网页后端可保留游戏/下载。

开发验证：`bash scripts/test.sh`。测试依赖在 requirements-dev.txt。每次修改真实 Steam 交互或游戏启动参数时，增加对应模拟测试并明确仍需上游现场验证。交付结论注明哪些是代码测试、哪些是真实硬件与客户端测试。
