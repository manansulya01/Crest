"""Reproducibility manifest digest behavior.

The research-reproduce manifest must hash stable scientific content, not
volatile bookkeeping such as evaluation timestamps: repeated runs over
equivalent inputs and outputs must produce the same ``result_digest``.
"""
from __future__ import annotations

from crest.cli import _canonical_digest, _reproducible_result_payload


def _details(stamp: str) -> dict:
    return {
        "verdict": "SUPPORTED",
        "reason": "generalized evidence behaved as pre-declared",
        "criteria": {"C1": True, "C4": 0.0},
        "generated_at": stamp,
    }


def _digest(summary: dict, artifacts=None, failures=None) -> str:
    return _canonical_digest(
        _reproducible_result_payload(
            summary, artifacts or [], failures or []
        )
    )


def test_digest_stable_across_evaluation_timestamps():
    first = {
        "conclusion": "SUPPORTED",
        "conclusion_details": _details("2026-01-01T00:00:00+00:00"),
    }
    second = {
        "conclusion": "SUPPORTED",
        "conclusion_details": _details("2026-10-18T11:22:33.123456+00:00"),
    }
    assert _digest(first) == _digest(second)


def test_digest_changes_when_verdict_changes():
    first = {"conclusion": "SUPPORTED", "conclusion_details": _details("t")}
    second = {"conclusion": "NOT_SUPPORTED", "conclusion_details": _details("t")}
    assert _digest(first) != _digest(second)


def test_digest_changes_when_criteria_change():
    changed = _details("t")
    changed["criteria"] = {"C1": False, "C4": 0.5}
    first = {"conclusion": "SUPPORTED", "conclusion_details": _details("t")}
    second = {"conclusion": "SUPPORTED", "conclusion_details": changed}
    assert _digest(first) != _digest(second)


def test_digest_changes_when_failures_change():
    base = {"conclusion": None, "conclusion_details": None}
    assert _digest(base) != _digest(base, failures=["conclusion evaluation failed"])


def test_digest_covers_artifact_metadata():
    base = {"conclusion": None, "conclusion_details": None}
    artifact = {
        "name": "tables",
        "path": "all_tables.md",
        "sha256": "f" * 64,
        "size_bytes": 100,
    }
    same = dict(artifact)
    other = dict(artifact, sha256="e" * 64)
    assert _digest(base, artifacts=[artifact]) != _digest(base, artifacts=[other])
    assert _digest(base, artifacts=[artifact]) == _digest(base, artifacts=[same])


def test_digest_handles_missing_conclusion_details():
    base = {"conclusion": None, "conclusion_details": None}
    assert isinstance(_digest(base), str)
    assert len(_digest(base)) == 64
