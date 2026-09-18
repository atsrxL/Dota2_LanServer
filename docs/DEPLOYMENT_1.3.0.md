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

## Workshop Tools 后续现场验证

用户安装 Tools 后，真实 resourcecompiler.exe 已成功编译四个 Panorama 文件，Windows 客户端与 CT 均已部署。修复根 Panel 禁止 id 的真实编译错误，保留内部 LANRoot 供 JS 使用；测试 fixture 排除本地 compiled 产物，避免已编译开发环境污染缺资源测试。

Linux 当前不支持 dota_launch_custom_game；-addon 参数也未挂载 addon。按引擎 map 帮助实测，实际 argv 应为 +dota_force_gamemode 15 +map dota customgamemode lan_dota；等号形式被解析成单个 KV key 而失败。现已记录 Mounting addon 与 addon=lan_dota，但无 Lua BOOT/STATE，不能认定准备阶段通过。

用户正在真实客户端尝试连接；客户端初次报告出错，服务器未见握手。已要求开启 con_logfile lanlab-client.log 后重试，以读取具体错误。

## Panorama 准备阶段修复与规则工作进展

2026-09-18 后续实测：map 必须显式包含 gamemode 15 customgamemode lan_dota，才载入 addon_game_mode.lua。已收到真实 BOOT/STATE。INIT 卡住时仅在玩家连接后调用 ResetToCustomGameSetup 一次；用户已看到面板，服务器确认 phase=setup、hello=1、host=0，无错误。

修复 LANBody 缺少 flow-children:down 导致的区域重叠，缩窄下拉框及行内说明宽度。真实资源已重新编译至 r4，但更新后的游戏内视觉与交互仍待用户复核。

新增金币倍率 25%–1000%，默认 100%，服务端范围校验与 SetModifyGoldFilter，正向金币事件乘倍率、负值和零保持。39 项 addon 测试通过，含 INIT 单次恢复与金币正负值验证；尚未实测收益账目。

中立装备解锁时间：当前 build 25329722 的 scripts/npc/neutral_items.txt 使用 neutral_tiers/start_time，依次 0:00/15:00/25:00/35:00/60:00。尚未实现自定义时间的可靠运行时加载，不开放无效控件。

普通服天地星 1573671599 已从 Windows Workshop 导入，固定版本 ea5bacf5e672376dc1514f0758e7def17c48b28b8bf4a35a83c1308795f7f438，实测 1 人 + 9 Bot，用户观察暂未发现逻辑异常。addon 原生 Bot 路线仍未验收，不能把普通服结果套用。

## r5 下拉菜单样式修复

用户复核 r4 后仍报告选单重叠。lan_setup.xml 原先仅载入自定义样式，未载入原生控件基础样式；新增引用游戏 VPK 中真实存在的 s2r://panorama/styles/dotastyles.vcss。file:// 源码引用因 Tools 缺少对应原始 CSS 而编译失败，改用已编译资源引用后真实 resourcecompiler 通过。补充 DropDown 非选中 Label 隐藏、选中项显示、DropDownMenu 纵向排列及滚动，复选框子项横排。

已通过 QGA 同步 .98、真实编译、资源清单校验，部署 CT270 并重启游戏进程，收到新 session BOOT，无 runtime errors。r5 游戏内展开/收起视觉及交互待用户复核，不能以编译成功替代验收。客户端包 lanlab-client-r5.zip SHA256 46f02b9d8d66e69d9b0fb04bb27b2323934fd3d96cdfc4d1f697a2ea6c1bac2e。

r5 完整源码回归：204 passed / 28 warnings（70.30s），既有 forkpty 与重复 ZIP fixture 警告仍在。未把 mock 测试计为游戏内视觉验证。
