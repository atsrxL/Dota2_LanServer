"""Shared validation, atomic persistence and process-independent utilities."""
from __future__ import annotations
import json
import os
import re
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VERSION = "1.3.0"
DEFAULT_CONFIG = {
    "schema": 1, "hostname": "Dota 2 LAN", "port": 27015, "map": "dota",
    "game_mode": 1, "game_password": "", "insecure": False, "cheats": False,
    "auto_start": False, "auto_restart": True, "steam_username": "",
}
ACTIONS = {"login", "install", "update", "validate", "start", "stop", "restart", "backup", "restore", "bot_download", "bot_check", "bot_select", "bot_default", "bot_rollback", "bot_remove", "addon_deploy", "addon_scan"}
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

class Fault(Exception):
    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code

@dataclass(frozen=True)
class Paths:
    state: Path = Path("/var/lib/dota2")
    game: Path = Path("/srv/dota2")
    steam: Path = Path("/srv/steamcmd")
    socket: Path = Path("/run/dota-agent/control.sock")

    @classmethod
    def from_env(cls) -> "Paths":
        # Only service/CLI environment, never values from HTTP requests.
        base = os.environ.get("DOTA_TEST_ROOT")
        if base:
            p = Path(base).resolve()
            return cls(p / "state", p / "game", p / "steam", p / "run/control.sock")
        return cls()

    def prepare(self) -> None:
        for p in (self.state, self.game, self.steam, self.state / "logs", self.state / "backups"):
            p.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.socket.parent.mkdir(parents=True, exist_ok=True, mode=0o750)

    @property
    def config(self) -> Path:
        return self.state / "server.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".new-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path: Path, fallback: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except (ValueError, UnicodeError) as exc:
        raise Fault(f"JSON 文件损坏，请从配置备份恢复：{path.name}", 500) from exc


def plain(value: Any, name: str, limit: int = 120, empty: bool = True) -> str:
    if not isinstance(value, str) or len(value) > limit or (not empty and not value):
        raise Fault(f"{name} 长度或类型不正确")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise Fault(f"{name} 不得含换行或控制字符")
    return value


def engine_text(value: Any, name: str, limit: int = 80, empty: bool = True) -> str:
    value = plain(value, name, limit, empty)
    if any(c in value for c in (';', '"', "\\", "`")) or value.startswith(("+", "-")):
        raise Fault(f"{name} 不得包含引号、分号、反斜线、反引号或以 +/- 开头")
    return value


def validate_config(raw: Any) -> dict:
    if not isinstance(raw, dict) or set(raw) - set(DEFAULT_CONFIG):
        raise Fault("配置含未知字段，不能指定任意路径或可执行命令")
    c = DEFAULT_CONFIG | raw
    if type(c["schema"]) is not int or c["schema"] != 1:
        raise Fault("配置版本不受支持")
    for key, low, high in (("port", 1024, 65535), ("game_mode", 0, 30)):
        if type(c[key]) is not int or not low <= c[key] <= high:
            raise Fault(f"{key} 必须在 {low}～{high} 之间")
    for key in ("insecure", "cheats", "auto_start", "auto_restart"):
        if type(c[key]) is not bool:
            raise Fault(f"{key} 必须为布尔值")
    c["hostname"] = engine_text(c["hostname"], "服务器名称", 80, False)
    c["game_password"] = engine_text(c["game_password"], "游戏密码", 64)
    if not isinstance(c["map"], str) or not re.fullmatch(r"[A-Za-z0-9_/-]{1,80}", c["map"]) or ".." in c["map"]:
        raise Fault("地图名称无效")
    username = c["steam_username"]
    if not isinstance(username, str) or (username and not re.fullmatch(r"[A-Za-z0-9_]{2,64}", username)):
        raise Fault("Steam 登录名须为 2～64 个字母、数字或下划线；不是昵称/电子邮箱")
    return c


def credentials(raw: dict) -> dict:
    username = raw.get("username", "")
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{2,64}", username):
        raise Fault("请填写 Steam 登录账号名（不是昵称或邮箱）")
    password = plain(raw.get("password", ""), "Steam 密码", 256)
    guard = plain(raw.get("guard", ""), "Steam Guard", 12)
    if guard and not re.fullmatch(r"[A-Za-z0-9]{4,12}", guard):
        raise Fault("Steam Guard 格式无效")
    return {"username": username, "password": password, "guard": guard}


