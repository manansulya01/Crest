"""Focused tests for the Evidence Integrity simulator (Cycle 3)."""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace

import pytest

from experiments.benchmark.evidence_integrity import (
    DEFAULT_CONFIG,
    POLICIES,
    Calibration,
    EvidenceItem,
    Task,
    calibrate,
    claim_confidence,
    decide,
    generate_tasks,
    policy_blind_sequential,
    policy_provenance_sequential,
    policy_strong_high_risk_gate,
    run_full,
    stable_seed,
    subclaim_confidence,
)


def make_item(
    evidence_id: str,
    kind: str,
    ancestry,
    scope,
    verdicts,
    cost: float = 0.5,
    stale: bool = False,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        kind=kind,
        family="test-family",
        ancestry=ancestry,
        scope=scope,
        verdicts=verdicts,
        cost=cost,
        stale=stale,
    )


@pytest.fixture()
def calibration() -> Calibration:
    return Calibration(
        prior_subclaim=0.75,
        rel_det=0.99,
        rel_cheap=0.65,
        rel_strong=0.65,
        rel_ext=0.85,
        rel_format=0.60,
        rel_unknown=0.5,
    )


def test_stable_seed_across_hash_seeds() -> None:
    code = (
        "from experiments.benchmark.evidence_integrity import stable_seed;"
        "print(stable_seed('alpha', 'beta'))"
    )
    root = os.getcwd()
    base_env = os.environ.copy()
    base_env["PYTHONPATH"] = os.pathsep.join(["src", "."])
    outputs = []
    for hash_seed in ("1", "2"):
        env = dict(base_env)
        env["PYTHONHASHSEED"] = hash_seed
        outputs.append(
            subprocess.check_output(
                [sys.executable, "-c", code],
                cwd=root,
                env=env,
                text=True,
            ).strip()
        )
    assert outputs[0] == outputs[1]
    assert stable_seed("alpha", "beta") == int(outputs[0])


def test_generate_tasks_is_deterministic_and_splits_are_disjoint() -> None:
    cal_a, eval_a = generate_tasks(20, 30, 42)
    cal_b, eval_b = generate_tasks(20, 30, 42)
    assert [t.task_id for t in cal_a] == [t.task_id for t in cal_b]
    assert [t.task_id for t in eval_a] == [t.task_id for t in eval_b]
    assert [t.truth for t in eval_a] == [t.truth for t in eval_b]
    assert {t.task_id for t in cal_a}.isdisjoint({t.task_id for t in eval_a})
    assert all(t.split == "calibration" for t in cal_a)
    assert all(t.split == "evaluation" for t in eval_a)


def test_duplicate_shares_source_and_verdicts() -> None:
    cal, tasks = generate_tasks(30, 5, 42)
    task = tasks[0]
    judges = [item for item in task.evidence if item.kind == "cheap_judge"]
    assert len(judges) >= 2
    first, duplicate = judges[0], judges[1]
    assert first.evidence_id != duplicate.evidence_id
    assert first.ancestry == duplicate.ancestry
    assert first.scope == duplicate.scope
    assert first.verdicts == duplicate.verdicts


def test_duplicate_does_not_increase_provenance_aware_confidence(calibration) -> None:
    first = make_item("a", "cheap_judge", ("llm",), (0, 1), (True, True))
    duplicate = make_item("b", "cheap_judge", ("llm",), (0, 1), (True, True))

    one = subclaim_confidence([first], 0, calibration, blind=False, scope_aware=True)
    two = subclaim_confidence([first, duplicate], 0, calibration, blind=False, scope_aware=True)
    blind = subclaim_confidence([first, duplicate], 0, calibration, blind=True, scope_aware=True)

    assert two == pytest.approx(one)
    assert blind > one


def test_shared_family_counts_as_one_cluster(calibration) -> None:
    cheap = make_item("a", "cheap_judge", ("shared",), (0, 1), (True, True))
    strong = make_item("b", "strong_judge", ("shared",), (0, 1), (True, True))

    one = subclaim_confidence([cheap], 0, calibration, blind=False, scope_aware=True)
    shared = subclaim_confidence([cheap, strong], 0, calibration, blind=False, scope_aware=True)
    blind = subclaim_confidence([cheap, strong], 0, calibration, blind=True, scope_aware=True)

    assert shared == pytest.approx(one)
    assert blind > shared


def test_unknown_provenance_is_pooled_and_capped(calibration) -> None:
    cheap = make_item("a", "cheap_judge", None, (0, 1), (True, True))
    ext = make_item("b", "ext_registry", None, (0, 1), (True, True))

    one = subclaim_confidence([cheap], 0, calibration, blind=False, scope_aware=True)
    pooled = subclaim_confidence([cheap, ext], 0, calibration, blind=False, scope_aware=True)
    blind = subclaim_confidence([cheap, ext], 0, calibration, blind=True, scope_aware=True)

    # Unknown-provenance evidence is capped at 0.5 reliability, so it is neutral
    # for every policy and can never act as positive support.
    assert pooled == pytest.approx(one)
    assert blind == pytest.approx(pooled)
    known_cheap = make_item("c", "cheap_judge", ("llm",), (0, 1), (True, True))
    known_ext = make_item("d", "ext_registry", ("registry",), (0, 1), (True, True))
    known_pair = subclaim_confidence(
        [known_cheap, known_ext], 0, calibration, blind=False, scope_aware=True
    )
    assert known_pair > pooled
    # Unknown-provenance evidence is capped at 0.5 reliability.
    assert one < subclaim_confidence(
        [make_item("e", "ext_registry", ("registry",), (0, 1), (True, True))],
        0, calibration, blind=False, scope_aware=True,
    )


