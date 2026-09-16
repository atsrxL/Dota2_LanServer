"""Small WSGI control panel. Production listener is Waitress on loopback only."""
from __future__ import annotations
import argparse
import io
import json
import mimetypes
import os
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .agent import rpc
from .auth import Auth
from .common import VERSION, Fault, Paths, plain, read_json

STATIC = Path(__file__).parent / "static"
MAX_BODY = 16384
CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"

class WebApp:
    def __init__(self, auth_file: Path, settings_file: Path | None = None, rpc_call=None, secure: bool = True, no_auth: bool = False):
        self.auth = Auth(auth_file)
        self.settings_file = settings_file
        self.rpc = rpc_call or rpc
        self.secure = secure
        self.no_auth = no_auth

    def settings(self) -> dict:
        return read_json(self.settings_file, {}) if self.settings_file else {}

    def __call__(self, env: dict, start_response):
        extra_headers: list[tuple[str, str]] = []
        status, content_type, body = 200, "application/json; charset=utf-8", b""
        try:
            host = env.get("HTTP_HOST", "")
            if not host or any(c in host for c in "\r\n/\\@"):
                raise Fault("非法 Host", 400)
            allowed = self.settings().get("allowed_hosts", [])
            hostname = host.split(":", 1)[0].lower()
            if allowed and hostname not in [str(x).lower() for x in allowed]:
                raise Fault("访问域名/IP 未列入 allowed_hosts；通过配置中已有地址访问。", 403)
            method = env.get("REQUEST_METHOD", "GET").upper()
            path = env.get("PATH_INFO", "/")
            if len(path) > 256:
                raise Fault("请求路径过长", 414)
            if method not in {"GET", "POST"}:
                raise Fault("只支持 GET 和 POST", 405)
            cookie = env.get("HTTP_COOKIE", "")
            state = self.auth.session(cookie)
            # Only fixed assets, no arbitrary filesystem serving or directory listing.
            assets = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css", "/help": "help.html"}
            if method == "GET" and path in assets:
                name = assets[path]
                content_type = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}[Path(name).suffix]
                body = (STATIC / name).read_bytes()
            elif method == "GET" and path == "/api/session":
                if self.no_auth and not state:
                    token, state = self.auth.create_session()
                    flags = "; Secure" if self.secure else ""
                    extra_headers.append(("Set-Cookie", f"dota_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{flags}"))
                body = self._json({"authenticated": bool(state), "csrf": state["csrf"] if state else None,
                                   "username": state["username"] if state else None, "version": VERSION,
                                   "no_auth": self.no_auth})
            elif method == "POST":
                self._check_origin(env)
                data = self._body(env)
                if path == "/api/login":
                    if self.no_auth:
                        username = "lan-admin"
                        token, new_state = self.auth.create_session(username)
                    else:
                        username = plain(data.get("username", ""), "用户名", 64, False)
                        password = plain(data.get("password", ""), "密码", 256, False)
                        # Nginx overwrites X-Real-IP; backend listens only on loopback.
                        ip = env.get("HTTP_X_REAL_IP") or env.get("REMOTE_ADDR", "unknown")
                        token, new_state = self.auth.login(username, password, ip)
                    self.auth.logout(cookie)  # rotate any previous session
                    flags = "; Secure" if self.secure else ""
                    extra_headers.append(("Set-Cookie", f"dota_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{flags}"))
                    body = self._json({"ok": True, "csrf": new_state["csrf"], "username": username})
                else:
                    if not state:
                        raise Fault("请先登录", 401)
                    self.auth.check_csrf(state, env.get("HTTP_X_CSRF_TOKEN", ""))
                    if path == "/api/logout":
                        self.auth.logout(cookie)
                        flags = "; Secure" if self.secure else ""
                        extra_headers.append(("Set-Cookie", f"dota_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0{flags}"))
                        body = self._json({"ok": True})
                    else:
                        routes = {"/api/actions": "submit", "/api/config": "save_config", "/api/input": "input",
                                  "/api/cancel": "cancel", "/api/console": "console"}
                        if path not in routes:
                            raise Fault("接口不存在", 404)
                        result = self.rpc(routes[path], data)
                        status = 202 if path == "/api/actions" else 200
                        body = self._json(result)
            else:
                if not state:
                    raise Fault("请先登录", 401)
                q = parse_qs(env.get("QUERY_STRING", ""), max_num_fields=10)
                routes = {"/api/status": "status", "/api/config": "config", "/api/jobs": "jobs", "/api/backups": "backups"}
                if path in routes:
                    body = self._json(self.rpc(routes[path]))
                elif path == "/api/logs":
                    body = self._json(self.rpc("logs", {"name": q.get("name", ["server"])[0]}))
                elif path == "/api/diagnostics":
                    body = self._json(self.rpc("diagnostics"))
                    extra_headers.append(("Content-Disposition", 'attachment; filename="dota2-diagnostics.json"'))
                elif path == "/api/backup":
                    body = self._json(self.rpc("backup_read", {"name": q.get("name", [""])[0]}))
                    extra_headers.append(("Content-Disposition", 'attachment; filename="dota2-config-backup.json"'))
                else:
                    raise Fault("接口不存在", 404)
        except Fault as exc:
            status, body = exc.code, self._json({"error": str(exc)})
        except (ValueError, UnicodeError, TypeError):
            status, body = 400, self._json({"error": "请求格式不正确"})
        except Exception as exc:
            # Request bodies and exception buffers never go to access logs.
            status, body = 500, self._json({"error": f"面板内部错误（{type(exc).__name__}）"})
        headers = [("Content-Type", content_type), ("Content-Length", str(len(body))),
                   ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                   ("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"),
                   ("Content-Security-Policy", CSP)] + extra_headers
        start_response(f"{status} {HTTPStatus(status).phrase}", headers)
        return [body]

    @staticmethod
    def _json(value) -> bytes:
        return json.dumps(value, ensure_ascii=False).encode("utf-8")

    def _check_origin(self, env):
        scheme = "https" if self.secure else "http"
        origin = env.get("HTTP_ORIGIN", "")
        expected = scheme + "://" + env.get("HTTP_HOST", "")
        if origin != expected:
            raise Fault("请求来源不匹配；仅接受同源网页操作。", 403)

    @staticmethod
    def _body(env):
        if env.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json":
            raise Fault("只接受 application/json 请求", 415)
        try:
            size = int(env.get("CONTENT_LENGTH", "0"))
        except ValueError:
            raise Fault("Content-Length 无效") from None
        if not 0 < size <= MAX_BODY:
            raise Fault("请求体为空或超过 16 KiB", 413)
        data = json.loads(env["wsgi.input"].read(size))
        if not isinstance(data, dict):
            raise Fault("请求体必须为 JSON 对象")
        return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dev", action="store_true", help="仅本机开发演示使用，禁用 TLS Cookie。绝不用于生产。")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--auth-file", type=Path, default=Path("/etc/dota-panel/auth.json"))
    p.add_argument("--settings-file", type=Path, default=Path("/etc/dota-panel/web.json"))
    p.add_argument("--http", action="store_true", help="HTTP reverse-proxy mode; cookies are not marked Secure.")
    p.add_argument("--no-auth", action="store_true", help="Trusted-LAN mode: issue an admin session without password validation.")
    args = p.parse_args()
    app = WebApp(args.auth_file, args.settings_file, secure=not (args.dev or args.http), no_auth=args.no_auth)
    if args.dev:
        from wsgiref.simple_server import make_server
        print(f"DEV ONLY: http://127.0.0.1:{args.port}", flush=True)
        make_server("127.0.0.1", args.port, app).serve_forever()
    else:
        from waitress import serve
        serve(app, host="127.0.0.1", port=args.port, threads=6, connection_limit=64,
              channel_timeout=30, max_request_body_size=MAX_BODY, clear_untrusted_proxy_headers=False)

if __name__ == "__main__":
    main()
