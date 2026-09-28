# 发布与更新

日常改动分两类，各有一条命令。首次创建 LXC 见 `DEPLOYMENT.md`。

| 改了什么 | 做什么 |
|---|---|
| 面板、代理、工具、文档（`panel/` `tools/` `docs/` `scripts/`） | 部署代码包（第 1 节） |
| 游戏内 UI 或服务端 Lua（`addon/lan_dota/`） | 部署代码包，再运行发布流程（第 2 节） |

## 1. 部署代码包

在开发机的 git 检出里打包。打包会写入 `BUILD.json`，记录提交号和是否含未提交改动：

```bash
python3 scripts/package.py --output /tmp/d2pkg
```

把 `dota2-lan-kit-<版本>.zip` 复制到服务器，以 root 执行：

```bash
unzip -p dota2-lan-kit-1.3.0.zip dota2-lan-kit/tools/deploy_kit.py > /tmp/deploy_kit.py
python3 /tmp/deploy_kit.py --archive dota2-lan-kit-1.3.0.zip
```

`tools/deploy_kit.py` 的步骤：

1. 按包内 `SHA256SUMS` 校验每个文件；多出或被改动的文件直接拒绝。
2. 有玩家在线时拒绝部署，因为重启运行代理会结束对局。确需部署时加 `--force`。
3. 备份受管路径到 `/var/lib/dota2/kit-backups/kit-<时间>-<提交>.tgz`，只保留最新 3 份（`--keep`）。
4. 整体替换 `panel` `tools` `docs` `scripts` `addon/lan_dota/game` `addon/lan_dota/content`，旧版本残留文件随之消失；中途失败会还原已替换的目录。
5. 写入 `DEPLOYED.json`，重启 `dota-agent` 和 `dota-panel`。
6. 编译 UI 仍匹配源码时，自动重新启动原本在运行的游戏；不匹配时提示运行发布流程。

不会改动：`config/`、`client-downloads/`、`addon/lan_dota/compiled/`、`/var/lib/dota2` 下的状态。

面板页脚显示 `v1.3.0 · <提交号> · 部署于 <时间>`；没有 `BUILD.json` 时显示"未记录提交"。

## 2. 发布游戏资源（服务器上编译）

以 root 执行，放入源码和编译两步会通过 `runuser` 切到 steam 用户：

```bash
python3 /opt/dota2-lan-kit/tools/release.py --version r26 --restart
```

步骤依次为：

1. 把 UI 源码放入编译工具目录（stage）。同时把 `lan_setup.js` 里的 `__LAN_SOURCE_SHA256__` 替换成服务器源码哈希，客户端据此判断自己是否过期。
2. 用 Wine 运行官方 `resourcecompiler.exe`，每个输入都必须输出 `OK: N compiled, 0 failed`。
3. 收集并校验编译产物，导入 `addon/lan_dota/compiled`。
4. 生成 Windows 安装包，先复制再改名发布，清单最后替换。
5. 在 `/var/lib/dota2/artifacts/<版本>/` 保存编译 ZIP、安装包和 `release.json`，只保留最新 3 个带 `release.json` 的版本，手工目录不动。旧的 `compiled-backup-*` 也只保留 3 份。
6. 加 `--restart` 时重启游戏服务器；启动时会部署当前源码。

任何一步失败都会停止，不会继续打包或重启。版本号不能重复使用。

只编译不发布：`runuser -u steam -- python3 tools/compile_panorama_wine.py`（参数 `--tools-root` `--wineprefix` `--log-dir`）。

### 编译环境（CT270 已就绪）

- 编译工具目录：`/srv/steamcmd/linux32/steamapps/content/app_570/depot_381450`，属主 steam。其中 `game/dota_addons` 也须属于 steam。
- Steam 工具 depot 381450，Windows 引擎 depot 373303；均通过 SteamCMD 登录缓存下载，没有覆盖 Linux 游戏安装。
- 缺少的 core/dota 元数据和 VPK 链接到现有 Linux 安装。`assettypes_common.txt` 必须可被 steam 读取；root 所有且权限 0700 时，编译器会误报文件缺失。
- Wine 9.0 + Xvfb，Wine 前缀 `/var/lib/dota2/wine-tools`，编译日志 `/var/lib/dota2/compile-*.log`。

## 3. Windows 客户端安装包

面板"Windows 客户端资源"页提供两个固定下载：`/api/client-download?kind=exe` 和 `?kind=zip`。

- 只提供 `/opt/dota2-lan-kit/client-downloads` 下的两个文件，下载前核对大小、SHA-256，以及安装包对应的源码是否等于服务器源码。不一致时返回 409，等待重新发布。
- 安装包由 NSIS 生成，只含本项目客户端资源和安装脚本。`install.ps1` 以 UTF-8 BOM 写入，保证 Windows PowerShell 5.1 能读中文。

安装脚本的行为：

- 从注册表读取 Steam 路径，并解析 `libraryfolders.vdf`；也可以直接选择 `dota 2 beta` 目录。
- 候选目录先规范化，再不区分大小写去重。
- 要求 Dota 2 已退出；覆盖前备份到 `%LOCALAPPDATA%\Dota2LAN\Backups`，复制前后都核对哈希，失败时回滚。
- `game/dota_addons/lan_dota` 里新包不再包含的文件，先备份再删除。
- 结果写入 UTF-16 文件交给 NSIS 显示，避免中文乱码。

## 4. 客户端版本不一致时

- 进入游戏后，客户端比较自己编译时写入的源码哈希与服务器公布的 `source_sha256`。不一致时屏幕顶部持续显示"客户端资源版本与服务器不一致"，折叠工具窗口也不会隐藏。
- 服务器只记录不拒绝（日志事件 `CLIENT_BUILD`），面板概览会显示"N 名玩家的客户端资源版本不符"。
- 处理方法：退出 Dota 2，从面板重新下载并运行安装包。