def build_command(paths: Paths, config: dict, bot: dict | None = None, addon: dict | None = None) -> tuple[list[str], dict[str, str]]:
    c = validate_config(config)
    wrapper = paths.game / "game/dota.sh"
    root_wrapper = paths.game / "dota.sh"
    binary = paths.game / "game/bin/linuxsteamrt64/dota2"
    # Current App 570's dota.sh refuses to run outside Valve's sniper container.
    # The dedicated binary is independently usable with the shipped libraries, and
    # is preferred after a live launch check on the target Ubuntu 24.04 LXC.
    if binary.is_file() and os.access(binary, os.X_OK):
        cmd = [str(binary)]
    elif wrapper.is_file():
        cmd = ["/bin/bash", str(wrapper)]
    elif root_wrapper.is_file():
        cmd = ["/bin/bash", str(root_wrapper)]
    else:
        raise Fault("没有找到 Valve 的 dota.sh / Linux dota2 可执行文件。请先安装或校验。", 409)
    cmd += ["-dedicated", "-console", "-allow_no_lobby_connect", "-game", "dota", "-port", str(c["port"])]
    if c["insecure"]:
        cmd.append("-insecure")
    cmd += ["+sv_lan", "1", "+hostname", c["hostname"], "+sv_cheats", "1" if c["cheats"] else "0"]
    if c["game_password"]:
        cmd += ["+sv_password", c["game_password"]]
    if c["game_mode"] and not addon:
        cmd += ["+dota_force_gamemode", str(c["game_mode"])]
    if bot:
        # The normalized version is deployed in the local developer bots path.
        # 0 selects the local/default script path, not a remote Workshop lookup.
        # Dedicated runtime behavior remains a target-host acceptance item.
        difficulty = bot.get("difficulty", 2)
        if type(difficulty) is not int or not 0 <= difficulty <= 3:
            raise Fault("机器人难度必须在 0～3 之间")
        cmd += ["+dota_bot_practice_script", "0", "+dota_bot_practice_difficulty", str(difficulty),
                "+dota_bot_set_difficulty", str(difficulty)]
        if not addon:
            cmd += ["+dota_wait_for_players_to_load", "1", "+dota_wait_for_players_to_load_timeout", "180"]
        # Never fill ten slots at process startup before human players connect.
    if addon:
        if addon.get("name") != "lan_dota" or addon.get("launch_method") not in {"custom_command", "addon_flag"}:
            raise Fault("非法附加模式启动配置")
        # Mutually exclusive candidates, never launch a normal dota map first.
        if addon["launch_method"] == "custom_command":
            cmd += ["+dota_launch_custom_game", "lan_dota", "dota"]
        else:
            cmd += ["+dota_force_gamemode", "15", "+map", "dota", "gamemode", "15", "customgamemode", "lan_dota"]
    else:
        cmd += ["+map", c["map"]]
    env = os.environ.copy()
    env.update(HOME=str(paths.state), USER="steam", LOGNAME="steam", LANG="C.UTF-8",
               SteamAppId="570", SteamGameId="570", TERM="xterm")
    env["LD_LIBRARY_PATH"] = ":".join(str(p) for p in (
        paths.game / "game/bin/linuxsteamrt64", paths.game / "game/dota/bin/linuxsteamrt64",
        paths.steam / "linux64"))
    return cmd, env


def installed(paths: Paths) -> bool:
    return any((paths.game / p).is_file() for p in ("game/dota.sh", "dota.sh", "game/bin/linuxsteamrt64/dota2"))


def manifest(paths: Paths) -> dict:
    for p in (paths.game / "steamapps/appmanifest_570.acf", paths.steam / "steamapps/appmanifest_570.acf"):
        if p.is_file():
            text = p.read_text(errors="replace")[:1000000]
            result = {k: (re.search(r'"' + k + r'"\s+"([^"\n]*)"', text) or [None, ""])[1]
                      for k in ("buildid", "StateFlags", "LastUpdated", "SizeOnDisk")}
            result["source"] = str(p)
            return result
    return {}


def tail(path: Path, limit: int = 48000) -> str:
    if not path.is_file():
        return "暂无日志。"
    with path.open("rb") as f:
        f.seek(0, 2)
        end = f.tell()
        f.seek(max(0, end - limit))
        data = f.read(limit)
    return data.decode("utf-8", errors="replace")


def new_id(prefix: str = "job") -> str:
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{secrets.token_hex(4)}"
