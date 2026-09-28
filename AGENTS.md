# 接手规则（先读）

用户要 PVE 的单实例 Dota 2 LAN 服务器，不是 Docker/VM 改造。Ubuntu 24.04 amd64 非特权 LXC、nesting=0；不要自行增配、引入 Docker、GPU、特权容器或公网暴露。

先读 `README.md`、`docs/RELEASE.md`、`docs/OPERATIONS.md`，再进入相关源码。`docs/archive/` 是历史记录，其中描述的机器人管理页、附加模式管理页等已移除。

## 安全与边界

- 不得向用户索取 Steam 密码、Guard、管理员密码或私钥，也不得把它们写入源码、env、命令行、日志、提交记录或交接文件。网页有一次性输入通道，真实授权由用户本人输入。
- 不用 `shell=True`，不提供任意命令或路径入口、sudo 代理、Docker socket。新功能维持固定动作白名单、CSRF、Origin 校验、Unix socket 权限、JSON 原子写、任务互斥与停服更新。
- 面板仅 HTTP、免登录，这是用户的硬约束。Steam/Guard 授权必须保留；LAN 白名单和防跨站校验不是登录功能，不可删除。
- 宿主脚本只操作明确的 CT，不调整全局防火墙或内核，不自动删除 CT；现场先 dry-run。
- 不为了得到"成功"状态删除维护保护文件，或忽略 SteamCMD 的失败。

## 附加模式与发布

- 游戏内 UI 必须用官方 resourcecompiler 真实编译（服务器上的 `tools/release.py`）。不得把测试用的合成资源放进 `compiled/`，也不得把 XML 改名冒充编译产物。
- 保留引擎事件来源身份校验，不信任 payload 里的 PlayerID。
- 改了 UI 或 Lua 就发布新版本：服务器、编译资源、客户端安装包必须来自同一源码哈希。
- 重启 `dota-agent` 会结束正在进行的对局。部署前先确认没有玩家在线（`tools/deploy_kit.py` 会检查）。

## 开发与验证

- 运行 `bash scripts/test.sh`，依赖在 `requirements-dev.txt`。修改 Steam 交互、游戏启动参数或游戏内行为时，增加对应的模拟测试（Python / Lua spec / Panorama mock）。
- 交付结论分清哪些是代码测试，哪些是真实服务器和客户端验证；没实测的写明未实测。
- 现场操作和验证结果追加到 `docs/OPERATIONS.md`。

## 代码风格

仓库里有大量一行几百字符的旧代码，不要整体重排，以免污染 git 历史。新增或修改的代码按正常方式换行：

- 一行一条语句，行宽尽量不超过 120。
- Lua 和 Python 用 4 空格或沿用所在文件的缩进；HTML 一个元素一行。
- 修改旧的长行时，可以顺手把被改的那一段拆开。
