
"""Crest command line interface."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .agent_runtime import CrestRuntime
from .config import default_yaml
from .recovery import RecoveryProgram


def _runtime(args) -> CrestRuntime:
    return CrestRuntime.from_config(args.config)


def _parse_kvs(pairs: list[str] | None) -> dict:
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(
                f"invalid --arg {pair!r}; expected key=value"
            )
        key, value = pair.split("=", 1)
        out[key] = value
    return out


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_metadata() -> dict[str, Any]:
    """Collect Git metadata without requiring Git to be available."""
    metadata: dict[str, Any] = {
        "git_commit": None,
        "working_tree_dirty": None,
    }

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        metadata["git_commit"] = commit.stdout.strip()

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        metadata["working_tree_dirty"] = bool(status.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass

    return metadata


def _package_versions() -> list[str] | None:
    """Return installed package versions, or None if collection fails."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=True,
        )
        return sorted(result.stdout.splitlines())
    except (OSError, subprocess.SubprocessError):
        return None


def _file_metadata(path_value: Any) -> dict[str, Any] | None:
    """Describe an output file when its path exists and is readable."""
    if not path_value:
        return None

    try:
        path = Path(path_value)
        if not path.is_file():
            return None

        return {
            "path": str(path),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    except (OSError, TypeError, ValueError):
        return None


# Fields that change on every evaluation but carry no scientific content.
# They are excluded from the reproducibility digest so that repeated runs
# over equivalent inputs and outputs produce a stable result digest.
_VOLATILE_CONCLUSION_FIELDS = ("generated_at",)


def _reproducible_result_payload(
    summary: dict[str, Any],
    artifacts: list[dict[str, Any]],
    failures: list[str],
) -> dict[str, Any]:
    """The subset of the manifest that defines run-to-run reproducibility.

    Volatile bookkeeping (evaluation timestamps) is normalized away; the
    digest is not included in its own input, to avoid circular hashing.
    """
    details = summary.get("conclusion_details")
    if isinstance(details, dict):
        details = {
            key: value
            for key, value in details.items()
            if key not in _VOLATILE_CONCLUSION_FIELDS
        }
    return {
        "conclusion": summary.get("conclusion"),
        "conclusion_details": details,
        "artifacts": artifacts,
        "full_experiments": summary.get("full_experiments"),
        "failures": failures,
    }


def _canonical_digest(payload: dict[str, Any]) -> str:
    """Stable SHA-256 over a canonically serialized payload."""
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _run_research_reproduction(args) -> int:
    """Run the research validation and write its reproducibility manifest."""
    import importlib

    started_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []
    artifacts: list[dict[str, Any]] = []

    summary: dict[str, Any] = {
        "manifest_version": 1,
        "experiment_name": "research-reproduce",
        "started_at": started_at,
        "finished_at": None,
        "full": args.full,
        "python": sys.version.split()[0],
        "crest_version": __version__,
        "os": platform.platform(),
        "experiment_seed": None,
        "experiment_version": None,
        "package_versions": _package_versions(),
        "artifacts": artifacts,
        "failures": failures,
    }

    summary.update(_git_metadata())

    # Hash the configuration actually selected by the CLI.
    config_path = Path(args.config)
    if config_path.is_file():
        try:
            summary["config"] = {
                "path": str(config_path),
                "sha256": _sha256_file(config_path),
            }
        except OSError as exc:
            summary["config"] = {
                "path": str(config_path),
                "error": str(exc),
            }
            failures.append(f"Could not hash configuration: {exc}")
    else:
        summary["config"] = {
            "path": str(config_path),
            "sha256": None,
            "status": "not_found",
        }

    try:
        conclusion = importlib.import_module(
            "experiments.generalization.conclusion"
        )
        outcome = conclusion.evaluate()
        summary["conclusion"] = outcome.get("verdict")
        summary["conclusion_details"] = outcome

        # Record the conclusion artifact when the experiment writes one.
        conclusion_artifact = _file_metadata(
            Path(__file__).resolve().parents[2]
            / "experiments"
            / "results"
            / "conclusion.json"
        )
        if conclusion_artifact:
            artifacts.append({
                "name": "conclusion",
                **conclusion_artifact,
            })

    except Exception as exc:
        summary["conclusion"] = None
        failures.append(
            f"Conclusion evaluation failed: {type(exc).__name__}: {exc}"
        )

    try:
        tables = importlib.import_module(
            "experiments.generalization.tables"
        )
        tables_path = tables.write_all()
        summary["tables"] = str(tables_path)

        table_artifact = _file_metadata(tables_path)
        if table_artifact:
            artifacts.append({
                "name": "tables",
                **table_artifact,
            })

    except Exception as exc:
        summary["tables"] = None
        failures.append(
            f"Table generation failed: {type(exc).__name__}: {exc}"
        )

    if args.full:
        full_experiments = (
            (
                "experiments.generalization.cross_distribution",
                "run_grid",
            ),
            (
                "experiments.generalization.ablations",
                "run_all",
            ),
            (
                "experiments.generalization.exposure_sweep",
                "run_all",
            ),
            (
                "experiments.generalization.confidence_sensitivity",
                "run_all",
            ),
            (
                "experiments.generalization.drift_experiment",
                "run",
            ),
        )

        summary["full_experiments"] = {}

        for module_name, function_name in full_experiments:
            try:
                module = importlib.import_module(module_name)
                getattr(module, function_name)()
                summary["full_experiments"][module_name] = "ok"
            except Exception as exc:
                message = (
                    f"{type(exc).__name__}: {exc}"
                )
                summary["full_experiments"][module_name] = {
                    "status": "failed",
                    "error": message,
                }
                failures.append(f"{module_name}: {message}")

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()

    # Hash the actual collected outcome and artifact metadata. Volatile
    # evaluation timestamps are normalized out so that repeated runs over
    # equivalent inputs produce a stable result digest; the digest itself is
    # excluded to avoid circular hashing.
    digest_payload = _reproducible_result_payload(
        summary, artifacts, failures
    )

    try:
        summary["result_digest"] = _canonical_digest(digest_payload)
    except (TypeError, ValueError) as exc:
        summary["result_digest"] = None
        failures.append(f"Could not calculate result digest: {exc}")

    manifest_dir = Path("reproduce_manifests")
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S_%fZ"
    )
    manifest_file = manifest_dir / f"reproduce_{timestamp}.json"

    try:
        manifest_dir.mkdir(parents=True, exist_ok=True)
        with manifest_file.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(summary, file, indent=2, ensure_ascii=False)
            file.write("\n")
    except OSError as exc:
        print(
            f"ERROR: could not write research manifest: {exc}",
            file=sys.stderr,
        )
        print(json.dumps(summary, indent=2, default=str))
        return 2

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print(f"\nResearch manifest: {manifest_file}")

    # Exit status reports execution success, not scientific support.
    return 2 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crest",
        description="Crest runtime: capability admission control plane",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--config",
        default="crest.yaml",
        help="path to crest.yaml",
    )

    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser(
        "init",
        help="initialize crest.yaml and workspace state",
    )
    init_parser.add_argument("--root", default=".")

    sub.add_parser("status")
    sub.add_parser("config")

    capabilities = sub.add_parser("capabilities")
    capabilities_sub = capabilities.add_subparsers(dest="caps_command")
    capabilities_sub.add_parser("list")

    capability_show = capabilities_sub.add_parser("show")
    capability_show.add_argument("capability_id")

    capability_revoke = capabilities_sub.add_parser("revoke")
    capability_revoke.add_argument("capability_id")
    capability_revoke.add_argument("--reason", default="manual")

    receipts = sub.add_parser("receipts")
    receipts_sub = receipts.add_subparsers(dest="receipts_command")
    receipts_sub.add_parser("list")

    receipt_show = receipts_sub.add_parser("show")
    receipt_show.add_argument("receipt_id")

    audit = sub.add_parser("audit")
    audit.add_argument("--limit", type=int, default=50)

    policy = sub.add_parser("policy")
    policy_sub = policy.add_subparsers(dest="policy_command")
    policy_check = policy_sub.add_parser("check")
    policy_check.add_argument("--tool", required=True)
    policy_check.add_argument("--operation", required=True)
    policy_check.add_argument("--arg", action="append", default=[])

    verify = sub.add_parser(
        "verify",
        help="run independent verification and admit a capability",
    )
    verify.add_argument("--action", required=True)
    verify.add_argument("--recovery", required=True)
    verify.add_argument("--scope", default="*")
    verify.add_argument("--target", default="a.txt")
    verify.add_argument("--trials", type=int, default=8)
    verify.add_argument("--seed", type=int, default=7)

    execute = sub.add_parser("exec")
    execute.add_argument("tool")
    execute.add_argument("operation")
    execute.add_argument("--arg", action="append", default=[])
    execute.add_argument("--dry-run", action="store_true")

    evidence = sub.add_parser("evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_command")
    evidence_sub.add_parser("list")

    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument(
        "--deep",
        action="store_true",
        help="run cross-table invariant audit",
    )

    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument(
        "which",
        nargs="?",
        default="all",
        choices=[
            "all",
            "admission",
            "security",
            "generalization",
            "drift",
        ],
    )

    sub.add_parser("report")

    experiment = sub.add_parser(
        "experiment",
        help="run a research experiment",
    )
    experiment.add_argument(
        "name",
        choices=[
            "cross-distribution",
            "ablations",
            "exposure-sweep",
            "confidence",
            "drift",
            "tables",
            "conclusion",
            "holdout",
        ],
    )

    research = sub.add_parser(
        "research",
        help="reproducible research validation",
    )
    research_sub = research.add_subparsers(dest="research_command")
    reproduce = research_sub.add_parser(
        "reproduce",
        help="run research validation and write a manifest",
    )
    reproduce.add_argument(
        "--full",
        action="store_true",
        help="run the heavier experiments too",
    )

    generalized = sub.add_parser(
        "verify-generalized",
        help="run cross-fixture holdout verification",
    )
    generalized.add_argument("--action", required=True)
    generalized.add_argument("--recovery", required=True)
    generalized.add_argument("--scope", default="*")
    generalized.add_argument(
        "--families",
        default="filesystem.single_file",
        help="comma-separated family IDs",
    )
    generalized.add_argument("--seed", type=int, default=0)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "init":
        config_path = Path(args.config)
        root = Path(args.root).resolve()
        root.mkdir(parents=True, exist_ok=True)

        if not config_path.exists():
            config_path.write_text(
                default_yaml(root),
                encoding="utf-8",
            )

        (root / ".crest").mkdir(exist_ok=True)
        print(
            f"initialized crest config at {config_path} "
            f"(root={root})"
        )
        return 0

    if (
        args.command == "research"
        and args.research_command == "reproduce"
    ):
        return _run_research_reproduction(args)

    try:
        return _dispatch(args, parser)
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        from .store import SecurityStateCorrupt

        if isinstance(exc, (SecurityStateCorrupt, OSError)):
            print(
                f"ERROR: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 2
        raise


def _dispatch(args, parser) -> int:
    if args.command == "experiment" and args.name in (
        "conclusion",
        "tables",
    ):
        import importlib

        module_map = {
            "tables": (
                "experiments.generalization.tables",
                "write_all",
            ),
            "conclusion": (
                "experiments.generalization.conclusion",
                "evaluate",
            ),
        }
        module_name, function_name = module_map[args.name]
        module = importlib.import_module(module_name)

        if args.name == "tables":
            print(f"wrote {getattr(module, function_name)()}")
            return 0

        outcome = getattr(module, function_name)()
        print(json.dumps(outcome, indent=2))

        results_dir = (
            Path(__file__).resolve().parents[2]
            / "experiments"
            / "results"
        )
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "conclusion.json").write_text(
            json.dumps(outcome, indent=2),
            encoding="utf-8",
        )
        return 0

    runtime = _runtime(args)

    try:
        if args.command == "status":
            print(json.dumps(runtime.status(), indent=2))
            return 0

        if args.command == "config":
            import dataclasses

            print(
                json.dumps(
                    dataclasses.asdict(runtime.config),
                    indent=2,
                    default=str,
                )
            )
            return 0

        if args.command == "capabilities":
            if args.caps_command in (None, "list"):
                for row in runtime.list_capabilities():
                    print(
                        f"{row['capability_id']}  "
                        f"state={row['state']}  "
                        f"receipt={row['receipt_id']}"
                    )
                return 0

            if args.caps_command == "show":
                row = runtime.get_capability(args.capability_id)
                if row is None:
                    print(f"no such capability: {args.capability_id}")
                    return 4
                print(json.dumps(row, indent=2))
                return 0

            if args.caps_command == "revoke":
                try:
                    result = runtime.revoke(
                        args.capability_id,
                        args.reason,
                    )
                    print(json.dumps(result, indent=2))
                    return 0
                except KeyError:
                    print(f"no such capability: {args.capability_id}")
                    return 4

        if args.command == "receipts":
            if args.receipts_command in (None, "list"):
                for receipt in runtime.list_receipts():
                    print(
                        f"{receipt['receipt_id']}  "
                        f"{receipt['action_class']}  "
                        f"scope={receipt['scope']}  "
                        f"status={receipt['status']}  "
                        f"expires={receipt['expires_at']}"
                    )
                return 0

            if args.receipts_command == "show":
                payload = runtime.get_receipt(args.receipt_id)
                if payload is None:
                    print(f"no such receipt: {args.receipt_id}")
                    return 4
                print(json.dumps(payload, indent=2))
                return 0

        if args.command == "audit":
            for event in runtime.audit(args.limit):
                print(
                    f"{event['timestamp']}  "
                    f"{event['decision']:<22} "
                    f"{event['tool'] or '-':10} "
                    f"{event['operation'] or '-':16} "
                    f"{event['reason'] or ''}"
                )
            return 0

        if args.command == "policy":
            if args.policy_command == "check":
                decision = runtime.check(
                    agent_id="cli-policy-check",
                    tool=args.tool,
                    operation=args.operation,
                    arguments=_parse_kvs(args.arg),
                )
                print(json.dumps(decision.to_audit(), indent=2))
                return 0 if decision.allowed else 3

        if args.command == "verify":
            result = runtime.verify_and_admit(
                action_class=args.action,
                scope=args.scope,
                recovery=RecoveryProgram(kind=args.recovery),
                target=args.target,
                trials=args.trials,
                seed=args.seed,
            )
            print(json.dumps(result, indent=2))
            return 0 if result.get("admitted") else 3

        if args.command == "exec":
            arguments = _parse_kvs(args.arg)

            if args.dry_run:
                decision = runtime.check(
                    agent_id="cli",
                    tool=args.tool,
                    operation=args.operation,
                    arguments=arguments,
                )
                print(
                    json.dumps(
                        {
                            "dry_run": True,
                            **decision.to_audit(),
                        },
                        indent=2,
                    )
                )
                return 0 if decision.allowed else 3

            result = runtime.execute(
                agent_id="cli",
                tool=args.tool,
                operation=args.operation,
                arguments=arguments,
            )
            print(
                json.dumps(
                    {
                        "ok": result.ok,
                        "reason": result.reason,
                        "target": result.target,
                        "exposure_after": result.exposure_after,
                        "output": result.output,
                    },
                    indent=2,
                )
            )
            return 0 if result.ok else 3

        if (
            args.command == "evidence"
            and args.evidence_command in (None, "list")
        ):
            for row in runtime.list_receipts():
                payload = runtime.get_receipt(row["receipt_id"]) or {}
                generalization = payload.get("generalization")
                classification = (
                    generalization.get("classification")
                    if generalization
                    else "fixture-only"
                )
                print(
                    f"{row['receipt_id']}  "
                    f"{row['action_class']}  "
                    f"status={row['status']}  "
                    f"gen={classification}"
                )
            return 0

        if args.command == "doctor":
            from .doctor import doctor, doctor_deep

            if args.deep:
                return doctor_deep(runtime)
            return doctor(runtime)

        if args.command == "benchmark":
            from .benchmarks import run as run_benchmark

            print(
                json.dumps(
                    run_benchmark(args.which),
                    indent=2,
                )
            )
            return 0

        if args.command == "report":
            status = runtime.status()
            receipts_list = runtime.list_receipts()
            print(
                json.dumps(
                    {
                        "status": status,
                        "receipts": receipts_list,
                        "capabilities": runtime.list_capabilities(),
                        "audit_events": len(runtime.audit(500)),
                    },
                    indent=2,
                )
            )
            return 0

        if args.command == "verify-generalized":
            result = runtime.verify_generalized(
                action_class=args.action,
                scope=args.scope,
                recovery=RecoveryProgram(kind=args.recovery),
                family_ids=tuple(
                    family.strip()
                    for family in args.families.split(",")
                    if family.strip()
                ),
                seed=args.seed,
            )
            print(json.dumps(result, indent=2))
            return 0 if result.get("admitted") else 3

        if args.command == "experiment":
            import importlib

            module_map = {
                "cross-distribution": (
                    "experiments.generalization.cross_distribution",
                    "run_grid",
                ),
                "ablations": (
                    "experiments.generalization.ablations",
                    "run_all",
                ),
                "exposure-sweep": (
                    "experiments.generalization.exposure_sweep",
                    "run_all",
                ),
                "confidence": (
                    "experiments.generalization.confidence_sensitivity",
                    "run_all",
                ),
                "drift": (
                    "experiments.generalization.drift_experiment",
                    "run",
                ),
                "tables": (
                    "experiments.generalization.tables",
                    "write_all",
                ),
                "conclusion": (
                    "experiments.generalization.conclusion",
                    "evaluate",
                ),
                "holdout": (
                    "experiments.holdout.run_holdout",
                    "run",
                ),
            }

            module_name, function_name = module_map[args.name]
            module = importlib.import_module(module_name)
            function = getattr(module, function_name)

            if args.name == "tables":
                print(f"wrote {function()}")
                return 0

            if args.name == "conclusion":
                print(json.dumps(function(), indent=2))
                return 0

            function()
            return 0

        parser.print_help()
        return 0

    finally:
        runtime.close()


if __name__ == "__main__":
    sys.exit(main())
