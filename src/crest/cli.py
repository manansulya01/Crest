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
    ex.add_argument("--dry-run", action="store_true")

    ev = sub.add_parser("evidence")
    ev_sub = ev.add_subparsers(dest="evidence_command")
    ev_sub.add_parser("list")

    sub.add_parser("doctor")

    bench = sub.add_parser("benchmark")
    bench.add_argument("which", nargs="?", default="all", choices=["all", "admission", "security", "generalization", "drift"])

    sub.add_parser("report")

    exp = sub.add_parser("experiment", help="run a research experiment")
    exp.add_argument("name", choices=["cross-distribution", "ablations", "exposure-sweep", "confidence", "drift", "tables", "conclusion", "holdout"])

    research = sub.add_parser("research", help="reproducible research validation")
    research_sub = research.add_subparsers(dest="research_command")
    rep = research_sub.add_parser("reproduce", help="run the lightweight complete research validation (--full for heavy experiments)")
    rep.add_argument("--full", action="store_true")

    ver = sub.add_parser("verify-generalized", help="run cross-fixture holdout verification and admit if evidence class suffices")
    ver.add_argument("--action", required=True)
    ver.add_argument("--recovery", required=True)
    ver.add_argument("--scope", default="*")
    ver.add_argument("--families", default="filesystem.single_file", help="comma-separated")
    ver.add_argument("--seed", type=int, default=0)

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

    if args.command == "research" and args.research_command == "reproduce":
        import importlib

        summary: dict[str, Any] = {}
        conclusion = importlib.import_module("experiments.generalization.conclusion")
        out = conclusion.evaluate()
        summary["conclusion"] = out.get("verdict")
        tables = importlib.import_module("experiments.generalization.tables")
        summary["tables"] = str(tables.write_all())
        if args.full:
            for mod_name, fn in (("experiments.generalization.cross_distribution", "run_grid"),
                                 ("experiments.generalization.ablations", "run_all"),
                                 ("experiments.generalization.exposure_sweep", "run_all"),
                                 ("experiments.generalization.confidence_sensitivity", "run_all"),
                                 ("experiments.generalization.drift_experiment", "run")):
                try:
                    getattr(importlib.import_module(mod_name), fn)()
                    summary[mod_name] = "ok"
                except Exception as exc:
                    summary[mod_name] = f"failed: {exc}"
        # artifact manifest metadata
        import subprocess

        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            commit = "unknown"
        summary["git_commit"] = commit
        import sys, platform, crest

        summary["python"] = sys.version.split()[0]
        summary["crest_version"] = crest.__version__
        summary["os"] = f"{platform.system()} {platform.release()}"
        print(json.dumps(summary, indent=2))
        return 0 if out.get("verdict") in ("SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED", "INCONCLUSIVE") else 3

    if args.command == "experiment" and args.name in ("conclusion", "tables"):
        # These only read artifacts; no workspace config required.
        import importlib

        module_map = {
            "tables": ("experiments.generalization.tables", "write_all"),
            "conclusion": ("experiments.generalization.conclusion", "evaluate"),
        }
        mod_name, fn_name = module_map[args.name]
        mod = importlib.import_module(mod_name)
        if args.name == "tables":
            print(f"wrote {getattr(mod, fn_name)()}")
            return 0
        out = getattr(mod, fn_name)()
        print(json.dumps(out, indent=2))
        from pathlib import Path as _P

        results_dir = _P(__file__).resolve().parents[2] / "experiments" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "conclusion.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
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
            if args.dry_run:
                d = rt.check(agent_id="cli", tool=args.tool, operation=args.operation, arguments=args_map)
                print(json.dumps({"dry_run": True, **d.to_audit()}, indent=2))
                return 0 if d.allowed else 3
            result = rt.execute(agent_id="cli", tool=args.tool, operation=args.operation, arguments=args_map)
            print(json.dumps({"ok": result.ok, "reason": result.reason, "target": result.target, "exposure_after": result.exposure_after, "output": result.output}, indent=2))
            return 0 if result.ok else 3
        if args.command == "evidence" and args.evidence_command in (None, "list"):
            for r in rt.list_receipts():
                payload = rt.get_receipt(r["receipt_id"]) or {}
                gen = payload.get("generalization")
                suffix = f"  gen={gen.get('classification') if gen else 'fixture-only'}"
                print(f"{r['receipt_id']}  {r['action_class']}  status={r['status']}{suffix}")
            return 0
        if args.command == "doctor":
            from .doctor import doctor as run_doctor

            return run_doctor(rt)
        if args.command == "benchmark":
            from .benchmarks import run as run_bench

            print(json.dumps(run_bench(args.which), indent=2))
            return 0
        if args.command == "report":
            payload = rt.status()
            receipts = rt.list_receipts()
            print(json.dumps({
                "status": payload,
                "receipts": receipts,
                "capabilities": rt.list_capabilities(),
                "audit_events": len(rt.audit(500)),
            }, indent=2))
            return 0
        if args.command == "verify-generalized":
            out = rt.verify_generalized(
                action_class=args.action, scope=args.scope, recovery=RecoveryProgram(kind=args.recovery),
                family_ids=tuple(s.strip() for s in args.families.split(",") if s.strip()), seed=args.seed,
            )
            print(json.dumps(out, indent=2))
            return 0 if out.get("admitted") else 3
        if args.command == "experiment":
            import importlib

            module_map = {
                "cross-distribution": ("experiments.generalization.cross_distribution", "run_grid"),
                "ablations": ("experiments.generalization.ablations", "run_all"),
                "exposure-sweep": ("experiments.generalization.exposure_sweep", "run_all"),
                "confidence": ("experiments.generalization.confidence_sensitivity", "run_all"),
                "drift": ("experiments.generalization.drift_experiment", "run"),
                "tables": ("experiments.generalization.tables", "write_all"),
                "conclusion": ("experiments.generalization.conclusion", "evaluate"),
                "holdout": ("experiments.holdout.run_holdout", "run"),
            }
            mod_name, fn_name = module_map[args.name]
            mod = importlib.import_module(mod_name)
            if args.name == "tables":
                print(f"wrote {getattr(mod, fn_name)()}")
                return 0
            if args.name == "conclusion":
                print(json.dumps(getattr(mod, fn_name)(), indent=2))
                return 0
            getattr(mod, fn_name)()
            return 0
        p.print_help()
        return 0
    finally:
        rt.close()


if __name__ == "__main__":
    sys.exit(main())
