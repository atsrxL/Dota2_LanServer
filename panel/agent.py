"""Unprivileged process supervisor with authenticated-by-filesystem Unix RPC."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
import platform
import re
import shutil
import signal
import socket
import socketserver
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from .common import (ACTIONS, DEFAULT_CONFIG, VERSION, Fault, Paths, atomic_json, build_command,
                     credentials, installed, manifest, new_id, now, plain, read_json, tail, validate_config)
from .logs import SafeLog
from .process import GameProcess
from .steam import Cancelled, SteamJob

class Manager:
    def __init__(self, paths: Paths):
        self.paths = paths
        paths.prepare()
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.input_event = threading.Event()
        self.pending_input = ""
        self.active: dict | None = None
        self.worker = None
        self.closed = False
        self.game = GameProcess(paths)
        self.audit = SafeLog(paths.state / "logs/agent.log")
        self.config = validate_config(read_json(paths.config, DEFAULT_CONFIG.copy()))
        if not paths.config.exists():
            atomic_json(paths.config, self.config)
        self.jobs: list[dict] = read_json(paths.state / "jobs.json", [])
        for job in self.jobs:
            if job.get("state") in {"running", "waiting"}:
                job.update(state="interrupted", stage="agent_restarted", finished_at=now(), waiting_for=None,
                           message="运行代理被重启；不会盲目恢复上次操作。")
        self._persist()
        self.crashes: list[float] = []
        self.handled_generation = 0
        self.audit.event("运行代理启动；SteamCMD 与游戏均使用非特权 steam 用户。")

    def _persist(self) -> None:
        atomic_json(self.paths.state / "jobs.json", self.jobs[-100:])

    def _stage(self, stage: str) -> None:
        with self.lock:
            if self.active:
                self.active["stage"] = stage
                self._persist()

    def _ask(self, kind: str, message: str) -> str:
        with self.lock:
            if not self.active:
                raise Fault("任务已结束", 409)
            self.pending_input = ""
            self.input_event.clear()
            self.active.update(state="waiting", waiting_for=kind, message=message)
            self._persist()
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if self.cancel_event.is_set() or self.closed:
                raise Cancelled()
            if self.input_event.wait(0.5):
                with self.lock:
                    result = self.pending_input
                    self.pending_input = ""
                    self.active.update(state="running", waiting_for=None, message="输入已交给 SteamCMD。")
                    self._persist()
                    return result
        raise Fault("等待密码/验证码超过 5 分钟；任务已停止，请重新登录。", 408)

    def provide_input(self, data: dict) -> dict:
        with self.lock:
            if not self.active or data.get("job_id") != self.active["id"] or not self.active.get("waiting_for"):
                raise Fault("当前任务没有等待输入，或任务 ID 已变化", 409)
            if self.input_event.is_set():
                raise Fault("上一条输入正在处理", 409)
            value = plain(data.get("value", ""), "输入", 256, False)
            if self.active["waiting_for"] == "guard" and not re.fullmatch(r"[A-Za-z0-9]{4,12}", value):
                raise Fault("验证码格式无效")
            self.pending_input = value
            self.input_event.set()
            return {"ok": True}

    def submit(self, data: dict) -> dict:
        action = data.get("action")
        if action not in ACTIONS:
            raise Fault("不支持此操作")
        for flag in ("stop_server", "restart_after"):
            if flag in data and type(data[flag]) is not bool:
                raise Fault(f"{flag} 必须为布尔值")
        with self.lock:
            if self.closed:
                raise Fault("代理正在退出", 503)
            if self.active:
                raise Fault("已有任务正在执行；请等待结束或取消当前任务。", 409)
            private: dict[str, Any] = {}
            if action in {"login", "install", "update", "validate"}:
                private = credentials({"username": data.get("username") or self.config["steam_username"],
                                       "password": data.get("password", ""), "guard": data.get("guard", "")})
            if action in {"install", "update", "validate"}:
                if self.game.running() and not data.get("stop_server", False):
                    raise Fault("游戏正在运行；先停服，或明确允许本次维护停服。", 409)
                # Conservative headroom; actual depot size changes and may need more.
                free = shutil.disk_usage(self.paths.game).free
                required = (100 if not installed(self.paths) else 20) * 1024**3
                if free < required and not os.environ.get("DOTA_TEST_ROOT"):
                    raise Fault(f"剩余磁盘不足，初装建议至少 100 GiB、更新至少 20 GiB 空闲。当前 {free / 1024**3:.1f} GiB。", 409)
            if action in {"start", "restart"}:
                if (self.paths.state / "maintenance.json").exists():
                    raise Fault("存在未完成维护标记；先成功更新/校验，不能启动可能损坏的安装。", 409)
                if not installed(self.paths):
                    raise Fault("请先安装 Dota 2", 409)
            if action == "restore":
                if self.game.running():
                    raise Fault("恢复配置前请先停服", 409)
                private["backup"] = self._backup_file(data.get("backup", ""))
            job = {"id": new_id(), "action": action, "state": "running", "stage": "starting",
                   "started_at": now(), "finished_at": None, "waiting_for": None, "message": "任务已提交。"}
            self.jobs = self.jobs[-99:] + [job]
            self.active = job
            self.cancel_event = threading.Event()
            self.input_event = threading.Event()
            self._persist()
            options = {"stop_server": data.get("stop_server", False), "restart_after": data.get("restart_after", False)}
            self.worker = threading.Thread(target=self._run, args=(job, private, options), daemon=True)
            self.worker.start()
            self.audit.event(f"任务 {job['id']}：{action}")
            return dict(job)

    def _run(self, job: dict, private: dict, options: dict) -> None:
        log = SafeLog(self.paths.state / "logs" / f"{job['id']}.log", [v for v in private.values() if isinstance(v, str)])
        action = job["action"]
        was_running = self.game.running()
        try:
            log.event(f"开始 {action}")
            if action in {"install", "update", "validate", "login"}:
                if action != "login":
                    self._backup()
                    if was_running:
                        self._stage("stopping_server")
                        self.game.stop()
                    atomic_json(self.paths.state / "maintenance.json", {"job": job["id"], "action": action, "started_at": now()})
                runner = SteamJob(self.paths, log, self.cancel_event, self._ask, self._stage)
                runner.run(private, action)
                if self.cancel_event.is_set():
                    raise Cancelled()
                if action != "login":
                    (self.paths.state / "maintenance.json").unlink(missing_ok=True)
                    if was_running and options["restart_after"]:
                        self._stage("restarting_server")
                        self.game.start(self.config)
            elif action == "start":
                self.crashes.clear()
                self.game.start(self.config)
            elif action == "stop":
                self.game.stop()
            elif action == "restart":
                self.game.stop()
                self.crashes.clear()
                self.game.start(self.config)
            elif action == "backup":
                filename = self._backup()
                log.event(f"配置备份已保存：{filename}")
                job["backup"] = filename
            elif action == "restore":
                restored = validate_config(read_json(private["backup"]))
                self._backup()
                with self.lock:
                    atomic_json(self.paths.config, restored)
                    self.config = restored
                log.event("配置已恢复；没有恢复 Steam 缓存、游戏文件或比赛状态。")
            with self.lock:
                job.update(state="success", stage="complete", message="任务完成；游戏实际连接仍需客户端验证。")
        except Cancelled as exc:
            with self.lock:
                job.update(state="cancelled", stage="cancelled", message=str(exc))
            log.event(str(exc))
        except Fault as exc:
            with self.lock:
                job.update(state="failed", stage="failed", message=log.clean(str(exc)))
            log.event(str(exc))
        except Exception as exc:
            # Never write raw repr(traceback), which might contain request secrets.
            message = f"内部错误 {type(exc).__name__}；保留日志并按接手文件排查。"
            with self.lock:
                job.update(state="failed", stage="failed", message=message)
            log.event(message)
        finally:
            private.clear()
            log.finish()
            with self.lock:
                job.update(finished_at=now(), waiting_for=None)
                self.pending_input = ""
                self.active = None
                self._persist()
                self.audit.event(f"任务 {job['id']} 结束：{job['state']}")
                # Bounded on-disk job logs; keep the current history's 100 jobs.
                keep = {j["id"] for j in self.jobs}
                for path in (self.paths.state / "logs").glob("job-*.log*"):
                    if path.name.split(".log", 1)[0] not in keep:
                        path.unlink(missing_ok=True)

    def _backup_file(self, name: Any) -> Path:
        if not isinstance(name, str) or not re.fullmatch(r"cfg-\d{8}-\d{6}-[a-f0-9]{8}\.json", name):
            raise Fault("备份名称不正确")
        path = self.paths.state / "backups" / name
        if not path.is_file() or path.is_symlink():
            raise Fault("配置备份不存在", 404)
        return path

    def _backup(self) -> str:
        name = new_id("cfg") + ".json"
        atomic_json(self.paths.state / "backups" / name, self.config)
        for path in sorted((self.paths.state / "backups").glob("cfg-*.json"), reverse=True)[20:]:
            path.unlink(missing_ok=True)
        return name

    def save_config(self, raw: dict) -> dict:
        config = validate_config(raw)
        with self.lock:
            if self.active:
                raise Fault("任务运行中不能修改配置", 409)
            self._backup()
            atomic_json(self.paths.config, config)
            self.config = config
            self.audit.event("服务器配置已更新；游戏参数需下次启动生效。")
            return {"ok": True, "restart_required": self.game.running(),
                    "notice": "更改游戏端口后，须同步修改 PVE 防火墙规则；面板不会修改宿主。"}

    def metrics(self) -> dict:
        usage = shutil.disk_usage(self.paths.game)
        result = {"disk_total": usage.total, "disk_free": usage.free, "load_average": list(os.getloadavg()),
                  "memory_current": None, "memory_max": None, "memory_events": ""}
        root = Path("/sys/fs/cgroup")
        try:
            current = root.joinpath("memory.current").read_text().strip()
            maximum = root.joinpath("memory.max").read_text().strip()
            result.update(memory_current=int(current), memory_max=int(maximum) if maximum.isdigit() else None,
                          memory_events=root.joinpath("memory.events").read_text()[:2000])
        except (OSError, ValueError):
            pass
        return result

    def status(self) -> dict:
        with self.lock:
            running = self.game.running()
            udp = False
            for path in ("/proc/net/udp", "/proc/net/udp6"):
                try:
                    for line in Path(path).read_text().splitlines()[1:]:
                        if int(line.split()[1].rsplit(":", 1)[1], 16) == self.config["port"]:
                            udp = True
                except (OSError, ValueError, IndexError):
                    pass
            return {"version": VERSION, "installed": installed(self.paths), "manifest": manifest(self.paths),
                    "running": running, "pid": self.game.child.pid if running else None,
                    "uptime": int(time.time() - self.game.started_at) if running and self.game.started_at else 0,
                    "last_exit": self.game.last_exit, "udp_port_listening": udp,
                    "readiness": "process_running_client_check_required" if running else "stopped",
                    "port": self.config["port"], "maintenance_block": read_json(self.paths.state / "maintenance.json"),
                    "active_job": dict(self.active) if self.active else None, "metrics": self.metrics(),
                    "crash_restarts_last_10min": len([x for x in self.crashes if x > time.time() - 600])}

    def diagnostics(self) -> dict:
        result = {"generated_at": now(), "version": VERSION, "platform": platform.platform(), "status": self.status(),
                  "notice": "这是本地运行诊断，不是客户端联机通过的证明。未包含 Steam 凭据缓存。"}
        try:
            cmd, _ = build_command(self.paths, self.config)
            for i, part in enumerate(cmd[:-1]):
                if part == "+sv_password":
                    cmd[i + 1] = "[REDACTED]"
            result["launch_argv"] = cmd
        except Fault as exc:
            result["launch_error"] = str(exc)
        binary = self.paths.game / "game/bin/linuxsteamrt64/dota2"
        if binary.is_file():
            try:
                # Only a fixed Valve path, unprivileged, bounded; no arbitrary executable input.
                p = subprocess.run(["/usr/bin/ldd", str(binary)], capture_output=True, text=True, timeout=8,
                                   env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
                result["ldd"] = (p.stdout + p.stderr)[-16000:]
            except (OSError, subprocess.TimeoutExpired):
                result["ldd"] = "ldd 不可用或超时"
        result["sdk64_link"] = str(self.paths.state / ".steam/sdk64/steamclient.so")
        result["sdk64_link_exists"] = (self.paths.state / ".steam/sdk64/steamclient.so").exists()
        result["logs"] = {"agent": tail(self.paths.state / "logs/agent.log", 16000),
                          "server": tail(self.paths.state / "logs/server.log", 32000)}
        return result

    def dispatch(self, request: dict) -> Any:
        if not isinstance(request, dict):
            raise Fault("请求必须是 JSON 对象")
        op, data = request.get("op"), request.get("data", {})
        if not isinstance(data, dict):
            raise Fault("请求 data 必须是对象")
        if op == "status":
            return self.status()
        if op == "config":
            with self.lock:
                return dict(self.config)
        if op == "save_config":
            return self.save_config(data)
        if op == "submit":
            return self.submit(data)
        if op == "input":
            return self.provide_input(data)
        if op == "cancel":
            with self.lock:
                if not self.active or self.active["id"] != data.get("job_id"):
                    raise Fault("任务不存在或已结束", 409)
                if self.active["action"] not in {"login", "install", "update", "validate"}:
                    raise Fault("该短操作不能取消", 409)
                self.cancel_event.set()
                return {"ok": True, "message": "已请求取消，等待 SteamCMD 安全退出。"}
        if op == "jobs":
            with self.lock:
                return [dict(j) for j in reversed(self.jobs)]
        if op == "backups":
            return [{"name": p.name, "bytes": p.stat().st_size} for p in sorted((self.paths.state / "backups").glob("cfg-*.json"), reverse=True)]
        if op == "backup_read":
            return read_json(self._backup_file(data.get("name")))
        if op == "console":
            self.game.console(data)
            return {"ok": True}
        if op == "logs":
            name = data.get("name", "server")
            if name in {"server", "agent"}:
                path = self.paths.state / "logs" / f"{name}.log"
            elif isinstance(name, str) and re.fullmatch(r"job-\d{8}-\d{6}-[a-f0-9]{8}", name):
                path = self.paths.state / "logs" / f"{name}.log"
            else:
                raise Fault("非法日志名称")
            return {"name": name, "text": tail(path)}
        if op == "diagnostics":
            return self.diagnostics()
        raise Fault("未知 RPC 操作", 404)

    def monitor(self) -> None:
        if self.config["auto_start"] and installed(self.paths) and not (self.paths.state / "maintenance.json").exists():
            try:
                self.submit({"action": "start"})
            except Fault as exc:
                self.audit.event(str(exc))
        while not self.closed:
            time.sleep(2)
            with self.lock:
                if self.active or self.game.running() or self.game.expected_stop or not self.config["auto_restart"]:
                    continue
                if self.handled_generation == self.game.generation:
                    continue
                self.handled_generation = self.game.generation
                self.crashes = [x for x in self.crashes if x > time.time() - 600]
                if len(self.crashes) >= 3 or (self.paths.state / "maintenance.json").exists():
                    self.audit.event("已停止自动拉起：10 分钟内最多重试 3 次，或安装维护尚未完成。")
                    continue
                self.crashes.append(time.time())
                self.audit.event("检测到游戏意外退出；准备自动重新启动。")
                # Do not use submit(start), which intentionally resets manual retry budget.
                try:
                    self.game.start(self.config)
                except Fault as exc:
                    self.audit.event(str(exc))

    def close(self) -> None:
        self.closed = True
        self.cancel_event.set()
        if self.worker:
            self.worker.join(timeout=10)
        self.game.stop()


class RPCHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(15)
        try:
            raw = self.rfile.readline(65537)
            if len(raw) > 65536 or not raw.endswith(b"\n"):
                raise Fault("RPC 请求过大或不完整", 413)
            request = json.loads(raw)
            result = self.server.manager.dispatch(request)
            reply = {"ok": True, "result": result}
        except Fault as exc:
            reply = {"ok": False, "error": str(exc), "code": exc.code}
        except (ValueError, UnicodeError):
            reply = {"ok": False, "error": "无效 JSON", "code": 400}
        except Exception as exc:
            reply = {"ok": False, "error": f"代理错误：{type(exc).__name__}", "code": 500}
        try:
            self.wfile.write(json.dumps(reply, ensure_ascii=False).encode() + b"\n")
        except (OSError, BrokenPipeError):
            pass

class RPCServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    request_queue_size = 32


def rpc(op: str, data: dict | None = None, paths: Paths | None = None) -> Any:
    paths = paths or Paths.from_env()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(20)
            s.connect(str(paths.socket))
            s.sendall(json.dumps({"op": op, "data": data or {}}, ensure_ascii=False).encode() + b"\n")
            with s.makefile("rb") as f:
                raw = f.readline(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise Fault("代理响应超限", 502)
            reply = json.loads(raw)
            if not reply.get("ok"):
                raise Fault(reply.get("error", "代理错误"), reply.get("code", 500))
            return reply["result"]
    except (OSError, ValueError) as exc:
        raise Fault(f"无法连接运行代理（{type(exc).__name__}）。检查 dota-agent.service。", 503) from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    paths = Paths.from_env()
    paths.prepare()
    # Hold a lifetime lock before unlinking any stale socket.
    with (paths.state / "agent.lock").open("a") as lockfile:
        try:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("已有运行代理，不能重复启动")
        manager = Manager(paths)
        if args.check:
            print(json.dumps(manager.status(), ensure_ascii=False, indent=2))
            return
        paths.socket.unlink(missing_ok=True)
        server = RPCServer(str(paths.socket), RPCHandler)
        server.manager = manager
        os.chmod(paths.socket, 0o660)
        def shutdown(*_):
            manager.closed = True
            manager.cancel_event.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        threading.Thread(target=manager.monitor, daemon=True).start()
        try:
            server.serve_forever(poll_interval=0.25)
        finally:
            manager.close()
            server.server_close()
            paths.socket.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
