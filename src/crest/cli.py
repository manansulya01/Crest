"""Crest command line interface."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .agent_runtime import CrestRuntime
from .config import default_yaml
from .recovery import RecoveryProgram


def _runtime(args) -> CrestRuntime:
    return CrestRuntime.from_config(args.config)


def _parse_kvs(pairs: list[str] | None) -> dict:
    out = {}
    for p in pairs or []:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k] = v
        else:
            raise SystemExit(f"invalid --arg {p!r}; expected key=value")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="crest", description="Crest runtime: capability admission control plane")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", default="crest.yaml", help="path to crest.yaml")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("init", help="initialize crest.yaml and workspace state")
    s.add_argument("--root", default=".")

    sub.add_parser("status")
    sub.add_parser("config")

    caps = sub.add_parser("capabilities")
    caps_sub = caps.add_subparsers(dest="caps_command")
    caps_sub.add_parser("list")
    show = caps_sub.add_parser("show")
    show.add_argument("capability_id")
    revoke = caps_sub.add_parser("revoke")
    revoke.add_argument("capability_id")
    revoke.add_argument("--reason", default="manual")

    rcp = sub.add_parser("receipts")
    rcp_sub = rcp.add_subparsers(dest="receipts_command")
    rcp_sub.add_parser("list")
    rshow = rcp_sub.add_parser("show")
    rshow.add_argument("receipt_id")

    au = sub.add_parser("audit")
    au.add_argument("--limit", type=int, default=50)

    pol = sub.add_parser("policy")
    pol_sub = pol.add_subparsers(dest="policy_command")
    pc = pol_sub.add_parser("check")
    pc.add_argument("--tool", required=True)
    pc.add_argument("--operation", required=True)
    pc.add_argument("--arg", action="append", default=[])

    ver = sub.add_parser("verify", help="run independent verification and admit a capability")
    ver.add_argument("--action", required=True)
    ver.add_argument("--recovery", required=True, help="registered recovery kind")
    ver.add_argument("--scope", default="*")
    ver.add_argument("--target", default="a.txt")
    ver.add_argument("--trials", type=int, default=8)
    ver.add_argument("--seed", type=int, default=7)

    ex = sub.add_parser("exec")
    ex.add_argument("tool")
    ex.add_argument("operation")
    ex.add_argument("--arg", action="append", default=[])

    args = p.parse_args(argv)
    if args.command is None:
        p.print_help()
        return 0

    if args.command == "init":
        cfg_path = Path(args.config)
        root = Path(args.root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if not cfg_path.exists():
            cfg_path.write_text(default_yaml(root), encoding="utf-8")
        (root / ".crest").mkdir(exist_ok=True)
        print(f"initialized crest config at {cfg_path} (root={root})")
        return 0

    rt = _runtime(args)
    try:
        if args.command == "status":
            print(json.dumps(rt.status(), indent=2))
            return 0
        if args.command == "config":
            import dataclasses

            print(json.dumps(dataclasses.asdict(rt.config), indent=2, default=str))
            return 0
        if args.command == "capabilities":
            if args.caps_command in (None, "list"):
                for row in rt.list_capabilities():
                    print(f"{row['capability_id']}  state={row['state']}  receipt={row['receipt_id']}")
                return 0
            if args.caps_command == "show":
                row = rt.get_capability(args.capability_id)
                if row is None:
                    print(f"no such capability: {args.capability_id}")
                    return 4
                print(json.dumps(row, indent=2))
                return 0
            if args.caps_command == "revoke":
                try:
                    print(json.dumps(rt.revoke(args.capability_id, args.reason), indent=2))
                    return 0
                except KeyError:
                    print(f"no such capability: {args.capability_id}")
                    return 4
        if args.command == "receipts":
            if args.receipts_command in (None, "list"):
                for r in rt.list_receipts():
                    print(f"{r['receipt_id']}  {r['action_class']}  scope={r['scope']}  status={r['status']}  expires={r['expires_at']}")
                return 0
            if args.receipts_command == "show":
                payload = rt.get_receipt(args.receipt_id)
                if payload is None:
                    print(f"no such receipt: {args.receipt_id}")
                    return 4
                print(json.dumps(payload, indent=2))
                return 0
        if args.command == "audit":
            for e in rt.audit(args.limit):
                print(f"{e['timestamp']}  {e['decision']:<22} {e['tool'] or '-':10} {e['operation'] or '-':16} {e['reason'] or ''}")
            return 0
        if args.command == "policy":
            if args.policy_command == "check":
                d = rt.check(agent_id="cli-policy-check", tool=args.tool, operation=args.operation, arguments=_parse_kvs(args.arg))
                print(json.dumps(d.to_audit(), indent=2))
                return 0 if d.allowed else 3
        if args.command == "verify":
            out = rt.verify_and_admit(
                action_class=args.action, scope=args.scope, recovery=RecoveryProgram(kind=args.recovery),
                target=args.target, trials=args.trials, seed=args.seed,
            )
            print(json.dumps(out, indent=2))
            return 0 if out.get("admitted") else 3
        if args.command == "exec":
            args_map = _parse_kvs(args.arg)
            result = rt.execute(agent_id="cli", tool=args.tool, operation=args.operation, arguments=args_map)
            print(json.dumps({"ok": result.ok, "reason": result.reason, "target": result.target, "exposure_after": result.exposure_after, "output": result.output}, indent=2))
            return 0 if result.ok else 3
        p.print_help()
        return 0
    finally:
        rt.close()


if __name__ == "__main__":
    sys.exit(main())
