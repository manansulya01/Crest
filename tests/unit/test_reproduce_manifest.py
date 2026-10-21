"""Reproducibility manifest digest behavior.

The research-reproduce manifest must hash stable scientific content, not
volatile bookkeeping such as evaluation timestamps: repeated runs over
equivalent inputs and outputs must produce the same ``result_digest``.
"""
from __future__ import annotations

from crest.cli import (
    _canonical_digest,
    _performance_digest,
    _reproducible_result_payload,
)


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


def test_digest_ignores_artifact_location_and_order():
    base = {"conclusion": None, "conclusion_details": None}
    first = {
        "name": "table:ablations.md",
        "path": "C:/checkout-a/experiments/tables/ablations.md",
        "sha256": "f" * 64,
        "size_bytes": 100,
    }
    elsewhere = dict(
        first, path="D:/another-checkout/experiments/tables/ablations.md"
    )
    second = {
        "name": "table:drift.md",
        "path": "C:/checkout-a/experiments/tables/drift.md",
        "sha256": "e" * 64,
        "size_bytes": 200,
    }
    assert _digest(base, artifacts=[first, second]) == _digest(
        base, artifacts=[elsewhere, second]
    )
    assert _digest(base, artifacts=[first, second]) == _digest(
        base, artifacts=[second, first]
    )


def test_digest_handles_missing_conclusion_details():
    base = {"conclusion": None, "conclusion_details": None}
    assert isinstance(_digest(base), str)
    assert len(_digest(base)) == 64


# ---------------------------------------------------------------------------
# configuration and source provenance in the digest
# ---------------------------------------------------------------------------

def test_digest_covers_experiment_configuration():
    base = {
        "conclusion": None,
        "conclusion_details": None,
        "experiment_config": {"samples": 20, "canonical": True},
        "sources": {"ablations.jsonl": {"sha256": "a" * 64}},
    }
    reduced = dict(
        base, experiment_config={"samples": 10, "canonical": False}
    )
    assert _digest(base) != _digest(reduced)


def test_digest_covers_source_hashes():
    base = {
        "conclusion": None,
        "conclusion_details": None,
        "experiment_config": None,
        "sources": {"ablations.jsonl": {"sha256": "a" * 64}},
    }
    assert _digest(base) != _digest(
        dict(base, sources={"ablations.jsonl": {"sha256": "b" * 64}})
    )
    assert _digest(base) == _digest(
        dict(base, sources={"ablations.jsonl": {"sha256": "a" * 64}})
    )


def test_digest_prefers_normalized_scientific_sources():
    base = {
        "conclusion": None,
        "conclusion_details": None,
        "scientific_sources": {"ablations.jsonl": "a" * 64},
        "sources": {"ablations.jsonl": {"sha256": "1" * 64}},
    }
    # Raw bytes changed (new timestamps/latencies), science did not.
    same_science = dict(
        base,
        sources={"ablations.jsonl": {"sha256": "2" * 64}},
    )
    assert _digest(base) == _digest(same_science)
    changed_science = dict(
        base,
        scientific_sources={"ablations.jsonl": "b" * 64},
    )
    assert _digest(base) != _digest(changed_science)


def test_digest_ignores_timing_criteria_but_performance_digest_does_not():
    details = _details("t")
    details["criteria"] = {
        "C1": True,
        "C6_general_cost_mean_seconds": 1.0,
        "C7_fixture_cost_mean_seconds": 0.5,
    }
    base = {
        "conclusion": "SUPPORTED",
        "conclusion_details": details,
        "performance": {
            "run_seconds": 1.0,
            "conclusion_criteria": {
                "C6_general_cost_mean_seconds": 1.0,
                "C7_fixture_cost_mean_seconds": 0.5,
            },
        },
    }
    slower = {
        "conclusion": "SUPPORTED",
        "conclusion_details": {
            **details,
            "criteria": {
                **details["criteria"],
                "C6_general_cost_mean_seconds": 9.0,
                "C7_fixture_cost_mean_seconds": 3.0,
            },
        },
        "performance": {
            "run_seconds": 17.0,
            "conclusion_criteria": {
                "C6_general_cost_mean_seconds": 9.0,
                "C7_fixture_cost_mean_seconds": 3.0,
            },
        },
    }
    assert _digest(base) == _digest(slower)
    assert _performance_digest(base, []) != _performance_digest(slower, [])


