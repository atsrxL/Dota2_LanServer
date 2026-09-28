# 技术依据与核验边界

检索日期：2026-09-16。引用只用于技术路线选择；不代替真实 Steam 登录、下载、运行和联机测试。Valve Developer Community 页面属于开发者 wiki，并不构成某一当日版本的官方服务 SLA。

## [S1] SteamCMD AppID / 匿名授权

Valve Developer Community — Dedicated Servers List
https://developer.valvesoftware.com/wiki/Dedicated_Servers_List

Dota 2 条目列出 AppID 570，匿名登录列为 No。用于纠正前序答复中匿名下载的过度确定性。本版从账号授权设计，仍须根据实际 Steam 返回确认许可。

## [S2] SteamCMD 安装及更新

Valve Developer Community — SteamCMD
https://developer.valvesoftware.com/wiki/SteamCMD

以 force_install_dir、login、app_update/validate 为安装与校验路线。validate 可能覆盖上游管理的文件。安装器种子来自 Valve 的 CDN：
https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz

本包不含安装器、游戏文件或 Valve 库。CDN URL 内容可变；可选预期 SHA-256 校验，不提供未经验证的固定哈希。

## [S3] Proxmox 容器参数与存储

Proxmox — pct(1)
https://pve.proxmox.com/pve-docs/pct.1.html

Proxmox — Proxmox Container Toolkit
https://pve.proxmox.com/pve-docs/chapter-pct.html

Proxmox 官方论坛工作人员关于 rootfs 存储容量语法的说明（2026-01）
https://forum.proxmox.com/threads/creation-of-lxc-via-api-ceph-without-precreating-vm-storage.178834/

使用存储分配语法 `<storagename>:<size>`，而非拼造已有 volume 名称；unprivileged、cores、memory、net0、rootfs、features、startup/onboot 等使用 pct 接口。仍需现场核对本机 PVE 版本与模板。

## [S4] Nginx 入口参考（当前部署不启用 HTTPS）

Nginx — Configuring HTTPS servers
https://nginx.org/en/docs/http/configuring_https_servers.html

该资料仅作为 Nginx 配置参考。当前版本按用户要求使用受信任 LAN HTTP，不生成证书，也不应公开到互联网。

## [S5] 网页会话与 CSRF 的设计依据

Pallets — Security Considerations / Flask documentation
https://flask.palletsprojects.com/en/stable/web-security/

参考的是 Cookie/CSRF/安全响应头的一般原则。**实现不是 Flask**，不声明使用或继承 Flask 的自动安全机制；本项目 WSGI WebApp 自行实现并测试其校验逻辑。

Waitress — Using Behind a Reverse Proxy
https://docs.pylonsproject.org/projects/waitress/en/stable/reverse-proxy.html

生产使用 Waitress 回环监听，Nginx 覆盖 Host/X-Real-IP/代理头；开发演示才使用本机 wsgiref。Python 自带 http.server 不作为公开生产服务。

## [S6] Linux Dota 2 管理入口交叉参考

CubeCoders AMPTemplates（项目维护方发布的模板源码）
https://raw.githubusercontent.com/CubeCoders/AMPTemplates/main/dota2.kvp
https://raw.githubusercontent.com/CubeCoders/AMPTemplates/main/dota2config.json

该模板提供 Linux 路径 `570/game/bin/linuxsteamrt64/dota2`、LAN、地图与服务器参数的工程参考。不是 Valve 对当前服务器兼容性的官方保证。本项目独立实现，未打包该模板源码或 AMP。

ValveSoftware/Dota-2 原始问题记录（用于确认官方 Linux wrapper 路径而非服务器成功证明）
https://github.com/ValveSoftware/Dota-2/issues/2404

## [S7] Steam Guard

Valve — Steamworks Documentation: Uploading to Steam / login troubleshooting
https://partner.steamgames.com/doc/sdk/uploading

说明 Steam Guard 可以影响 SteamCMD 登录、需按账号授权提示处理。与本项目下载服务器的用途不同；这里只用于交互授权机制的依据，不用于推断用户账号已有 App 570 权限。

## 明确未验证的项目

未连接用户 PVE；未运行真实 Ubuntu apt 安装；未以真实 Steam 账号登录；未下载真实当日 App 570；未实测 Linux Dota 二进制的依赖；未连接真实 Dota 2 客户端。所有现场步骤、接受标准及不确定性已保留在 ACCEPTANCE.md 与 CODEX_HANDOFF.md 中。
