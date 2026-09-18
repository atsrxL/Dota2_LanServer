# CPU / 内存实时监控

本轮基于原始 1.0.0 源码制作；没有取得 GitHub 当前提交。合并后仍须在真实 PVE/LXC 上核验监控范围。固定部署目标保持 6 vCPU、6144 MiB、250 G；监控不硬编码这些数值伪装实测。

## 显示内容

概览页增加 CPU 总使用率、有效配额、等效忙碌核心数、每个可见核心占用、内存总占用/实际上限/占用率、工作集估算、文件缓存、Swap 与累计 OOM/OOM kill。两张趋势图保留当前页面最近两分钟的样本，刷新页面清空，不写磁盘。

浏览器每次请求完成后约 2 秒再次采样；每个请求 5 秒超时，不叠加请求。页面隐藏时暂停，返回自动恢复。连接失败立即清空实时数值并保留带断点的历史；同一采样超过 6 秒不更新则显示过期，不伪装为实时。后台多个访问者共享至少 1 秒间隔的采样缓存，不会为每个浏览器独立 sleep 或启动 top。

## CPU 计算与局限

总 CPU 优先读取当前 cgroup 命名空间挂载根 `/sys/fs/cgroup/cpu.stat` 的 `usage_usec`，不是 `/system.slice/dota-agent.service` 子组；在目标 LXC 中这样才能包含游戏、SteamCMD、网页及其他容器服务。现场必须确认这个挂载根确实是本 CT，而不是宿主或不适合的子组。

计算：两次 CPU 时间差 ÷ monotonic 墙钟时间差 = 等效忙碌核心数。再除以有效配额并乘 100 得到总 CPU 百分比；6 核配额时，单核持续满载约为 16.7%，六核占满才是 100%。容量读取 cpu.max/cpuset/可见核心或 affinity，支持小数配额；对外百分比限制 0–100，等效忙碌核数保留原计算值。

每核心读取 `/proc/stat` 的前八项时间差，idle 与 iowait 视为非忙碌时间。guest/guest_nice 已包含在 user/nice 中，不重复相加。首轮、计数回退、核心热插拔或配额改变时重新建立基线，缺失数据返回 null，不显示成 0%。

**cgroup v2 没有直接提供逐核心的本容器任务占用接口。**LXCFS `/proc/stat` 是虚拟可见视图，不承诺精确的物理逐核归属。未检测到 LXCFS 时明确告警，普通 proc 读数按允许的 CPU affinity/cpuset 过滤，但仍可能包含宿主任务；仅过滤 CPU 编号不等于隔离任务用量。源数据来自哪里、总量和每核的 scope 都直接在界面标注。

LXCFS 可将物理 CPU 12–17 重编号为可见 0–5，因此不能把虚拟编号简单与物理 affinity 求交。代码检测挂载并区分这两种视图。不静默截取前六核、不平均分摊总占用伪造逐核数值。

## 内存计算

优先读取挂载根的 `memory.current` / `memory.max`。主要占用率用计费总量，包括缓存；工作集单列为 `max(0, memory.current - inactive_file)`，不是进程 RSS 总和。文件缓存取 memory.stat 的 file。Swap 单列，不掺入 RAM 6 GiB。OOM 数字是该 cgroup 的累计事件，不表示此刻仍在 OOM。

计数不可读时显式降级到 `/proc/meminfo`：可见占用为 MemTotal − MemAvailable，并标明 scope，可能是宿主视图。上限缺失或为 max 时不给虚假的 6 GiB 或百分比。没有用前端预置六核/6 GiB 冒充监控。

## API 和本地命令

`GET /api/metrics` 无面板登录要求，受现有 LAN/Host 限制；只读，不需 CSRF。返回 schema、sequence、sampled_at、interval_seconds、cpu、memory、warnings。缺失数值使用 JSON null。`/api/status` 保留原 metrics.memory_current/memory_max/disk 等兼容字段，并追加 metrics.resources。

```bash
# 在 LXC 内；本地代理须已启动
dota-cli metrics
curl --fail http://127.0.0.1:8765/api/metrics
```

## 现场对照（必须由 Codex 在真实设备完成）

在 PVE 上确认实际 CT 的 cores=6、memory=6144、rootfs 容量=250G；在 LXC 检查 `cat /sys/fs/cgroup/cpu.max`、`cat /sys/fs/cgroup/cpuset.cpus.effective`、`cat /sys/fs/cgroup/memory.max` 与 `/proc/self/mountinfo`。6 GiB 上限为 6442450944 字节；不要用本地开发截图中的 4 GiB/5 个可见 CPU 当作用户 CT 的证据。

确认 agent 的 systemd 隔离设置下仍能只读该挂载根；不得为获取数据改特权 CT、放开宿主 cgroup 写权限或 chmod 777。做短时间、明确授权的 CPU/内存负载对照，比较趋势而不是要求不同采样窗口的每个瞬时值完全相同。核查多浏览器、页面隐藏/恢复、后端重启以及首次采样行为。未执行项保持 NOT RUN。

## 依据

Linux kernel cgroup v2：
https://docs.kernel.org/admin-guide/cgroup-v2.html

LXCFS 上游说明及 proc 文件虚拟化：
https://github.com/lxc/lxcfs

LXCFS 上游版本记录（含 cgroup v2 的 /proc/stat 核心数修复）：
https://linuxcontainers.org/lxcfs/news/