def test_digest_uses_normalized_artifact_content_not_raw_bytes():
    base = {"conclusion": None, "conclusion_details": None}
    artifact = {
        "name": "table:ablations.md",
        "sha256": "1" * 64,
        "size_bytes": 100,
        "content_sha256": "a" * 64,
    }
    timing_only = {
        **artifact,
        "sha256": "2" * 64,
        "size_bytes": 101,
    }
    changed_content = {**artifact, "content_sha256": "b" * 64}
    assert _digest(base, artifacts=[artifact]) == _digest(
        base, artifacts=[timing_only]
    )
    assert _performance_digest(base, [artifact]) != _performance_digest(
        base, [timing_only]
    )
    assert _digest(base, artifacts=[artifact]) != _digest(
        base, artifacts=[changed_content]
    )


def test_performance_digest_changes_when_only_source_timings_change():
    base = {
        "conclusion": None,
        "conclusion_details": None,
        "sources": {"ablations.jsonl": {"sha256": "1" * 64}},
        "performance": {
            "run_seconds": 1.0,
            "source_timings": {"ablations.jsonl": {"verification_seconds": [1.0]}},
        },
    }
    slower = {
        **base,
        "performance": {
            "run_seconds": 2.0,
            "source_timings": {"ablations.jsonl": {"verification_seconds": [2.0]}},
        },
    }
    assert _digest(base) == _digest(slower)
    assert _performance_digest(base, []) != _performance_digest(slower, [])


# ---------------------------------------------------------------------------
# CLI reproduction modes
# ---------------------------------------------------------------------------

import importlib  # noqa: E402
import json  # noqa: E402

import crest.cli as cli  # noqa: E402
from experiments.generalization import config as experiment_config  # noqa: E402
from experiments.generalization import provenance  # noqa: E402

_EXPERIMENT_FUNCTIONS = {
    "experiments.generalization.ablations": "run_all",
    "experiments.generalization.cross_distribution": "run_grid",
    "experiments.generalization.exposure_sweep": "run_all",
    "experiments.generalization.confidence_sensitivity": "run_all",
    "experiments.generalization.drift_experiment": "run",
}


def _no_pip_freeze(monkeypatch):
    monkeypatch.setattr(cli, "_package_versions", lambda: None)


def _stub_file_metadata(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_file_metadata",
        lambda path_value: {
            "path": str(path_value),
            "sha256": "ab" * 32,
            "size_bytes": 42,
        },
    )
    # Keep CLI-mode tests independent of the developer's stored results.
    monkeypatch.setattr(
        provenance,
        "scientific_jsonl_digest",
        lambda path_value: "cd" * 32,
    )
    monkeypatch.setattr(provenance, "timing_values", lambda path_value: {})


def _stub_experiments(monkeypatch, order, fail_module=None, calls=None):
    for module_name, function_name in _EXPERIMENT_FUNCTIONS.items():
        module = importlib.import_module(module_name)

        def _stub(*args, _name=module_name, **kwargs):
            order.append(_name)
            if calls is not None:
                calls[_name] = kwargs
            if _name == fail_module:
                raise RuntimeError("stubbed experiment failure")

        monkeypatch.setattr(module, function_name, _stub)


def _stub_conclusion(monkeypatch, order=None):
    module = importlib.import_module("experiments.generalization.conclusion")
    fixed = {
        "verdict": "SUPPORTED",
        "reason": "stub",
        "criteria": {},
        "generated_at": "t",
    }

    def _evaluate():
        if order is not None:
            order.append("conclusion")
        return dict(fixed)

    monkeypatch.setattr(module, "evaluate", _evaluate)


