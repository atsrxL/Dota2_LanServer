"""Recovery CLI: credentials are read with getpass, never command-line flags."""
from __future__ import annotations
import argparse
import getpass
import json
import subprocess
from pathlib import Path
from .agent import rpc
from .auth import password_hash
from .common import ACTIONS, Fault, atomic_json

def main():
    p = argparse.ArgumentParser(description="Dota 2 LAN 控制/恢复工具（LXC 内执行）")
    p.add_argument("command", choices=sorted(ACTIONS | {"status", "jobs", "logs", "config", "diagnostics", "input", "cancel", "reset-password"}))
    p.add_argument("--name", default="server", help="日志名或备份名")
    p.add_argument("--username", default="", help="Steam 账号名；不接收密码参数")
    p.add_argument("--job-id", default="")
    p.add_argument("--stop-server", action="store_true")
    p.add_argument("--restart-after", action="store_true")
    args = p.parse_args()
    try:
        if args.command == "reset-password":
            import os
            if os.geteuid() != 0:
                raise Fault("重置面板密码须以 LXC root 执行")
            pw = getpass.getpass("新面板密码（至少 14 字符）：")
            if len(pw) < 14 or pw != getpass.getpass("再次输入："):
                raise Fault("密码太短或两次输入不相同")
            path = Path("/etc/dota-panel/auth.json")
            st = path.stat()
            atomic_json(path, {"username": "admin", "password_hash": password_hash(pw)}, 0o640)
            os.chown(path, st.st_uid, st.st_gid)
            subprocess.run(["systemctl", "restart", "dota-panel.service"], check=True)
            print("面板密码已更新，旧会话已失效。/root 初始密码文件不再代表当前密码。")
            return
        if args.command in ACTIONS:
            data = {"action": args.command, "stop_server": args.stop_server, "restart_after": args.restart_after}
            if args.command in {"login", "install", "update", "validate"}:
                data.update(username=args.username or input("Steam 登录账号名：").strip(),
                            password=getpass.getpass("Steam 密码（留空尝试缓存登录）："),
                            guard=getpass.getpass("已有 Steam Guard 验证码（可留空）："))
            if args.command == "restore":
                data["backup"] = args.name
            result = rpc("submit", data)
        elif args.command == "input":
            result = rpc("input", {"job_id": args.job_id, "value": getpass.getpass("密码或验证码：")})
        elif args.command == "cancel":
            result = rpc("cancel", {"job_id": args.job_id})
        elif args.command == "logs":
            result = rpc("logs", {"name": args.name})
        else:
            result = rpc(args.command)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Fault as exc:
        raise SystemExit(str(exc)) from None

if __name__ == "__main__":
    main()
