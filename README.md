# Dota 2 LAN Kit

在 PVE 的 Ubuntu 24.04 非特权 LXC 里，用原生 SteamCMD 运行 Dota 2 局域网服务器。通过中文 HTTP 免登录网页面板管理，游戏内由自制 Panorama 界面配置对局。当前用途是一名真人对战天地星 AI（Workshop 1627071163）。

## 组成

| 部分 | 位置 | 作用 |
|---|---|---|
| 运行代理 | `panel/agent.py`（`dota-agent`） | 管理 SteamCMD 任务、游戏进程、部署附加模式、解析游戏日志 |
| 网页面板 | `panel/web.py` + `panel/static/`（`dota-panel`） | 概览、SteamCMD、客户端下载、日志、配置、备份 |
| 附加模式 | `addon/lan_dota/` | 服务端 Lua（房间、收益规则、对局工具）和游戏内 UI 源码 |
| 发布工具 | `tools/` | 服务器上 Wine 编译 UI、生成 Windows 安装包、部署代码包 |
| 首次创建 | `pve/` `install/` | 创建 LXC 并安装运行环境 |

## 常用操作

- 首次创建 LXC：`docs/DEPLOYMENT.md`。
- 更新服务器代码：`python3 scripts/package.py` 打包，在服务器运行 `tools/deploy_kit.py`（`docs/RELEASE.md` 第 1 节）。
- 发布游戏资源（UI 或 Lua 有改动时）：在服务器运行 `tools/release.py --version rNN --restart`（第 2 节）。
- 玩家安装客户端资源：面板"Windows 客户端资源"页（第 3 节）。

面板页脚显示当前部署的提交号；概览页的"游戏资源版本"卡片对比源码、服务器已部署版本和客户端安装包三者是否一致。

## 开发

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
PATH=.venv/bin:$PATH bash scripts/test.sh
```

Lua 测试需要本机有 liblua5.4，JS 语法检查需要 node。这些都是模拟环境测试，不能代替真实 Dota 2 联机验收。

## 文档

| 文档 | 内容 |
|---|---|
| `docs/HELP.md` | 面板与游戏内工具使用帮助（生成 `/help` 页面：`python3 tools/build_help.py`） |
| `docs/RELEASE.md` | 部署代码、编译发布、客户端安装包 |
| `docs/OPERATIONS.md` | 现场操作与验证记录 |
| `docs/DEPLOYMENT.md` | 首次创建 LXC 与运维手册 |
| `docs/ARCHITECTURE.md` `docs/API.md` `docs/SECURITY.md` `docs/MONITORING.md` | 架构、接口、安全边界、资源监控 |
| `docs/LAN_ADDON.md` `docs/TIANDIXING_VALIDATION.md` `docs/ACCEPTANCE.md` | 附加模式、天地星验证、现场验收清单 |
| `docs/archive/` | 历史版本说明、交接文件和测试报告（含旧 README） |