def _forbid_tables(monkeypatch):
    module = importlib.import_module("experiments.generalization.tables")

    def _forbidden(**kwargs):
        raise AssertionError("canonical tables must not be written by this mode")

    monkeypatch.setattr(module, "write_all", _forbidden)


def _manifest(tmp_path):
    manifests = sorted((tmp_path / "reproduce_manifests").glob("reproduce_*.json"))
    assert len(manifests) == 1
    return json.loads(manifests[0].read_text(encoding="utf-8"))


def test_quick_reproduction_never_writes_research_artifacts(tmp_path, monkeypatch):
    _no_pip_freeze(monkeypatch)
    _stub_file_metadata(monkeypatch)
    _stub_conclusion(monkeypatch)
    _forbid_tables(monkeypatch)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["research", "reproduce"]) == 0
    manifest = _manifest(tmp_path)
    assert manifest["manifest_version"] == 3
    assert manifest["experiment_config"]["source"] == "canonical"
    assert manifest["experiment_config"]["samples"] == 20
    assert manifest["experiment_config"]["canonical"] is True
    assert (
        manifest["experiment_config"]["config_digest"]
        == experiment_config.canonical().digest()
    )
    assert manifest["tables"]["status"] == "not_run"
    assert manifest["sources"]["ablations.jsonl"]["status"] == "ok"
    assert manifest["conclusion"] == "SUPPORTED"


def test_quick_reproduction_without_stored_results_fails(tmp_path, monkeypatch):
    _no_pip_freeze(monkeypatch)
    monkeypatch.setattr(cli, "_file_metadata", lambda path_value: None)
    _stub_conclusion(monkeypatch)
    _forbid_tables(monkeypatch)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["research", "reproduce"]) == 2
    manifest = _manifest(tmp_path)
    assert any(
        "no stored ablation results" in failure
        for failure in manifest["failures"]
    )


def test_failed_conclusion_is_reported_and_exits_nonzero(tmp_path, monkeypatch):
    _no_pip_freeze(monkeypatch)
    _stub_file_metadata(monkeypatch)
    module = importlib.import_module("experiments.generalization.conclusion")

    def _boom():
        raise RuntimeError("stubbed failure")

    monkeypatch.setattr(module, "evaluate", _boom)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["research", "reproduce"]) == 2
    manifest = _manifest(tmp_path)
    assert manifest["conclusion"] is None
    assert any(
        "Conclusion evaluation failed" in failure
        for failure in manifest["failures"]
    )
    assert manifest["result_digest"]


def test_full_reproduction_runs_experiments_first_then_writes_tables(tmp_path, monkeypatch):
    _no_pip_freeze(monkeypatch)
    _stub_file_metadata(monkeypatch)
    order: list[str] = []
    calls: dict[str, dict] = {}
    _stub_experiments(monkeypatch, order, calls=calls)
    _stub_conclusion(monkeypatch, order)
    fake_dir = tmp_path / "fake-tables"
    fake_dir.mkdir()
    (fake_dir / "ablations.md").write_text("| a |\n|---|\n", encoding="utf-8")

    tables_module = importlib.import_module("experiments.generalization.tables")

    def _fake_write_all(**kwargs):
        order.append("tables")
        return {
            "dir": str(fake_dir),
            "files": ["ablations.md"],
            "sha256": {"ablations.md": "0" * 64},
            "config_digest": "config-digest",
        }

    monkeypatch.setattr(tables_module, "write_all", _fake_write_all)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["research", "reproduce", "--full"]) == 0
    assert order == [
        "experiments.generalization.ablations",
        "experiments.generalization.cross_distribution",
        "experiments.generalization.exposure_sweep",
        "experiments.generalization.confidence_sensitivity",
        "experiments.generalization.drift_experiment",
        "conclusion",
        "tables",
    ]
    manifest = _manifest(tmp_path)
    assert manifest["manifest_version"] == 3
    assert manifest["result_digest"]
    assert manifest["performance_digest"]
    assert "scientific_sources" in manifest
    assert "performance" in manifest
    assert manifest["tables"]["status"] == "written"
    assert manifest["experiment_config"]["source"] == "canonical"
    # Canonical full runs must let each experiment resolve its own canonical
    # parameter. Passing the ablation n=20 to confidence (canonical 6) or
    # cross-distribution (canonical 8) silently produces non-canonical data.
    assert calls == {
        "experiments.generalization.ablations": {},
        "experiments.generalization.cross_distribution": {},
        "experiments.generalization.exposure_sweep": {},
        "experiments.generalization.confidence_sensitivity": {},
        "experiments.generalization.drift_experiment": {},
    }
    assert all(
        value == "ok" for value in manifest["full_experiments"].values()
    )
    assert [artifact["name"] for artifact in manifest["artifacts"]] == [
        "table:ablations.md"
    ]


