# 运维记录

按时间倒序记录现场操作和验证结果。过程说明见 `RELEASE.md`，更早的记录见 `archive/`。

## 当前服务器

- CT270 `dota2-lan`，Ubuntu 24.04 非特权 LXC，地址 `192.168.123.66`。面板用 80 端口，游戏端口以面板显示为准（目前 27000）。
- 代码目录 `/opt/dota2-lan-kit`（不是 git 检出，以 `BUILD.json` / `DEPLOYED.json` 记录版本）；状态目录 `/var/lib/dota2`。
- 面板和代理服务：`dota-panel`、`dota-agent`。重启 `dota-agent` 会结束正在运行的游戏。

## 2026-09-30 · 代码 e2b1011 + r29

- 快捷技能菜单展开时对局窗口加宽到 420px，字号恢复为 14；收起菜单或折叠窗口时恢复原宽度。
- 部署并发布 r29：部署源码与代码目录一致，都是 `1c78c5081991`；没有错误，客户端包 r29 与服务器一致。
- 尚未实测：游戏内加宽后的位置是否挡住顶部英雄头像栏。

## 2026-09-30 · 代码 ee4a1b8 + r28

- 快捷技能二级菜单改为每行 3 个；已拥有的技能显示 ✓ 并高亮，再点一次发送移除。
- `deploy_kit.py` 部署后运行 `release.py --version r28 --restart`：部署源码与代码目录一致，都是 `707bcee0f70f`；没有错误，客户端包 r28 与服务器一致。
- 尚未实测：游戏内每行 3 个的排版，以及点击移除。

## 2026-09-28 · 下载参考地图 Workshop 2781880190

- 用 steam 用户和缓存登录手动跑 SteamCMD `workshop_download_item 570 2781880190 validate`，`force_install_dir` 设为独立目录 `/var/lib/dota2/workshop-ref`，没有动 `/srv/dota2` 和面板任务；当时没有正在执行的任务，游戏服照常运行。
- 结果：`Success. Downloaded item 2781880190`，56621288 字节；日志在 `/var/lib/dota2/workshop-ref/steamcmd-2781880190.log`。
- 已复制到开发机 `reference/workshop-2781880190/` 并解包，只作功能参考，不部署。

## 2026-09-28 · 代码 ed14ac3 + r27

- 快捷技能改为 36 个先天技能的二级菜单。内部名称来自官方 datafeed，并与服务器 Dota 自带的 `abilities_schinese.txt` 逐一核对，名称全部一致。
- 用 `deploy_kit.py` 部署后运行 `release.py --version r27 --restart`：部署源码与代码目录一致，都是 `47a75765b120`；心跳正常，没有错误，客户端包 r27 与服务器一致。
- 尚未实测：游戏内二级菜单，以及这 36 个技能添加到英雄后的实际效果（部分先天技能依赖原英雄的机制）。

## 2026-09-28 · 代码 7b6d0ad + r26

- 第一次用 `tools/deploy_kit.py` 部署代码包：校验通过，当时没有玩家在线；备份在 `/var/lib/dota2/kit-backups/kit-20260928-093106-7b6d0add067b.tgz`，`DEPLOYED.json` 已写入，面板页脚显示该提交。脚本正确提示 UI 源码已变化，需要重新发布。
- `tools/release.py --version r26 --restart`：四个 UI 输入都编译成功，产物保存在 `/var/lib/dota2/artifacts/r26/`，`compiled-backup-*` 剩 2 份。
- 重启后部署源码与代码目录一致，都是 `4c0b9a339643`；心跳正常，没有错误。编译后的 `lan_setup.vjs_c` 里已写入该源码哈希，占位符 `__LAN_SOURCE_SHA256__` 已被替换。
- 线上下载 EXE 为 150520 字节，与清单 SHA-256 `96a1734e99e32b43…` 一致。
- 尚未实测：游戏内的 restart 按钮、删除技能、版本不一致提示，以及 r26 在 Windows 上的安装。

## 2026-09-28 · r25

- 用 `tools/release.py` 发布 r25。之前手工放入编译工具目录的两个副本没有 stage 标记，`game/dota_addons` 也属于 root，所以先把副本移到 `/root/agent.backup/dota-tools-stage-pre-r25-20260928/`，并把该目录交给 steam（一次性处理）。
- 四个 UI 输入都编译成功（0 failed）。重启后，部署源码与代码目录一致，都是 `e83149686d61`；引擎心跳正常，没有错误，`-basetime` 已启用。
- 线上下载 EXE 为 148320 字节，与清单 SHA-256 `f4d80108da6316a2…` 一致。
- 代码更新前的备份：`/root/agent.backup/dota-kit-pre-fa0b6f4-20260928/`。
- 尚未实测：r25 在 Windows 上的安装，以及游戏内验收。

## 2026-09-20 · r23 / r24

- 在 CT270 上用 Wine 9.0 + Xvfb 运行官方编译器，r24 的四个 UI 输入全部编译成功（shader 警告不影响 Panorama）。depot：工具 381450 manifest 3664814097704453884，Windows 引擎 373303 manifest 9112253242025854370，均复用 Steam 登录缓存下载。
- 客户端安装包先按当时服务器源码发布为 r23；r24 编译产物单独保存在 `/var/lib/dota2/artifacts/r24/`，之后才切换。浏览器验证了下载哈希和页面。
- 面板在登录验证成功后记住账号名；空密码请求复用 Steam 缓存，配置里不保存密码。
- 面板精简：移除概览里重复的任务、附加模式和入门卡片以及常驻说明文字；Steam 账号只在 SteamCMD 页编辑。
