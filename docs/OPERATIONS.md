# 运维记录

按时间倒序记录现场操作和验证结果。过程说明见 `RELEASE.md`，更早的记录见 `archive/`。

## 当前服务器

- CT270 `dota2-lan`，Ubuntu 24.04 非特权 LXC，地址 `192.168.123.66`。面板用 80 端口，游戏端口以面板显示为准（目前 27000）。
- 代码目录 `/opt/dota2-lan-kit`（不是 git 检出，以 `BUILD.json` / `DEPLOYED.json` 记录版本）；状态目录 `/var/lib/dota2`。
- 面板和代理服务：`dota-panel`、`dota-agent`。重启 `dota-agent` 会结束正在运行的游戏。

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