def test_full_reproduction_with_failed_experiment_skips_tables(tmp_path, monkeypatch):
    _no_pip_freeze(monkeypatch)
    _stub_file_metadata(monkeypatch)
    order: list[str] = []
    _stub_experiments(
        monkeypatch,
        order,
        fail_module="experiments.generalization.ablations",
    )
    _stub_conclusion(monkeypatch, order)
    _forbid_tables(monkeypatch)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["research", "reproduce", "--full"]) == 2
    manifest = _manifest(tmp_path)
    assert manifest["tables"]["status"] == "skipped"
    assert "failures" in manifest["tables"]
    assert any("ablations" in failure for failure in manifest["failures"])


def test_samples_override_is_reported_and_skips_canonical_tables(tmp_path, monkeypatch):
    _no_pip_freeze(monkeypatch)
    _stub_file_metadata(monkeypatch)
    order: list[str] = []
    calls: dict[str, dict] = {}
    _stub_experiments(monkeypatch, order, calls=calls)
    _stub_conclusion(monkeypatch, order)
    _forbid_tables(monkeypatch)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["research", "reproduce", "--full", "--samples", "2"]) == 0
    manifest = _manifest(tmp_path)
    assert manifest["experiment_config"]["source"] == "cli-override"
    assert manifest["experiment_config"]["samples"] == 2
    assert manifest["experiment_config"]["canonical"] is False
    assert manifest["tables"]["status"] == "skipped"
    assert "canonical" in manifest["tables"]["reason"]
    # Explicit overrides are applied uniformly to the sample-count arms and
    # never to the fixed-budget experiments.
    assert calls["experiments.generalization.ablations"] == {"n": 2}
    assert calls["experiments.generalization.confidence_sensitivity"] == {"n": 2}
    assert calls["experiments.generalization.cross_distribution"] == {"samples": 2}
    assert calls["experiments.generalization.exposure_sweep"] == {}
    assert calls["experiments.generalization.drift_experiment"] == {}


def test_samples_override_equal_to_canonical_is_still_noncanonical(
    tmp_path, monkeypatch
):
    _no_pip_freeze(monkeypatch)
    _stub_file_metadata(monkeypatch)
    order: list[str] = []
    _stub_experiments(monkeypatch, order)
    _stub_conclusion(monkeypatch, order)
    _forbid_tables(monkeypatch)
    monkeypatch.chdir(tmp_path)

    canonical_samples = experiment_config.canonical().samples
    assert cli.main(
        [
            "research",
            "reproduce",
            "--full",
            "--samples",
            str(canonical_samples),
        ]
    ) == 0
    manifest = _manifest(tmp_path)
    assert manifest["experiment_config"]["source"] == "cli-override"
    assert manifest["experiment_config"]["samples"] == canonical_samples
    assert manifest["experiment_config"]["canonical"] is False
    assert manifest["tables"]["status"] == "skipped"


def test_samples_override_requires_full_mode(capsys):
    assert cli.main(["research", "reproduce", "--samples", "2"]) == 2
    assert "--samples requires --full" in capsys.readouterr().err
