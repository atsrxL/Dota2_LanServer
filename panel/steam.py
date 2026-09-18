"""Interactive SteamCMD: password/Guard go through a non-echo PTY, never argv."""
from __future__ import annotations
import os
import re
import shutil
import time
import pexpect
from .common import Fault, Paths, installed, manifest
from .logs import SafeLog
from .process import terminate_child
from .bots import locate_download, workshop_id

class Cancelled(Fault):
    def __init__(self):
        super().__init__("任务已取消；若中断安装/更新，成功校验前禁止启动游戏。", 409)

class SteamJob:
    def __init__(self, paths: Paths, log: SafeLog, cancel, ask, stage):
        self.paths, self.log, self.cancel, self.ask, self.stage = paths, log, cancel, ask, stage
        self.child = None
        self.workshop_active = False

    def _expect(self, patterns: list, timeout: float):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.cancel.is_set():
                raise Cancelled()
            if self.workshop_active and not os.environ.get("DOTA_TEST_ROOT"):
                if min(shutil.disk_usage(p).free for p in (self.paths.steam, self.paths.game, self.paths.state)) < 512 * 1024**2:
                    raise Fault("Workshop 下载期间空闲磁盘低于 512 MiB；已中止，保留现用脚本。", 409)
            i = self.child.expect(patterns + [pexpect.EOF, pexpect.TIMEOUT], timeout=min(1, max(0.01, end - time.monotonic())))
            if i == len(patterns):
                raise Fault("SteamCMD 意外退出；请检查任务日志、网络与磁盘。", 409)
            if i < len(patterns):
                return i
        raise Fault("SteamCMD 等待超时；请检查任务日志，必要时重新登录。", 408)

    def _command(self, text: str, timeout: float = 90):
        self.child.sendline(text)
        self._expect([r"Steam>"], timeout)
        return self.child.before or ""

    def _login(self, cred: dict) -> None:
        self.stage("logging_in")
        self.log.event("登录 Steam；密码和验证码仅提交给 SteamCMD，应用不将它们保存到配置。")
        for value in cred.values():
            self.log.add_secret(value)
        self.child.sendline("login " + cred["username"])
        patterns = [r"(?i)(?:password|密码)\s*:\s*", r"(?i)(?:Steam Guard code|two.factor code|authenticator code)\s*:\s*",
                    r"(?i)(?:confirm.*(?:sign.?in|login).*request|waiting for.*(?:confirmation|approval)|check your.*Steam.*app)",
                    r"Steam>"]
        auth_text = ""
        deadline = time.monotonic() + 600
        sent_password = False
        while time.monotonic() < deadline:
            i = self._expect(patterns, min(600, max(1, deadline - time.monotonic())))
            auth_text = (auth_text + (self.child.before or "") + str(self.child.after or ""))[-30000:]
            if i == 0:
                value = cred.get("password", "") if not sent_password else ""
                if not value:
                    value = self.ask("password", "SteamCMD 正在等待密码；请在任务输入框提交。")
                self.log.add_secret(value)
                self.child.sendline(value)
                sent_password = True
            elif i == 1:
                value = cred.pop("guard", "") or self.ask("guard", "请提交 Steam Guard 验证码，或完成手机端批准。")
                self.log.add_secret(value)
                self.child.sendline(value)
            elif i == 2:
                self.stage("awaiting_mobile_approval")
                self.log.event("请在 Steam 手机客户端批准登录；本任务会继续等待。")
            else:
                # Do not treat merely receiving the command prompt as login success.
                ok = re.search(r"(?is)(Waiting for user info[^\n]*OK|Logged in (?:OK|successfully)|Logging in[^\n]*\.\.\.OK|Connecting anonymously[^\n]*OK)", auth_text)
                bad = re.search(r"(?i)(Login Failure|Invalid Password|InvalidPassword|AccessDenied|No subscription|Account Logon Denied)", auth_text)
                if not ok or bad:
                    raise Fault("Steam 登录未确认成功。核对账号名、密码、授权和验证码，查看任务日志。", 409)
                self.stage("authenticated")
                return
        raise Fault("Steam 登录授权超时", 408)

    def _workshop(self, item: str):
        item = workshop_id(item)
        self.workshop_active = True
        self.stage("downloading_workshop")
        self.log.event(f"下载 Dota 2 Workshop 条目 {item}；不会修改正在运行的脚本。")
        self.child.sendline(f"workshop_download_item 570 {item} validate")
        success, output = False, ""
        deadline = time.monotonic() + 2 * 3600
        patterns = [r"(?i)Success\.\s+Downloaded item\s+" + re.escape(item) + r"\b[^\r\n]*",
                    r"(?i)(?:ERROR!|Failure|Download item failed)[^\r\n]*", r"Steam>"]
        while time.monotonic() < deadline:
            i = self._expect(patterns, max(1, deadline - time.monotonic()))
            output = (output + (self.child.before or "") + str(self.child.after or ""))[-16000:]
            if i == 0:
                success = True
            elif i == 1:
                raise Fault("SteamCMD 报告 Workshop 下载失败；检查账号授权、网络和任务日志。保留现用版本。", 409)
            else:
                break
        if not success:
            raise Fault("没有收到指定 Workshop ID 的下载成功标记，不能使用磁盘上的旧文件冒充成功。", 409)
        self.stage("checking_workshop_files")
        return locate_download(self.paths, item, output)

    def run(self, cred: dict, mode: str, item: str | None = None):
        launcher = self.paths.steam / "steamcmd.sh"
        if not launcher.is_file():
            raise Fault("未找到 SteamCMD；请重新执行 LXC 环境安装脚本。", 409)
        env = os.environ.copy()
        env.update(HOME=str(self.paths.state), USER="steam", LOGNAME="steam", LANG="C.UTF-8", TERM="xterm")
        self.log.event("启动 Valve SteamCMD。首次自更新可能暂时没有下载百分比。")
        self.stage("steamcmd_bootstrap")
        try:
            self.child = pexpect.spawn("/bin/bash", [str(launcher)], cwd=str(self.paths.steam), env=env,
                                       encoding="utf-8", codec_errors="replace", echo=False, timeout=1,
                                       dimensions=(40, 160))
            self.child.logfile_read = self.log
            self._expect([r"Steam>"], 300)
            self._command('@sSteamCmdForcePlatformType linux')
            self._command(f'force_install_dir "{self.paths.game}"')
            self._login(dict(cred))
            if mode == "workshop":
                return self._workshop(item)
            if mode == "login":
                self.log.event("登录测试完成。Valve 是否保留可复用登录状态，以其后续行为为准。")
                return
            self.stage("validating" if mode in {"install", "validate"} else "updating")
            command = "app_update 570" + (" validate" if mode in {"install", "validate"} else "")
            self.child.sendline(command)
            saw_success = False
            end = time.monotonic() + 12 * 3600
            patterns = [r"(?i)Success!\s+App\s+'?570'?[^\r\n]*(?:fully installed|already up to date)[^\r\n]*",
                        r"(?i)ERROR![^\r\n]*", r"Steam>"]
            while time.monotonic() < end:
                i = self._expect(patterns, max(1, end - time.monotonic()))
                if i == 0:
                    saw_success = True
                    self.stage("checking_installation")
                elif i == 1:
                    raise Fault("SteamCMD 报告安装/更新错误；请检查任务日志。不会自动启动游戏。", 409)
                elif i == 2:
                    break
            if not saw_success:
                raise Fault("没有收到 App 570 安装成功标志；不把退出码或文件存在当作下载成功。", 409)
            state = manifest(self.paths)
            if not installed(self.paths) or state.get("StateFlags") != "4":
                raise Fault("SteamCMD 返回成功，但本地 Linux 启动文件或完整安装状态不匹配；请检查诊断。", 409)
            self.log.event(f"App 570 安装完整性检查通过；本地 buildid={state.get('buildid', 'unknown')}。")
        except (pexpect.ExceptionPexpect, OSError) as exc:
            # Do not serialize pexpect exceptions: they can contain sensitive child buffers.
            raise Fault(f"SteamCMD 交互失败（{type(exc).__name__}）；查看已脱敏任务日志。", 500) from None
        finally:
            if self.child:
                terminate_child(self.child, graceful=1.5, send_quit=not self.cancel.is_set())
                try:
                    self.child.close(force=True)
                except Exception:
                    pass
            self.log.finish()
