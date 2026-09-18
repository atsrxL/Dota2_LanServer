# 本轮审查范围与改动记录

## 不能混淆的状态

目标：atsrxL/Dota2_LanServer。尝试 GitHub 页面、raw/API 与 git ls-remote 未取得目标仓库内容；GitHub 写入连接未授权。没有仓库 HEAD、提交列表或可核对的 diff，因此**没有完成用户已提交修改的审查，没有远端 commit/push**。

当前代码仅基于本对话原交付 dota2-lan-kit-1.0.0.zip。为不覆盖用户新改动，交付独立本地 Git 历史、两个变更提交、format-patch 与完整源代码快照。不能将快照直接覆盖真实仓库。原始 ZIP 仅作为对照基线，本地基线提交不是 GitHub 原有祖先。

## 原交付代码中已确认并修改的点

| 项目 | 原交付情况 | 本轮本地处理 |
|---|---|---|
| HTTP / 无面板密码 | WebApp 使用 Auth、Cookie 会话；Nginx 依赖 TLS，bootstrap 生成管理员密码与证书 | 删除认证与 TLS 初始化，HTTP 默认 8080，无登录/退出/重置密码；自定义端口保留 |
| 剩余旧入口 | CLI、帮助、计划、PVE 输出继续要求 HTTPS/密码 | 同步更新生效说明与脚本；历史测试记录显式标成历史，不用其证明新功能 |
| HTTP 剪贴板 | 只依赖 navigator.clipboard | 失败时选中连接命令并提示 Ctrl+C / Cmd+C，不强迫使用 HTTPS |
| CPU 监控 | 原 metrics 只有 load average，不是总 CPU 或每核百分比 | 新增只读 ResourceMonitor、/api/metrics 和概览组件 |
| 资源显示缺失值 | 顶部 memory_current 缺失时存在被算为 0 的风险 | 必须有数值才显示正常比例；监控缺失/失效显示 — |
| 容器统计误读风险 | CPU 未实现，不能据此断言每核属于容器任务 | cgroup 根总量、可见每核分开，标注 source/scope，LXCFS/宿主视图警告 |
| 采样异常 | 未实现 CPU 基线/复位 | 缓存共享、guest 不重复计数、重置/热插拔/配额变化重新建基线 |

这不是对 GitHub 当前版本的缺陷清单。用户可能已经完成其中部分改动，Codex 必须先对照真实代码再选取或调整补丁。

## 保持不变

6 vCPU / 6 GiB / 250 G 非特权原生 LXC；不加 Docker/GPU/nesting。Steam 账号/Guard/手机批准属于 Valve 授权，不能与面板登录一并删除。保留 LAN 白名单、Host/Origin/CSRF、固定动作、任务互斥、更新前停服授权、维护锁、日志脱敏、非 root 运行与 Unix socket 权限。

## 尚未完成

真实仓库差异审查/冲突合并/远端推送，PVE 现场部署，目标 LXC 的 cgroup/LXCFS 统计范围核验，真实 Steam 下载与两客户端对局。pexpect 多线程 forkpty 警告仍存在，未通过本次 UI/监控改动解决。
