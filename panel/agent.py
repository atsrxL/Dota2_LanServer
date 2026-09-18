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
from .resources import ResourceMonitor
from .lan_addon import LanAddon
from .bots import BotLibrary, lookup_item, workshop_id, version_id
from .logs import SafeLog
from .process import GameProcess
from .steam import Cancelled, SteamJob

class Manager:
    def __init__(self, paths: Paths, workshop_lookup=None):
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
        self.bots = BotLibrary(paths)
        self.addon = LanAddon(paths)
        self.workshop_lookup = workshop_lookup or lookup_item
        self.resources = ResourceMonitor()
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
        if str(action).startswith('bot_') and (self.paths.state / 'bot-library/fixed-policy.json').exists():
            raise Fault("本服务器固定使用天地星；Bot 管理功能已存档停用", 403)
        if action not in ACTIONS:
            raise Fault("不支持此操作")
        for flag in ("stop_server", "restart_after", "select_after", "entry_probe"):
            if flag in data and type(data[flag]) is not bool:
                raise Fault(f"{flag} 必须为布尔值")
        with self.lock:
            if self.closed:
                raise Fault("代理正在退出", 503)
            if self.active:
                raise Fault("已有任务正在执行；请等待结束或取消当前任务。", 409)
            private: dict[str, Any] = {}
            if action in {"login", "install", "update", "validate", "bot_download"}:
                private = credentials({"username": data.get("username") or self.config["steam_username"],
                                       "password": data.get("password", ""), "guard": data.get("guard", "")})
            if action in {"bot_download", "bot_check", "bot_select", "bot_remove"}:
                private["item_id"] = workshop_id(data.get("item_id"))
            if action in {"bot_select", "bot_remove"} and data.get("version"):
                private["version"] = version_id(data["version"])
            if action in {"bot_select", "bot_download"}:
                difficulty = data.get("difficulty", 2)
                if type(difficulty) is not int or not 0 <= difficulty <= 3:
                    raise Fault("机器人难度必须在 0～3 之间")
                private.update(difficulty=difficulty, entry_probe=data.get("entry_probe", True))
            if action == "bot_remove" and not private.get("version"):
                raise Fault("移除机器人版本必须指定完整版本 SHA")
            if action == "bot_download" and shutil.disk_usage(self.paths.state).free < 1024**3 and not os.environ.get("DOTA_TEST_ROOT"):
                raise Fault("机器人安装至少需要 1 GiB 空闲空间", 409)
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
            if action == "addon_deploy" and self.game.running():
                raise Fault("附加模式部署必须先停服", 409)
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
            options = {"stop_server": data.get("stop_server", False), "restart_after": data.get("restart_after", False), "select_after": data.get("select_after", False)}
            self.worker = threading.Thread(target=self._run, args=(job, private, options), daemon=True)
            self.worker.start()
            self.audit.event(f"任务 {job['id']}：{action}")
            return dict(job)

    def _run(self, job: dict, private: dict, options: dict) -> None:
        log = SafeLog(self.paths.state / "logs" / f"{job['id']}.log", [private[k] for k in ("username", "password", "guard") if private.get(k)])
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
                        self._start_game()
            elif action in {"bot_download", "bot_check"}:
                self._stage("checking_workshop_metadata")
                metadata = self.workshop_lookup(private["item_id"])
                self._check_cancel()
                job["workshop"] = metadata
                log.event(f"Workshop {metadata['item_id']}：{metadata['title']}")
                if action == "bot_download":
                    runner = SteamJob(self.paths, log, self.cancel_event, self._ask, self._stage)
                    cred = {k: private[k] for k in ("username", "password", "guard")}
                    source = runner.run(cred, "workshop", private["item_id"])
                    self._check_cancel()
                    self._stage("installing_bot_version")
                    info = self.bots.install(source, metadata, self._check_cancel)
                    job["bot_version"] = info["version"]
                    log.event(f"文件安装完成：{info['version']}，{len(info['files'])} 个文件；未进行真实 AI 验收。")
                    if info['skipped_count']:
                        log.event(f"未部署 {info['skipped_count']} 个非脚本/数据文件，详见版本元数据。")
                    if options["select_after"]:
                        self._check_cancel()
                        self.bots.select({"item_id": private["item_id"], "version": info["version"],
                                          "difficulty": private["difficulty"], "entry_probe": private["entry_probe"]})
                        log.event("已设为下一局脚本。当前运行进程及其脚本没有改变。")
            elif action == "bot_select":
                job["selection"] = self.bots.select(private)
                log.event("已保存下一局选择，实际部署在下次手动启动/重启之前执行。")
            elif action == "bot_default":
                self.bots.select({"item_id": None})
                log.event("下次手动开局停用面板自定义机器人；恢复接管前 bots 目录（它可能也是用户脚本）。")
            elif action == "bot_rollback":
                job["selection"] = self.bots.rollback_selection()
                log.event("已恢复上次的下一局选择；不改变当前对局。")
            elif action == "bot_remove":
                self.bots.remove(private, self.game.bot_spec if self.game.running() else None)
                log.event("已移除未引用的脚本版本；SteamCMD 下载缓存未删除。")
            elif action == "addon_deploy":
                job["addon"] = self.addon.deploy()
                log.event("附加模式源文件已部署；编译资源与真实连通性仍须验收。")
            elif action == "addon_scan":
                report = self.addon.scan(self.bots)
                job["audit"] = {k: report[k] for k in ("content_sha256", "lua_files", "static_result")}
                log.event("静态扫描完成；未在此步骤执行第三方 Lua 或声明运行兼容。")
            elif action == "start":
                self.crashes.clear()
                self._start_game()
            elif action == "stop":
                self.game.stop()
            elif action == "restart":
                self.game.stop()
                self.crashes.clear()
                self._start_game()
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

    def _check_cancel(self):
        if self.cancel_event.is_set() or self.closed:
            raise Cancelled()

    def _start_game(self, reuse_running=False):
        policy = read_json(self.paths.state / 'bot-library/fixed-policy.json')
        if policy:
            selected = self.bots._selection().get('selected') or {}
            if any(selected.get(k) != policy.get(k) for k in ('item_id', 'version')):
                raise Fault("天地星固定版本与选择不一致；拒绝启动其他脚本", 409)
            if not self.addon.config['enabled'] or not self.addon.config['probe_bots']:
                raise Fault("本服必须启用 LAN 附加模式及天地星", 409)
        if self.game.running():
            raise Fault("服务器已经在运行", 409)
        if (self.paths.state / "maintenance.json").exists():
            raise Fault("安装维护未完成，禁止开服", 409)
        use_addon = bool(self.game.addon_spec) if reuse_running else self.addon.config["enabled"]
        if use_addon:
            spec, runtime = self.addon.prepare(self.bots, override=self.game.bot_spec, reuse=reuse_running,
                                               prior=self.game.addon_spec)
            self.game.start(self.config, spec, addon=runtime)
        else:
            spec = self.bots.prepare_launch(override=self.game.bot_spec, use_override=reuse_running)
            self.game.start(self.config, spec)

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
        resources = self.resources.sample()
        memory = resources['memory']
        try:
            disk = shutil.disk_usage(self.paths.game)
            disk_total, disk_free = disk.total, disk.free
        except OSError:
            disk_total = disk_free = None
        try:
            load = list(os.getloadavg())
        except OSError:
            load = []
        # Compatibility keys remain for existing consumers of /api/status.
        return {"disk_total": disk_total, "disk_free": disk_free, "load_average": load,
                "memory_current": memory['used_bytes'], "memory_max": memory['limit_bytes'],
                "memory_events": "\n".join(f"{k} {v}" for k,v in memory['events'].items()),
                "resources": resources}

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
                    "addon_active": bool(running and self.game.addon_spec),
                    "port": self.config["port"], "maintenance_block": read_json(self.paths.state / "maintenance.json"),
                    "active_job": dict(self.active) if self.active else None, "metrics": self.metrics(),
                    "bot_runtime": {"selection": self.game.bot_spec if running else None,
                                    "entry_seen": self.game.bot_entry_seen if running else False,
                                    "acceptance": "entry_executed_not_full_ai_verified" if running and self.game.bot_entry_seen else "not_verified"},
                    "crash_restarts_last_10min": len([x for x in self.crashes if x > time.time() - 600])}

    def diagnostics(self) -> dict:
        result = {"generated_at": now(), "version": VERSION, "platform": platform.platform(), "status": self.status(),
                  "notice": "这是本地运行诊断，不是客户端联机通过的证明。未包含 Steam 凭据缓存。"}
        try:
            running = self.game.running()
            preview_addon = self.game.addon_spec if running else ({"name": "lan_dota", "launch_method": self.addon.config["launch_method"]} if self.addon.config["enabled"] else None)
            preview_bot = self.game.bot_spec if running else (None if self.addon.config["enabled"] and not self.addon.config["probe_bots"] else self.bots._selection().get("selected"))
            cmd, _ = build_command(self.paths, self.config, preview_bot, preview_addon)
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
        if op == "addon":
            with self.lock:
                return self.addon.status(self.game)
        if op == "addon_report":
            with self.lock:
                return {"generated_at": now(), "version": VERSION, "game_manifest": manifest(self.paths),
                        "addon": self.addon.status(self.game), "server_log_tail": tail(self.paths.state / "logs/server.log", 32000),
                        "notice": "自动日志证据与静态审计，不是完整实机验收。分享前核对玩家名称和本地路径。"}
        if op == "save_addon":
            with self.lock:
                if self.active or self.game.running():
                    raise Fault("修改附加模式启动策略前先停服并结束任务", 409)
                return self.addon.save(data)
        if op == "bots":
            with self.lock:
                return self.bots.list()
        if op == "metrics":
            return self.resources.sample()
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
                if self.active["action"] not in {"login", "install", "update", "validate", "bot_download", "bot_check"}:
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
            with self.lock:
                if self.active and self.active["action"] not in {"bot_download", "bot_check", "login"}:
                    raise Fault("变更任务执行中不能操作游戏控制台", 409)
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
                    self._start_game(reuse_running=True)
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
