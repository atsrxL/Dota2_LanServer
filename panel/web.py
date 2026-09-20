"""Small WSGI control panel. Production listener is Waitress on loopback only."""
from __future__ import annotations
import argparse
import hmac
import secrets
import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .agent import rpc
from .common import VERSION, Fault, read_json
from . import client_downloads

STATIC = Path(__file__).parent / "static"
MAX_BODY = 16384
CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"

class WebApp:
    def __init__(self, settings_file: Path | None = None, rpc_call=None):
        self.settings_file = settings_file
        self.rpc = rpc_call or rpc
        # Anti-CSRF token, NOT a password/session. All allowed LAN users get it
        # automatically. Never use this token as an authentication boundary.
        self.csrf = secrets.token_urlsafe(32)

    def settings(self) -> dict:
        return read_json(self.settings_file, {}) if self.settings_file else {}

    def __call__(self, env: dict, start_response):
        extra_headers: list[tuple[str, str]] = []
        status, content_type, body = 200, "application/json; charset=utf-8", b""
        try:
            host = env.get("HTTP_HOST", "")
            hostname = self._host(host)
            allowed = self.settings().get("allowed_hosts", [])
            if allowed and hostname not in [str(x).lower() for x in allowed]:
                raise Fault("访问域名/IP 未列入 allowed_hosts；通过配置中已有地址访问。", 403)
            method = env.get("REQUEST_METHOD", "GET").upper()
            path = env.get("PATH_INFO", "/")
            if len(path) > 256:
                raise Fault("请求路径过长", 414)
            if method not in {"GET", "POST"}:
                raise Fault("只支持 GET 和 POST", 405)
            # Only fixed assets, no arbitrary filesystem serving or directory listing.
            assets = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css", "/help": "help.html", "/metrics.js": "metrics.js", "/addon.js": "addon.js"}
            if method == "GET" and path in assets:
                name = assets[path]
                content_type = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}[Path(name).suffix]
                body = (STATIC / name).read_bytes()
            elif method == "GET" and path == "/api/session":
                body = self._json({"auth_required": False, "mode": "lan-no-auth",
                                   "csrf": self.csrf, "transport": "http", "version": VERSION})
            elif method == "POST":
                routes = {"/api/actions": "submit", "/api/config": "save_config", "/api/input": "input",
                          "/api/cancel": "cancel", "/api/console": "console", "/api/addon": "save_addon"}
                if path not in routes:
                    raise Fault("接口不存在", 404)
                self._check_origin(env)
                supplied = env.get("HTTP_X_CSRF_TOKEN", "")
                if not isinstance(supplied, str) or not hmac.compare_digest(
                        self.csrf.encode(), supplied.encode("utf-8")):
                    raise Fault("操作令牌已失效；刷新页面后重试。本面板不需要登录。", 403)
                result = self.rpc(routes[path], self._body(env))
                status = 202 if path == "/api/actions" else 200
                body = self._json(result)
            else:
                q = parse_qs(env.get("QUERY_STRING", ""), max_num_fields=10)
                routes = {"/api/addon": "addon", "/api/bots": "bots", "/api/metrics": "metrics", "/api/status": "status", "/api/config": "config", "/api/jobs": "jobs", "/api/backups": "backups"}
                if path in routes:
                    body = self._json(self.rpc(routes[path]))
                elif path == "/api/client-resources":
                    body = self._json(client_downloads.metadata())
                elif path == "/api/client-download":
                    body, filename = client_downloads.download(q.get('kind', ['exe'])[0])
                    content_type = 'application/octet-stream'
                    extra_headers.append(('Content-Disposition', 'attachment; filename="' + filename + '"'))
                elif path == "/api/logs":
                    body = self._json(self.rpc("logs", {"name": q.get("name", ["server"])[0]}))
                elif path == "/api/addon/report":
                    body = self._json(self.rpc("addon_report"))
                    extra_headers.append(("Content-Disposition", 'attachment; filename="lan-addon-report.json"'))
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

    @staticmethod
    def _host(host: str) -> str:
        if not host or any(c.isspace() or ord(c) < 32 or c in "/\\@?#%" for c in host):
            raise Fault("非法 Host", 400)
        try:
            parsed = urlsplit("http://" + host)
            if not parsed.hostname or parsed.username or parsed.password:
                raise ValueError()
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError()
            return parsed.hostname.lower()
        except ValueError:
            raise Fault("非法 Host", 400) from None

    @staticmethod
    def _check_origin(env):
        origin = env.get("HTTP_ORIGIN", "")
        if origin != "http://" + env.get("HTTP_HOST", ""):
            raise Fault("请求来源不匹配；仅接受同源 HTTP 网页操作。", 403)
        if env.get("HTTP_SEC_FETCH_SITE", "same-origin") not in {"same-origin", "none"}:
            raise Fault("拒绝跨站操作。", 403)

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
    p.add_argument("--dev", action="store_true", help="仅本机开发演示使用 WSGI 测试服务器；生产使用 Waitress。")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--settings-file", type=Path, default=Path("/etc/dota-panel/web.json"))
    args = p.parse_args()
    if not args.dev:
        settings = read_json(args.settings_file, {})
        if not settings.get("allowed_hosts"):
            p.error("生产环境必须配置 allowed_hosts；请先执行 bootstrap。")
    app = WebApp(args.settings_file)
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
