"""Tests for the independent V0.5 validation harness.

These tests exercise the harness machinery, not the confirmatory result. They
are deliberately small and do not write the canonical artifact.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from crest.distributions import Distribution
import experiments.validation.harness as harness
import experiments.validation.policies as policy_module
from experiments.validation.policies import (
    Candidate,
    FamilyEvidence,
    FixtureOnly,
    GeneralizedEvidence,
    Oracle,
    PolicyResult,
    deployable_policies,
)


CANDIDATE = Candidate(
    "delete_file",
    "filesystem.single_file",
    "restore_from_snapshot",
)


class _StaticPolicy:
    name = "static"
    deployable = True

    def __init__(self, name: str, admitted: bool):
        self.name = name
        self._admitted = admitted

    def decide(self, candidate: Candidate) -> PolicyResult:
        return PolicyResult(
            self._admitted,
            "VERIFIED_FIXTURE" if self._admitted else "UNVERIFIED",
            "test policy",
            0.0,
            {},
        )


class _BrokenPolicy:
    name = "generalized"
    deployable = True

    def decide(self, candidate: Candidate) -> PolicyResult:
        raise RuntimeError("deliberate verifier failure")


def _static_policy_suite() -> list[_StaticPolicy]:
    return [
        _StaticPolicy("deny_all", False),
        _StaticPolicy("admit_all", True),
        _StaticPolicy("fixture_only", False),
        _StaticPolicy("family_only", True),
        _StaticPolicy("generalized", True),
    ]


def _row(
    candidate_id: str,
    *,
    admitted: bool,
    reliable: bool,
    seconds: float = 0.0,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "admitted": admitted,
        "reliable": reliable,
        "verification_seconds": seconds,
        "unsafe_admission": admitted and not reliable,
        "false_rejection": (not admitted) and reliable,
    }


def _minimal_scientific_result() -> dict[str, object]:
    return {
        "protocol_sha256": "a" * 64,
        "canonical_config_digest": "b" * 64,
        "design": {"candidates": 1},
        "candidates": [{"candidate_id": "candidate"}],
        "evaluations": [
            {
                "candidate_id": "candidate",
                "total_trials": 1,
                "total_passed": 1,
                "reliable": True,
                "replicates": [],
                "errors": [],
            }
        ],
        "policies": {
            "deny_all": {
                "admitted": 0,
                "total_verification_seconds": 1.0,
                "mean_verification_seconds": 1.0,
            }
        },
        "policy_decisions": {
            "deny_all": [
                {
                    "candidate_id": "candidate",
                    "admitted": False,
                    "evidence_class": "UNVERIFIED",
                    "verification_seconds": 1.0,
                }
            ]
        },
        "paired": {"candidate_pairs": 1},
        "verdict": {"overall": "PASS"},
    }


def test_candidate_grid_is_preregistered_42_unique_candidates():
    grid = harness.candidate_grid()
    assert len(grid) == 42
    assert len({candidate.candidate_id for candidate in grid}) == 42
    assert {candidate.action_class for candidate in grid} == {
        "delete_file",
        "modify_file",
        "move_file",
    }
    assert {candidate.family_id for candidate in grid} == {
        "filesystem.single_file",
        "filesystem.directory_tree",
    }
    assert len({candidate.recovery_kind for candidate in grid}) == 7


def test_candidate_validation_rejects_empty_duplicate_and_drifted_sets():
    with pytest.raises(ValueError, match="empty"):
        harness.validate_candidate_set([])
    with pytest.raises(ValueError, match="duplicate"):
        harness.validate_candidate_set(
            [CANDIDATE, CANDIDATE],
            strict=False,
        )
    with pytest.raises(ValueError, match="preregistered"):
        harness.validate_candidate_set([CANDIDATE], strict=True)


def test_evaluation_seeds_are_disjoint_from_policy_seeds():
    evaluation_seeds = {
        base + distribution_index * 100 + index
        for base in harness.EVAL_REPLICATES
        for distribution_index in range(len(harness.EVAL_DISTRIBUTIONS))
        for index in range(harness.EVAL_SEEDS_PER_DISTRIBUTION)
    }
    policy_seeds = set(range(1000, 1012))
    policy_seeds |= set(range(90000, 90012))
    policy_seeds |= set(range(50000, 50018))
    assert evaluation_seeds.isdisjoint(policy_seeds)


def test_evaluate_candidate_rejects_empty_designs():
    with pytest.raises(ValueError):
        harness.evaluate_candidate(CANDIDATE, replicates=())
    with pytest.raises(ValueError):
        harness.evaluate_candidate(CANDIDATE, seeds_per_distribution=0)
    with pytest.raises(ValueError):
        harness.evaluate_candidate(CANDIDATE, distributions=())
    with pytest.raises(ValueError):
        harness.evaluate_candidate(CANDIDATE, replicates=(1, 1))


def test_wilson_interval_has_expected_boundaries():
    low, high = harness._wilson(0, 12)
    assert low == 0.0
    assert high == pytest.approx(0.2425, abs=0.002)
    low, high = harness._wilson(12, 12)
    assert low == pytest.approx(0.7575, abs=0.002)
    assert high == 1.0
    assert harness._wilson(0, 0) is None


def test_exact_binomial_pair_tests():
    assert harness._binom_two_sided(6, 0) == 0.03125
    assert harness._binom_one_sided_generalized_less(6, 0) == 0.015625
    assert harness._binom_two_sided(0, 0) == 1.0
    assert harness._binom_two_sided(1, 1) == 1.0


def test_policy_summary_counts_and_denominators():
    summary = harness._policy_summary(
        _StaticPolicy("fixture_only", True),
        [
            _row("a", admitted=True, reliable=True, seconds=1.0),
            _row("b", admitted=True, reliable=False, seconds=2.0),
            _row("c", admitted=False, reliable=True, seconds=3.0),
            _row("d", admitted=False, reliable=False, seconds=4.0),
        ],
    )
    assert summary["admitted"] == 2
    assert summary["reliable_candidates"] == 2
    assert summary["reliable_admitted"] == 1
    assert summary["unsafe_admitted"] == 1
    assert summary["false_rejections"] == 1
    assert summary["coverage_rate"] == 0.5
    assert summary["reliable_coverage_rate"] == 0.5
    assert summary["precision"] == 0.5
    assert summary["unsafe_rate_among_admitted"] == 0.5
    assert summary["unsafe_rate_among_candidates"] == 0.25
    assert summary["total_verification_seconds"] == 10.0
    assert summary["mean_verification_seconds"] == 2.5
    assert summary["unsafe_ids"] == ["b"]
    assert summary["false_rejection_ids"] == ["c"]


def test_paired_comparison_uses_only_discordant_pairs():
    fixture = [
        _row("a", admitted=True, reliable=True),
        _row("b", admitted=True, reliable=False),
        _row("c", admitted=True, reliable=False),
        _row("d", admitted=False, reliable=False),
    ]
    generalized = [
        _row("a", admitted=True, reliable=True),
        _row("b", admitted=False, reliable=False),
        _row("c", admitted=True, reliable=False),
        _row("d", admitted=False, reliable=False),
    ]
    paired = harness._paired_comparison(fixture, generalized)
    assert paired["fixture_only_unsafe_generalized_safe"] == 1
    assert paired["generalized_unsafe_fixture_only_safe"] == 0
    assert paired["both_unsafe"] == 1
    assert paired["neither_unsafe"] == 2
    assert paired["mcnemar_exact_two_sided_p"] == 1.0
    assert paired["one_sided_safety_p"] == 0.5


def test_verdict_applies_preregistered_rules():
    fixture = {"unsafe_admitted": 2}
    generalized = {
        "unsafe_admitted": 0,
        "reliable_candidates": 10,
        "reliable_admitted": 10,
        "false_rejections": 0,
        "precision": 1.0,
    }
    family = {"precision": 1.0}
    verdict = harness._verdict(fixture, generalized, family)
    assert verdict["H1_safety"] == "PASS"
    assert verdict["H2_reliable_coverage"] == "PASS"
    assert verdict["H3_evidence_precision"] == "PASS"
    assert verdict["overall"] == "PASS"

    partial = harness._verdict(
        fixture,
        {**generalized, "unsafe_admitted": 1},
        family,
    )
    assert partial["H1_safety"] == "PARTIAL"
    assert partial["overall"] == "FAIL"

    failed = harness._verdict(
        {"unsafe_admitted": 0},
        generalized,
        family,
    )
    assert failed["H1_safety"] == "FAIL"
    assert failed["overall"] == "FAIL"


def test_scientific_digest_excludes_timing_and_provenance():
    base = _minimal_scientific_result()
    first = harness._scientific_digest(base)
    timing_changed = copy.deepcopy(base)
    timing_changed["policies"]["deny_all"]["total_verification_seconds"] = 99.0
    timing_changed["policies"]["deny_all"]["mean_verification_seconds"] = 99.0
    timing_changed["generated_at"] = "2999-01-01T00:00:00+00:00"
    timing_changed["run"] = {"git_commit": "another-machine", "os": "other"}
    assert harness._scientific_digest(timing_changed) == first

    scientific_changed = copy.deepcopy(base)
    scientific_changed["evaluations"][0]["total_passed"] = 0
    assert harness._scientific_digest(scientific_changed) != first

    verdict_changed = copy.deepcopy(base)
    verdict_changed["verdict"]["overall"] = "FAIL"
    assert harness._scientific_digest(verdict_changed) != first

    candidate_changed = copy.deepcopy(base)
    candidate_changed["candidates"][0]["candidate_id"] = "other"
    assert harness._scientific_digest(candidate_changed) != first

    classification_changed = copy.deepcopy(base)
    classification_changed["policy_decisions"]["deny_all"][0][
        "evidence_class"
    ] = "VERIFIED_GENERAL"
    assert harness._scientific_digest(classification_changed) != first


def test_protocol_digest_is_sha256_of_frozen_plan():
    digest = harness._sha256_file(harness.PLAN_PATH)
    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")


def test_policy_module_has_no_evaluation_layer_imports():
    source = Path(policy_module.__file__).read_text(encoding="utf-8")
    assert "validation.generator" not in source
    assert "validation.harness" not in source
    assert "EVAL_REPLICATES" not in source


def test_deployable_policies_never_include_oracle():
    policies = deployable_policies()
    assert all(policy.deployable for policy in policies)
    assert {policy.name for policy in policies} == {
        "deny_all",
        "admit_all",
        "fixture_only",
        "family_only",
        "generalized",
    }
    assert Oracle({CANDIDATE.candidate_id: True}).deployable is False


def test_policies_do_not_read_the_validation_generator(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("policy read the evaluation generator")

    monkeypatch.setattr(harness.generator, "build", fail)
    for policy in (
        FixtureOnly(n=2),
        FamilyEvidence(n=2),
        GeneralizedEvidence(n=2, shift_cases=1),
    ):
        result = policy.decide(CANDIDATE)
        assert isinstance(result, PolicyResult)


def test_generator_exception_is_recorded_as_a_trial_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("generator boom")

    monkeypatch.setattr(harness.generator, "build", fail)
    row = harness.evaluate_candidate(
        CANDIDATE,
        replicates=(1,),
        seeds_per_distribution=1,
        distributions=(Distribution.IN_DISTRIBUTION,),
    )
    assert row.total_trials == 1
    assert row.total_passed == 0
    assert row.reliable is False
    assert any("trial:RuntimeError" in error for error in row.errors)


def test_action_exception_is_recorded_as_a_trial_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("action boom")

    monkeypatch.setitem(harness.ACTIONS, "delete_file", fail)
    ok, error = harness._eval_trial(
        CANDIDATE,
        1,
        Distribution.IN_DISTRIBUTION,
    )
    assert ok is False
    assert error is not None and "action:RuntimeError" in error


def test_run_validation_rejects_missing_required_policies():
    with pytest.raises(ValueError, match="missing required"):
        harness.run_validation(
            write=False,
            candidates=[CANDIDATE],
            policy_suite=[_StaticPolicy("deny_all", False)],
            strict_candidates=False,
        )


def test_run_validation_writes_artifact_and_keeps_oracle_diagnostic(tmp_path):
    result = harness.run_validation(
        write=True,
        candidates=[CANDIDATE],
        policy_suite=_static_policy_suite(),
        eval_replicates=(1,),
        eval_seeds_per_distribution=1,
        eval_distributions=(Distribution.IN_DISTRIBUTION,),
        artifact_dir=tmp_path,
        strict_candidates=False,
    )
    assert result["design"]["candidates"] == 1
    assert result["design"]["evaluation_trials_per_candidate"] == 1
    assert result["policies"]["oracle"]["deployable"] is False
    assert result["policies"]["fixture_only"]["admitted"] == 0
    assert (tmp_path / "v05_validation.json").exists()
    markdown = (tmp_path / "v05_validation.md").read_text(encoding="utf-8")
    assert "Verdict" in markdown
    assert "oracle" in markdown
    assert result["result_digest"] in markdown


def test_run_validation_marks_policy_exception_inconclusive(tmp_path):
    suite = _static_policy_suite()
    suite[-1] = _BrokenPolicy()
    result = harness.run_validation(
        write=False,
        candidates=[CANDIDATE],
        policy_suite=suite,
        eval_replicates=(1,),
        eval_seeds_per_distribution=1,
        eval_distributions=(Distribution.IN_DISTRIBUTION,),
        artifact_dir=tmp_path,
        strict_candidates=False,
    )
    assert result["verdict"]["overall"] == "INCONCLUSIVE"
    assert result["harness_errors"]
    assert "deliberate verifier failure" in result["harness_errors"][0]
