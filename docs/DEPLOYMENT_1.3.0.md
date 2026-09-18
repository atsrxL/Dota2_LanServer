# 1.3.0 合并与现场部署记录

日期：2026-09-18。真实仓库基线 88871cb；候选 bundle 04ee114。使用三方合并保留真实仓库已有二进制启动修复及回归测试，未覆盖用户工作区。原交付的 LAN/Workshop 测试报告保持历史性质。

## 已完成

- 已有 Ubuntu 24.04 非特权 CT 270 从停止状态启动并升级到 1.3.0；6 vCPU、6144 MiB、250 G、nesting=0 未变。
- 沿用原 HTTP 8443、UDP 27015 和 LAN ACL；原 App 570 数据与 Steam 缓存保留。buildid 25329722，StateFlags=4。
- dry-run 核对通过；最终 provision-existing --apply 成功，nginx 配置与三个服务健康检查通过。
- 普通模式真实启动、加载 dota 地图、进入 ss_active、UDP 监听；正常停止后再次启动。观察中无退出、OOM kill=0。不是客户端联机通过。
- 附加模式源码已受管部署，编译资源缺失时 ready=false，未强制启用或伪造资源。
- 生产 Chrome 直接 HTTP 页面检查通过：版本、实时 CPU/每核/6 GiB 内存、附加模式资源提示可见。缺 CSRF 与跨 Origin POST 均返回 403。
- Windows VM 已通过 Znas QGA guest-ping 和命令完成验证；对应 Tiny11_clone、Windows 11、Dota buildid 同为 25329722。源码已置于 C:/lanlab-130/source，游戏安装 D:/steam/steamapps/common/dota 2 beta。

## 合并及调试修复

- 保留 linuxsteamrt64/dota2 优先启动，避免退回需要嵌套 namespace 的 wrapper。
- systemd 删除旧 --http --no-auth 参数，与新版本无登录 HTTP 入口一致。第一次升级因此失败，修复后完整部署重新执行成功。
- 资源导入工具规范化自身临时目录，兼容 macOS /var 到 /private/var 的系统别名；外部目录链接拒绝仍保留。
- cgroup memory.max 不提供有限值时，仅在验证 LXCFS meminfo 挂载后使用实际 MemTotal；保留容量来源，不硬编码 6 GiB。
- 游戏日志写盘前屏蔽引擎生成的 tv_secret_code/server_key，包含跨块测试。新启动日志已验证脱敏。旧日志不会被此代码自动重写，导出前须审阅。
- 宿主 CT 防火墙备份移至 /root/agent.backup，固定 agent-owned 名称只保留该 CT 最新两份。

## 测试证据与限制

首次 macOS 测试 196 passed / 6 failed：5 项缺少 Lua5.4，一项临时路径别名问题。安装开发用 lua@5.4 并修复后，完整 202 passed；增加 LXCFS 回归后完整 203 passed / 28 warnings。最后日志脱敏新增测试及相关模块定向运行 54 passed。

命令：DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/lua@5.4/lib PATH="$PWD/.venv/bin:$PATH" bash scripts/test.sh。定向命令：.venv/bin/python -m pytest -q tests/test_common.py tests/test_resources.py。Lua suite 为 mock 引擎，并非 Dota VM。

保留 27 条多线程 forkpty 警告和 1 条刻意重复 ZIP 名测试警告；没有宣称已解决潜在并发风险。原交付曾有模拟子进程间歇错误，本轮未复现。

## 仍待完成

Windows 当前没有完整 Workshop Tools：无 content 目录、无独立 resourcecompiler.exe，只有资源 DLL；工具模式尝试退出并生成错误转储。已请用户通过 Steam DLC 安装 Dota 2 Workshop Tools。尚未生成四个真实 Panorama 编译文件，因此客户端包、Gate A 两端准备阶段、Gate B 天地星原生 Bot、Gate C 完整对局/卡顿比较均 NOT RUN。

不得把普通服启动、网页通过或源码复制当作这些验收通过。工具装好后按 CODEX_LAN_HANDOFF.md 编译、collect/import、双端部署，再继续 Gate A。

## 回退证据

CT 升级前代码、配置与状态备份位于 /root/agent.backup/dota130-preupgrade-20260918/state-code-config.tar.gz，0600，tar 读回验证通过。包含敏感 Steam 缓存，不可公开。游戏数据未整包备份且未进行游戏版本更新。宿主防火墙另有专用备份。回退须先正常停服和代理，恢复备份的代码/配置并 daemon-reload；不要删除整个 CT。
