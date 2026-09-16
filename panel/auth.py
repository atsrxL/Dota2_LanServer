"""Single administrator, PBKDF2 hashes, server-side sessions and bounded limits."""
from __future__ import annotations
import hashlib
import hmac
import secrets
import threading
import time
from http.cookies import SimpleCookie
from pathlib import Path
from .common import Fault, read_json

ITERATIONS = 600000


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        algo, rounds, salt, digest = encoded.split("$")
        if algo != "pbkdf2_sha256" or not 100000 <= int(rounds) <= 2000000:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False

class Auth:
    def __init__(self, auth_file: Path, idle_seconds: int = 1800, max_seconds: int = 28800):
        self.auth_file = auth_file
        self.idle_seconds, self.max_seconds = idle_seconds, max_seconds
        self.sessions: dict[str, dict] = {}
        self.attempts: dict[str, list[float]] = {}
        self.lock = threading.RLock()

    def _prune(self, ts: float) -> None:
        self.sessions = {k: v for k, v in self.sessions.items()
                         if ts - v["last"] < self.idle_seconds and ts - v["created"] < self.max_seconds}
        self.attempts = {k: [x for x in v if ts - x < 900] for k, v in self.attempts.items() if v and ts - v[-1] < 900}

    def login(self, username: str, password: str, ip: str) -> tuple[str, dict]:
        with self.lock:
            ts = time.time()
            self._prune(ts)
            attempts = self.attempts.setdefault(ip, [])
            if len(attempts) >= 8:
                raise Fault("登录失败次数过多，请在 15 分钟后重试。", 429)
            if len(self.attempts) > 2048:
                raise Fault("登录请求过多", 429)
            attempts.append(ts)
        saved = read_json(self.auth_file)
        if not saved or not isinstance(saved, dict):
            raise Fault("管理员账号未初始化，请运行环境安装脚本。", 503)
        valid = password_matches(password, saved.get("password_hash", ""))
        if not hmac.compare_digest(username.encode("utf-8"), saved.get("username", "admin").encode("utf-8")) or not valid:
            raise Fault("账号或密码不正确", 401)
        with self.lock:
            self.attempts.pop(ip, None)
            if len(self.sessions) >= 64:
                oldest = min(self.sessions, key=lambda x: self.sessions[x]["created"])
                self.sessions.pop(oldest, None)
            token = secrets.token_urlsafe(32)
            state = {"username": username, "csrf": secrets.token_urlsafe(32), "created": ts, "last": ts}
            self.sessions[token] = state
            return token, dict(state)

    def create_session(self, username: str = "lan-admin") -> tuple[str, dict]:
        """Create a bounded session without checking a password for trusted-LAN mode."""
        with self.lock:
            ts = time.time()
            self._prune(ts)
            if len(self.sessions) >= 64:
                oldest = min(self.sessions, key=lambda x: self.sessions[x]["created"])
                self.sessions.pop(oldest, None)
            token = secrets.token_urlsafe(32)
            state = {"username": username, "csrf": secrets.token_urlsafe(32), "created": ts, "last": ts}
            self.sessions[token] = state
            return token, dict(state)

    @staticmethod
    def token(cookie: str) -> str:
        try:
            c = SimpleCookie()
            c.load(cookie)
            return c["dota_session"].value if "dota_session" in c else ""
        except Exception:
            return ""

    def session(self, cookie: str) -> dict | None:
        token = self.token(cookie)
        with self.lock:
            ts = time.time()
            self._prune(ts)
            result = self.sessions.get(token)
            if result:
                result["last"] = ts
                return dict(result)
            return None

    def logout(self, cookie: str) -> None:
        with self.lock:
            self.sessions.pop(self.token(cookie), None)

    @staticmethod
    def check_csrf(state: dict, supplied: str) -> None:
        if not isinstance(supplied, str) or not hmac.compare_digest(state["csrf"].encode("utf-8"), supplied.encode("utf-8")):
            raise Fault("CSRF 校验失败，请刷新网页重新登录。", 403)
