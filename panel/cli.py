"""Recovery CLI: credentials are read with getpass, never command-line flags."""
from __future__ import annotations
import argparse
import getpass
import json
from .agent import rpc
from .common import ACTIONS, Fault

def main():
    p = argparse.ArgumentParser(description="Dota 2 LAN 控制/恢复工具（LXC 内执行）")
    p.add_argument("command", choices=sorted(ACTIONS | {"addon", "addon_report", "bots", "metrics", "status", "jobs", "logs", "config", "diagnostics", "input", "cancel"}))
    p.add_argument("--name", default="server", help="日志名或备份名")
    p.add_argument("--username", default="", help="Steam 账号名；不接收密码参数")
    p.add_argument("--job-id", default="")
    p.add_argument("--item-id", default="", help="Workshop 数字 ID")
    p.add_argument("--version", default="", help="脚本完整 SHA-256；选择时可省略以使用最新安装版")
    p.add_argument("--select-after", action="store_true", help="下载成功后设为下一局")
    p.add_argument("--difficulty", type=int, default=2, choices=range(4))
    p.add_argument("--no-entry-probe", action="store_true", help="不向部署副本添加入口日志探针")
    p.add_argument("--stop-server", action="store_true")
    p.add_argument("--restart-after", action="store_true")
    args = p.parse_args()
    try:
        if args.command in ACTIONS:
            data = {"action": args.command, "stop_server": args.stop_server, "restart_after": args.restart_after}
            if args.command in {"login", "install", "update", "validate", "bot_download"}:
                data.update(username=args.username or input("Steam 登录账号名：").strip(),
                            password=getpass.getpass("Steam 密码（留空尝试缓存登录）："),
                            guard=getpass.getpass("已有 Steam Guard 验证码（可留空）："))
            if args.command.startswith("bot_"):
                data.update(item_id=args.item_id, version=args.version, select_after=args.select_after,
                            difficulty=args.difficulty, entry_probe=not args.no_entry_probe)
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
