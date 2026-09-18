"""PTY-backed game process; there is no shell command endpoint and no sudo."""
from __future__ import annotations
import os
import re
import signal
import threading
import time
import pexpect
from .common import Fault, Paths, build_command, engine_text
from .logs import SafeLog
from .addon_runtime import AddonTelemetry


def terminate_child(child, graceful: float = 15.0, send_quit: bool = True) -> None:
    if child is None:
        return
    try:
        if child.isalive() and send_quit:
            child.sendline("quit")
        deadline = time.monotonic() + graceful
        while child.isalive() and time.monotonic() < deadline:
            time.sleep(0.1)
        if child.isalive():
            os.killpg(child.pid, signal.SIGTERM)
            deadline = time.monotonic() + 4
            while child.isalive() and time.monotonic() < deadline:
                time.sleep(0.1)
        if child.isalive():
            os.killpg(child.pid, signal.SIGKILL)
    except (ProcessLookupError, OSError, pexpect.ExceptionPexpect):
        pass

class GameProcess:
    def __init__(self, paths: Paths):
        self.paths = paths
        self.child = None
        self.log = None
        self.reader = None
        self.lock = threading.RLock()
        self.started_at = None
        self.last_exit = None
        self.expected_stop = True
        self.generation = 0
        self.bot_spec = None
        self.bot_entry_seen = False
        self.addon_spec = None
        self.addon_telemetry = None

    def running(self) -> bool:
        return bool(self.child and self.child.isalive())

    def start(self, config: dict, bot: dict | None = None, addon: dict | None = None) -> None:
        with self.lock:
            if self.running():
                raise Fault("服务器已经在运行", 409)
            cmd, env = build_command(self.paths, config, bot, addon)
            self.addon_spec = addon
            self.addon_telemetry = AddonTelemetry(addon["session"]) if addon else None
            self.bot_spec = dict(bot) if bot else None
            self.bot_entry_seen = False
            self.log = SafeLog(self.paths.state / "logs/server.log", [config["game_password"]])
            self.log.event("启动 Dota 2 LAN；进程存活不等于客户端连接验收通过。")
            # pexpect creates a separate session; its PID is the process-group ID.
            self.child = pexpect.spawn(cmd[0], cmd[1:], cwd=str(self.paths.game / "game" if (self.paths.game / "game").is_dir() else self.paths.game),
                                       env=env, encoding="utf-8", codec_errors="replace", echo=False,
                                       timeout=0.5, dimensions=(40, 160))
            self.started_at = time.time()
            self.expected_stop = False
            self.generation += 1
            self.reader = threading.Thread(target=self._read, args=(self.child, self.log, self.bot_spec, self.addon_telemetry), daemon=True)
            self.reader.start()
        time.sleep(1.5)
        if not self.running():
            raise Fault("游戏进程启动后退出，请查看服务器日志和诊断。", 409)

    def _read(self, child, log, bot=None, addon_telemetry=None) -> None:
        probe_buffer = ""
        try:
            while True:
                try:
                    data = child.read_nonblocking(8192, timeout=0.5)
                    log.write(data)
                    if addon_telemetry is not None:
                        addon_telemetry.feed(data)
                    if bot and bot.get("probe_token"):
                        probe_buffer = (probe_buffer + data)[-4096:]
                        marker = "DOTA_PANEL_BOT_ENTRY:" + bot["probe_token"] + ":hero_selection"
                        if child is self.child and re.search(r'(?:^|[\r\n])' + re.escape(marker) + r'\r?\n', probe_buffer):
                            self.bot_entry_seen = True
                except pexpect.TIMEOUT:
                    if not child.isalive():
                        break
                except pexpect.EOF:
                    break
        finally:
            try:
                child.close(force=False)
            except Exception:
                pass
            self.last_exit = {"exit_code": child.exitstatus, "signal": child.signalstatus, "at": time.time()}
            log.finish()
            log.event(f"游戏进程结束：exit={child.exitstatus}, signal={child.signalstatus}")

    def stop(self) -> None:
        with self.lock:
            self.expected_stop = True
            child = self.child
            if child and self.log:
                self.log.event("请求正常退出；超时后仅终止本代理创建的进程组。")
            terminate_child(child)
            if self.reader:
                self.reader.join(timeout=5)

    def console(self, raw: dict) -> None:
        name = raw.get("command")
        if name == "bots":
            raise Fault("Bot 控制功能已停用；机器人由游戏内准备界面自动填充。", 409)
        if name in {"lan_status", "lan_release_host"} and not self.addon_spec:
            raise Fault("当前不是 LAN 附加模式", 409)
        presets = {"status": "status", "pause": "dota_pause",
                   "lan_status": "lan_status", "lan_release_host": "lan_release_host"}
        if name == "say":
            text = engine_text(raw.get("text", ""), "聊天内容", 160, False)
            command = f'say "{text}"'
        elif name in presets:
            command = presets[name]
        else:
            raise Fault("只允许固定的 status / pause / say / lan_status / lan_release_host 命令")
        with self.lock:
            if not self.running():
                raise Fault("游戏未运行", 409)
            self.child.sendline(command)
            self.log.event(f"已向游戏控制台发送 {name}；是否支持请以游戏日志为准。")
