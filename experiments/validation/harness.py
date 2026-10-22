"""Independent confirmatory harness for the V0.5 recovery-admission claim.

The harness has three separate layers:

1. ``policies`` decides admissions without seeing evaluation labels;
2. ``generator`` builds environments the policies never see;
3. this module applies the evaluation oracle and computes the preregistered
   statistics.

The JSON artifact contains every candidate outcome, not just aggregates.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import crest
import crest.faults  # noqa: F401  (registers fault recovery programs)
from crest.actions import ACTIONS
from crest.distributions import Distribution, apply_distribution
from crest.env_family import FAMILIES
from crest.recovery import RecoveryContext, RecoveryProgram, get_handler
from crest.workspace import Workspace

from . import generator, recoveries  # noqa: F401  (registers validation recovery)
from .policies import (
    N_CASES,
    Candidate,
    Policy,
    PolicyResult,
    deployable_policies,
    Oracle,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = REPO_ROOT / "docs" / "v0.5-validation-plan.md"
ARTIFACT_DIR = REPO_ROOT / "experiments" / "validation" / "artifacts"

ACTIONS_TESTED = ("delete_file", "modify_file", "move_file")
FAMILIES_TESTED = ("filesystem.single_file", "filesystem.directory_tree")
RECOVERIES_TESTED = (
    "restore_from_snapshot",
    "restore_file_from_snapshot",
    "overfit_distractor_gate",
    "validation_overfit_training_shape",
    "noop_fault",
    "restore_truncated",
    "restore_with_side_effect",
)
EVAL_REPLICATES = (200000, 300000, 400000)
EVAL_SEEDS_PER_DISTRIBUTION = 3
EVAL_DISTRIBUTIONS = tuple(Distribution)


def candidate_grid() -> list[Candidate]:
    """The preregistered 3 x 2 x 7 candidate grid, in deterministic order."""
    return [
        Candidate(action, family, recovery)
        for action in ACTIONS_TESTED
        for family in FAMILIES_TESTED
        for recovery in RECOVERIES_TESTED
    ]


def validate_candidate_set(
    candidates: Iterable[Candidate],
    *,
    strict: bool = True,
) -> list[Candidate]:
    """Reject empty/duplicate sets and, for the confirmatory run, any drift.

    The fixed grid is part of the preregistration. Tests may pass
    ``strict=False`` when exercising a deliberately small harness subset.
    """
    rows = list(candidates)
    if not rows:
        raise ValueError("candidate set must not be empty")
    ids = [candidate.candidate_id for candidate in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate set contains duplicate candidate IDs")
    if strict:
        expected = {candidate.candidate_id for candidate in candidate_grid()}
        actual = set(ids)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                "candidate set differs from the preregistered grid; "
                f"missing={missing!r} extra={extra!r}"
            )
    return rows


@dataclass(frozen=True)
class EvaluationRow:
    candidate: Candidate
    total_trials: int
    total_passed: int
    reliable: bool
    replicates: tuple[dict[str, Any], ...]
    errors: tuple[str, ...]

    @property
    def success_rate(self) -> float:
        if self.total_trials <= 0:
            return 0.0
        return self.total_passed / self.total_trials


def _action_params(action_class: str, target: str) -> dict[str, Any]:
    if action_class == "modify_file":
        return {"content": "modified-by-validation\n"}
    if action_class == "move_file":
        return {"destination": "moved-" + target.rsplit("/", 1)[-1]}
    return {}


def _eval_trial(
    candidate: Candidate,
    seed: int,
    distribution: Distribution,
) -> tuple[bool, str | None]:
    ws = Workspace.temporary()
    try:
        fixture = generator.build(ws, FAMILIES[candidate.family_id], seed)
        apply_distribution(ws, fixture.target, distribution, seed=seed)
        pre = ws.snapshot()
        params = _action_params(candidate.action_class, fixture.target)
        try:
            ACTIONS[candidate.action_class](ws, fixture.target, params)
        except Exception as exc:
            return False, f"action:{type(exc).__name__}:{exc}"
        handler = get_handler(candidate.recovery_kind)
        if handler is None:
            return False, "no recovery handler"
        try:
            handler(
                ws,
                RecoveryContext(
                    candidate.action_class,
                    fixture.target,
                    params,
                    pre,
                ),
            )
        except Exception as exc:
            return False, f"recovery:{type(exc).__name__}:{exc}"
        if not ws.state_matches(pre):
            return False, "state mismatch after recovery"
        return True, None
    except Exception as exc:
        return False, f"trial:{type(exc).__name__}:{exc}"
    finally:
        ws.cleanup()


def evaluate_candidate(
    candidate: Candidate,
    *,
    replicates: Iterable[int] | None = None,
    seeds_per_distribution: int | None = None,
    distributions: Iterable[Distribution] | None = None,
) -> EvaluationRow:
    replicate_bases = tuple(EVAL_REPLICATES if replicates is None else replicates)
    n_seeds = (
        EVAL_SEEDS_PER_DISTRIBUTION
        if seeds_per_distribution is None
        else seeds_per_distribution
    )
    dists = tuple(EVAL_DISTRIBUTIONS if distributions is None else distributions)
    if not replicate_bases or n_seeds <= 0 or not dists:
        raise ValueError("evaluation design must be non-empty")
    if len(set(replicate_bases)) != len(replicate_bases):
        raise ValueError("evaluation replicates must be unique")
    if len(set(dists)) != len(dists):
        raise ValueError("evaluation distributions must be unique")

    replicates: list[dict[str, Any]] = []
    total = passed = 0
    errors: list[str] = []
    for base in replicate_bases:
        per_distribution: dict[str, dict[str, int]] = {}
        replicate_total = replicate_passed = 0
        for dist_index, distribution in enumerate(dists):
            d_passed = 0
            for index in range(n_seeds):
                seed = base + dist_index * 100 + index
                ok, error = _eval_trial(candidate, seed, distribution)
                replicate_total += 1
                d_passed += int(ok)
                if error:
                    errors.append(f"{base}:{distribution.value}:{error}")
            replicate_passed += d_passed
            per_distribution[distribution.value] = {
                "passed": d_passed,
                "n": n_seeds,
            }
        total += replicate_total
        passed += replicate_passed
        replicates.append(
            {
                "seed_base": base,
                "passed": replicate_passed,
                "n": replicate_total,
                "per_distribution": per_distribution,
                "success_rate": (
                    round(replicate_passed / replicate_total, 6)
                    if replicate_total
                    else 0.0
                ),
            }
        )
    return EvaluationRow(
        candidate=candidate,
        total_trials=total,
        total_passed=passed,
        reliable=total > 0 and passed == total,
        replicates=tuple(replicates),
        errors=tuple(errors),
    )


def _wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if n <= 0:
        return None
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    margin = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return [round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)]


def _policy_summary(
    policy: Policy,
    decisions: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    rows = list(decisions)
    n = len(rows)
    admitted_rows = [row for row in rows if row["admitted"]]
    reliable_rows = [row for row in rows if row["reliable"]]
    reliable_admitted = [
        row for row in admitted_rows if row["reliable"]
    ]
    unsafe = [row for row in admitted_rows if not row["reliable"]]
    false_rejections = [
        row for row in rows if not row["admitted"] and row["reliable"]
    ]
    admitted = len(admitted_rows)
    return {
        "policy": policy.name,
        "deployable": policy.deployable,
        "candidates": n,
        "admitted": admitted,
        "reliable_candidates": len(reliable_rows),
        "reliable_admitted": len(reliable_admitted),
        "unsafe_admitted": len(unsafe),
        "false_rejections": len(false_rejections),
        "coverage_rate": round(admitted / n, 6) if n else 0.0,
        "reliable_coverage_rate": (
            round(len(reliable_admitted) / len(reliable_rows), 6)
            if reliable_rows
            else None
        ),
        "unsafe_rate_among_admitted": (
            round(len(unsafe) / admitted, 6) if admitted else None
        ),
        "unsafe_rate_among_candidates": (
            round(len(unsafe) / n, 6) if n else 0.0
        ),
        "precision": (
            round(len(reliable_admitted) / admitted, 6) if admitted else None
        ),
        "unsafe_ci_95": _wilson(len(unsafe), admitted) if admitted else None,
        "precision_ci_95": (
            _wilson(len(reliable_admitted), admitted) if admitted else None
        ),
        "total_verification_seconds": round(
            sum(row["verification_seconds"] for row in rows), 6
        ),
        "mean_verification_seconds": (
            round(
                sum(row["verification_seconds"] for row in rows) / n,
                6,
            )
            if n
            else 0.0
        ),
        "admitted_ids": [row["candidate_id"] for row in admitted_rows],
        "unsafe_ids": [row["candidate_id"] for row in unsafe],
        "false_rejection_ids": [
            row["candidate_id"] for row in false_rejections
        ],
    }


def _binom_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1))
    return min(1.0, 2.0 * tail / (2**n))


def _binom_one_sided_generalized_less(b: int, c: int) -> float:
    """P(X <= c) under X~Bin(b+c, 0.5); the safety alternative is b > c."""
    n = b + c
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(c + 1)) / (2**n)


def _paired_comparison(
    fixture_rows: list[dict[str, Any]],
    generalized_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    fixture = {row["candidate_id"]: row for row in fixture_rows}
    generalized = {row["candidate_id"]: row for row in generalized_rows}
    ids = sorted(set(fixture) & set(generalized))
    b_rows = [
        cid
        for cid in ids
        if fixture[cid]["unsafe_admission"]
        and not generalized[cid]["unsafe_admission"]
    ]
    c_rows = [
        cid
        for cid in ids
        if generalized[cid]["unsafe_admission"]
        and not fixture[cid]["unsafe_admission"]
    ]
    return {
        "candidate_pairs": len(ids),
        "fixture_only_unsafe_generalized_safe": len(b_rows),
        "generalized_unsafe_fixture_only_safe": len(c_rows),
        "both_unsafe": sum(
            1
            for cid in ids
            if fixture[cid]["unsafe_admission"]
            and generalized[cid]["unsafe_admission"]
        ),
        "neither_unsafe": sum(
            1
            for cid in ids
            if not fixture[cid]["unsafe_admission"]
            and not generalized[cid]["unsafe_admission"]
        ),
        "fixture_only_unsafe_ids": b_rows,
        "generalized_only_unsafe_ids": c_rows,
        "mcnemar_exact_two_sided_p": round(
            _binom_two_sided(len(b_rows), len(c_rows)), 6
        ),
        "one_sided_safety_p": round(
            _binom_one_sided_generalized_less(len(b_rows), len(c_rows)),
            6,
        ),
    }


def _verdict(
    fixture: dict[str, Any],
    generalized: dict[str, Any],
    family: dict[str, Any],
) -> dict[str, Any]:
    fixture_unsafe = fixture["unsafe_admitted"]
    generalized_unsafe = generalized["unsafe_admitted"]
    if fixture_unsafe > 0 and generalized_unsafe == 0 and generalized_unsafe < fixture_unsafe:
        h1 = "PASS"
    elif generalized_unsafe < fixture_unsafe:
        h1 = "PARTIAL"
    else:
        h1 = "FAIL"

    reliable = generalized["reliable_candidates"]
    if (
        reliable >= 8
        and generalized["false_rejections"] == 0
        and generalized["reliable_admitted"] == reliable
    ):
        h2 = "PASS"
    elif reliable >= 8 and generalized["reliable_admitted"] >= 8:
        h2 = "PARTIAL"
    else:
        h2 = "FAIL"

    precisions = (family["precision"], generalized["precision"])
    if all(value == 1.0 for value in precisions if value is not None) and all(
        value is not None for value in precisions
    ):
        h3 = "PASS"
    elif all(
        value is not None and value >= 0.90 for value in precisions
    ):
        h3 = "PARTIAL"
    else:
        h3 = "FAIL"

    if h1 == "PASS" and h2 == "PASS" and h3 == "PASS":
        overall = "PASS"
    elif h1 == "PASS" and h2 != "FAIL" and h3 != "FAIL":
        overall = "PARTIAL"
    else:
        overall = "FAIL"

    return {
        "H1_safety": h1,
        "H2_reliable_coverage": h2,
        "H3_evidence_precision": h3,
        "overall": overall,
        "rule": (
            "PASS requires H1/H2/H3 PASS; PARTIAL requires H1 PASS and no "
            "H2/H3 FAIL; otherwise FAIL. See docs/v0.5-validation-plan.md."
        ),
    }


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scientific_payload(result: dict[str, Any]) -> dict[str, Any]:
    """The stable scientific subset; timings and machine metadata excluded."""
    return {
        "protocol_sha256": result["protocol_sha256"],
        "canonical_config_digest": result["canonical_config_digest"],
        "design": result["design"],
        "candidates": result["candidates"],
        "evaluations": [
            {
                "candidate_id": row["candidate_id"],
                "total_trials": row["total_trials"],
                "total_passed": row["total_passed"],
                "reliable": row["reliable"],
                "replicates": row["replicates"],
                "errors": row["errors"],
            }
            for row in result["evaluations"]
        ],
        "policies": {
            name: {
                key: value
                for key, value in summary.items()
                if key
                not in (
                    "total_verification_seconds",
                    "mean_verification_seconds",
                )
            }
            for name, summary in result["policies"].items()
        },
        "policy_decisions": {
            name: [
                {
                    key: value
                    for key, value in row.items()
                    if key != "verification_seconds"
                }
                for row in rows
            ]
            for name, rows in result.get("policy_decisions", {}).items()
        },
        "paired": result["paired"],
        "verdict": result["verdict"],
    }


def _scientific_digest(result: dict[str, Any]) -> str:
    payload = json.dumps(
        _scientific_payload(result),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Crest V0.5 independent validation result",
        "",
        "This file is generated from `experiments/validation/artifacts/v05_validation.json`.",
        "It reports a synthetic recovery-admission experiment, not model-provider",
        "economics and not a production safety guarantee.",
        "",
        f"- Protocol SHA-256: `{result['protocol_sha256']}`",
        f"- Result digest: `{result['result_digest']}`",
        f"- Commit: `{result['run']['git_commit']}`",
        f"- Working tree dirty: `{result['run']['working_tree_dirty']}`",
        f"- Canonical config digest: `{result['canonical_config_digest']}`",
        f"- Verdict: **{result['verdict']['overall']}**",
        "",
        "## Policy summary",
        "",
        "| policy | admitted | unsafe | reliable admitted | false rejects | precision | unsafe rate (admitted) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in (
        "deny_all",
        "admit_all",
        "fixture_only",
        "family_only",
        "generalized",
        "oracle",
    ):
        summary = result["policies"][name]
        lines.append(
            f"| {name} | {summary['admitted']} | {summary['unsafe_admitted']} | "
            f"{summary['reliable_admitted']} | {summary['false_rejections']} | "
            f"{summary['precision']} | {summary['unsafe_rate_among_admitted']} |"
        )
    lines.extend(
        [
            "",
            "## Paired safety comparison",
            "",
            f"- Fixture-only unsafe / generalized safe: "
            f"{result['paired']['fixture_only_unsafe_generalized_safe']}",
            f"- Generalized unsafe / fixture-only safe: "
            f"{result['paired']['generalized_unsafe_fixture_only_safe']}",
            f"- Exact McNemar two-sided p: "
            f"{result['paired']['mcnemar_exact_two_sided_p']}",
            f"- One-sided safety p: {result['paired']['one_sided_safety_p']}",
            "",
            "## Decision",
            "",
            f"- H1 safety: **{result['verdict']['H1_safety']}**",
            f"- H2 reliable coverage: **{result['verdict']['H2_reliable_coverage']}**",
            f"- H3 evidence precision: **{result['verdict']['H3_evidence_precision']}**",
            "",
            "The oracle row is a diagnostic upper bound using evaluation labels; it is",
            "not a deployable policy. Verification seconds are wall-clock observations",
            "and are excluded from the scientific digest.",
            "",
        ]
    )
    return "\n".join(lines)


def run_validation(
    *,
    write: bool = True,
    candidates: Iterable[Candidate] | None = None,
    policy_suite: Iterable[Policy] | None = None,
    eval_replicates: Iterable[int] | None = None,
    eval_seeds_per_distribution: int | None = None,
    eval_distributions: Iterable[Distribution] | None = None,
    artifact_dir: Path | None = None,
    protocol_path: Path | None = None,
    strict_candidates: bool = True,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    rows = validate_candidate_set(
        candidate_grid() if candidates is None else candidates,
        strict=strict_candidates,
    )
    replicate_bases = tuple(
        EVAL_REPLICATES if eval_replicates is None else eval_replicates
    )
    n_seeds = (
        EVAL_SEEDS_PER_DISTRIBUTION
        if eval_seeds_per_distribution is None
        else eval_seeds_per_distribution
    )
    dists = tuple(
        EVAL_DISTRIBUTIONS if eval_distributions is None else eval_distributions
    )
    if not replicate_bases or n_seeds <= 0 or not dists:
        raise ValueError("evaluation design must be non-empty")
    if len(set(replicate_bases)) != len(replicate_bases):
        raise ValueError("evaluation replicates must be unique")
    if len(set(dists)) != len(dists):
        raise ValueError("evaluation distributions must be unique")

    policies: list[Policy] = list(
        deployable_policies(n=N_CASES)
        if policy_suite is None
        else policy_suite
    )
    required_policies = {"fixture_only", "family_only", "generalized"}
    if not required_policies.issubset({policy.name for policy in policies}):
        missing = sorted(required_policies - {policy.name for policy in policies})
        raise ValueError(f"policy suite is missing required policies: {missing!r}")

    evaluations = [
        evaluate_candidate(
            candidate,
            replicates=replicate_bases,
            seeds_per_distribution=n_seeds,
            distributions=dists,
        )
        for candidate in rows
    ]
    labels = {
        row.candidate.candidate_id: row.reliable for row in evaluations
    }
    eval_by_id = {row.candidate.candidate_id: row for row in evaluations}
    if not any(policy.name == "oracle" for policy in policies):
        policies.append(Oracle(labels))

    policy_errors: list[str] = []
    policy_decisions: dict[str, list[dict[str, Any]]] = {}
    for policy in policies:
        decisions: list[dict[str, Any]] = []
        for candidate in rows:
            started = time.perf_counter()
            try:
                decision: PolicyResult = policy.decide(candidate)
            except Exception as exc:
                policy_errors.append(
                    f"{policy.name}:{candidate.candidate_id}:"
                    f"{type(exc).__name__}:{exc}"
                )
                decision = PolicyResult(
                    False,
                    "ERROR",
                    f"policy error: {type(exc).__name__}: {exc}",
                    round(time.perf_counter() - started, 6),
                    {},
                )
            evaluation = eval_by_id[candidate.candidate_id]
            decisions.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "action": candidate.action_class,
                    "family": candidate.family_id,
                    "recovery": candidate.recovery_kind,
                    "admitted": decision.admitted,
                    "evidence_class": decision.evidence_class,
                    "reason": decision.reason,
                    "verification_seconds": decision.verification_seconds,
                    "reliable": evaluation.reliable,
                    "evaluation_success": round(evaluation.success_rate, 6),
                    "unsafe_admission": decision.admitted
                    and not evaluation.reliable,
                    "false_rejection": (not decision.admitted)
                    and evaluation.reliable,
                }
            )
        policy_decisions[policy.name] = decisions

    summaries = {
        policy.name: _policy_summary(policy, policy_decisions[policy.name])
        for policy in policies
    }
    paired = _paired_comparison(
        policy_decisions["fixture_only"],
        policy_decisions["generalized"],
    )
    verdict = _verdict(
        summaries["fixture_only"],
        summaries["generalized"],
        summaries["family_only"],
    )
    if policy_errors:
        verdict["overall"] = "INCONCLUSIVE"
        verdict["policy_errors"] = policy_errors

    protocol_file = PLAN_PATH if protocol_path is None else protocol_path
    try:
        protocol_ref = str(protocol_file.relative_to(REPO_ROOT))
    except ValueError:
        protocol_ref = str(protocol_file)
    artifact_root = ARTIFACT_DIR if artifact_dir is None else artifact_dir

    from experiments.generalization.config import canonical

    result: dict[str, Any] = {
        "schema_version": 1,
        "experiment_name": "v05-independent-recovery-admission-validation",
        "protocol_path": protocol_ref.replace("\\", "/"),
        "protocol_sha256": _sha256_file(protocol_file),
        "generated_at": started_at,
        "run": {
            "git_commit": _git(["rev-parse", "HEAD"]),
            "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "working_tree_dirty": bool(_git(["status", "--porcelain"])),
            "crest_version": crest.__version__,
            "python": sys.version.split()[0],
            "os": platform.platform(),
        },
        "canonical_config_digest": canonical().digest(),
        "design": {
            "actions": list(ACTIONS_TESTED),
            "families": list(FAMILIES_TESTED),
            "recoveries": list(RECOVERIES_TESTED),
            "candidates": len(rows),
            "policy_n_cases": N_CASES,
            "generalized_shift_cases": 6,
            "evaluation_replicates": list(replicate_bases),
            "evaluation_distributions": [
                distribution.value for distribution in dists
            ],
            "evaluation_seeds_per_distribution": n_seeds,
            "evaluation_trials_per_candidate": (
                len(replicate_bases) * len(dists) * n_seeds
            ),
            "policy_seed_bases": {
                "verification": 1000,
                "holdout": 90000,
                "shift": 50000,
            },
            "experimental_failure_bound": 0.20,
        },
        "candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "action": candidate.action_class,
                "family": candidate.family_id,
                "recovery": candidate.recovery_kind,
            }
            for candidate in rows
        ],
        "evaluations": [
            {
                "candidate_id": row.candidate.candidate_id,
                "total_trials": row.total_trials,
                "total_passed": row.total_passed,
                "success_rate": round(row.success_rate, 6),
                "reliable": row.reliable,
                "replicates": list(row.replicates),
                "errors": list(row.errors),
            }
            for row in evaluations
        ],
        "policies": summaries,
        "policy_decisions": policy_decisions,
        "paired": paired,
        "verdict": verdict,
    }
    if policy_errors:
        result["harness_errors"] = policy_errors
    result["result_digest"] = _scientific_digest(result)

    if write:
        artifact_root.mkdir(parents=True, exist_ok=True)
        json_path = artifact_root / "v05_validation.json"
        json_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        md_path = artifact_root / "v05_validation.md"
        md_path.write_text(_markdown(result), encoding="utf-8", newline="\n")
        result["artifact_paths"] = {
            "json": str(json_path),
            "markdown": str(md_path),
        }
    return result


def main() -> int:
    result = run_validation()
    print(json.dumps(result["verdict"], indent=2))
    print(f"result_digest: {result['result_digest']}")
    print(f"artifact: {result['artifact_paths']['json']}")
    return 0 if result["verdict"]["overall"] in ("PASS", "PARTIAL") else 3


if __name__ == "__main__":
    raise SystemExit(main())