def test_scope_aware_ignores_out_of_scope_evidence(calibration) -> None:
    format_check = make_item("f", "format_check", ("format",), (2,), (True,))
    prior = calibration.prior_subclaim

    aware = subclaim_confidence([format_check], 0, calibration, blind=False, scope_aware=True)
    blind = subclaim_confidence([format_check], 0, calibration, blind=True, scope_aware=False)

    assert aware == pytest.approx(prior)
    assert blind > prior


def test_claim_confidence_is_weakest_link(calibration) -> None:
    det = make_item("d", "det_rule", ("rule",), (0,), (True,), cost=0.02)
    confidence, per = claim_confidence(
        [det], calibration, DEFAULT_CONFIG, blind=False, scope_aware=True
    )
    assert per[0] > 0.95
    assert per[1] == pytest.approx(calibration.prior_subclaim)
    assert confidence == pytest.approx(min(per))
    assert decide(confidence, "high", DEFAULT_CONFIG) == "INDETERMINATE"


def test_risk_thresholds_are_strictly_ordered() -> None:
    assert (
        DEFAULT_CONFIG.accept_threshold["low"]
        < DEFAULT_CONFIG.accept_threshold["med"]
        < DEFAULT_CONFIG.accept_threshold["high"]
    )
    assert (
        DEFAULT_CONFIG.reject_threshold["low"]
        > DEFAULT_CONFIG.reject_threshold["med"]
        > DEFAULT_CONFIG.reject_threshold["high"]
    )


def test_budget_exhaustion_never_accepts() -> None:
    cfg = replace(
        DEFAULT_CONFIG,
        budget={"low": 0.10, "med": 0.10, "high": 0.10},
    )
    calibration_tasks, evaluation_tasks = generate_tasks(30, 10, 42)
    calibration = calibrate(calibration_tasks, cfg)
    for task in evaluation_tasks:
        result = policy_strong_high_risk_gate(task, calibration, cfg)
        assert result.decision == "INDETERMINATE"
        assert result.cost <= 0.10 + 1e-9


def test_sequential_never_reacquires_a_known_source_at_equal_scope() -> None:
    calibration_tasks, evaluation_tasks = generate_tasks(50, 20, 42)
    calibration = calibrate(calibration_tasks, DEFAULT_CONFIG)
    task = next(
        t for t in evaluation_tasks
        if any(item.kind == "cheap_judge" and item.ancestry is not None for item in t.evidence)
    )
    result = policy_provenance_sequential(task, calibration, DEFAULT_CONFIG)
    by_id = {item.evidence_id: item for item in task.evidence}
    acquired = [by_id[eid] for eid in result.evidence_ids]
    for index, item in enumerate(acquired):
        for earlier in acquired[:index]:
            if item.ancestry is not None and earlier.ancestry == item.ancestry:
                assert not set(item.scope).issubset(set(earlier.scope))


def test_stale_evidence_is_discounted(calibration) -> None:
    fresh = make_item("f", "ext_registry", ("registry",), (0, 1), (True, True))
    stale = replace(fresh, evidence_id="s", stale=True)
    fresh_confidence = subclaim_confidence(
        [fresh], 0, calibration, blind=False, scope_aware=True
    )
    stale_confidence = subclaim_confidence(
        [stale], 0, calibration, blind=False, scope_aware=True
    )
    assert stale_confidence < fresh_confidence


def test_policies_do_not_read_ground_truth(monkeypatch) -> None:
    calibration_tasks, evaluation_tasks = generate_tasks(30, 5, 42)
    calibration = calibrate(calibration_tasks, DEFAULT_CONFIG)
    task = evaluation_tasks[0]

    def forbidden(self):
        raise AssertionError("policy read hidden ground truth")

    monkeypatch.setattr(Task, "truth", property(forbidden))
    for name, policy in POLICIES.items():
        if name == "oracle (diagnostic)":
            continue
        policy(task, calibration, DEFAULT_CONFIG)


def test_calibration_produces_sane_reliabilities() -> None:
    calibration_tasks, _ = generate_tasks(200, 0, 42)
    calibration = calibrate(calibration_tasks, DEFAULT_CONFIG)
    assert 0.90 < calibration.rel_det <= 1.0
    assert 0.40 < calibration.rel_cheap < 0.80
    assert 0.60 < calibration.rel_ext <= 1.0
    assert calibration.prior_subclaim > 0.5
    for value in (
        calibration.prior_subclaim,
        calibration.rel_det,
        calibration.rel_cheap,
        calibration.rel_strong,
        calibration.rel_ext,
        calibration.rel_format,
    ):
        assert 0.0 <= value <= 1.0


def test_full_run_is_deterministic() -> None:
    first = run_full(seeds=(42,), n_calibration=30, n_evaluation=40)
    second = run_full(seeds=(42,), n_calibration=30, n_evaluation=40)
    assert first == second
