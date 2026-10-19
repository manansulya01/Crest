"""Table generation integrity: provenance, validation, safe replacement.

Canonical tables may only be regenerated from results that record the
canonical configuration; reduced or malformed results must fail without
touching the existing artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from experiments.generalization import config, cross_distribution, tables


def _write_canonical_fixture(root: Path) -> Path:
    """Minimal source artifacts that record the canonical configuration."""
    cfg = config.canonical()
    rdir = root / "results"
    rdir.mkdir(parents=True, exist_ok=True)

    abl_rows = [
        {
            "mode": "fixture_only",
            "action": "delete_file",
            "family": "filesystem.single_file",
            "recovery": "restore_from_snapshot",
            "evidence_class": "VERIFIED_FIXTURE",
            "admitted": True,
            "evaluation_success": 1.0,
            "false_admission": False,
            "false_rejection": False,
            "verification_seconds": 0.1,
        },
        {
            "mode": "family_evidence",
            "action": "delete_file",
            "family": "filesystem.single_file",
            "recovery": "restore_from_snapshot",
            "evidence_class": "VERIFIED_FAMILY",
            "admitted": True,
            "evaluation_success": 1.0,
            "false_admission": False,
            "false_rejection": False,
            "verification_seconds": 0.2,
        },
    ]
    ablations_record = {
        "config": {
            "cases_per_measurement": cfg.samples,
            "maximum_failure_upper_bound": cfg.maximum_failure_upper_bound,
            "canonical": True,
            "config_digest": cfg.digest(),
        },
        "results": abl_rows,
    }
    (rdir / "ablations.jsonl").write_text(
        json.dumps(ablations_record) + "\n", encoding="utf-8"
    )

    cross_rows = [
        {
            "action": "delete_file",
            "family": "filesystem.single_file",
            "recovery_kind": "restore_from_snapshot",
            "distributions": {
                "training": {"success_rate": 1.0},
                "level2_holdout": {"success_rate": 1.0},
            },
            "config": {
                "samples_per_distribution": {
                    key: cfg.cross_distribution_samples
                    for key in cross_distribution.MEASURE_SAMPLE_KEYS
                },
                "canonical": True,
                "config_digest": cfg.digest(),
            },
        }
    ]
    (rdir / "cross_distribution.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in cross_rows), encoding="utf-8"
    )

    (rdir / "exposure_sweep.jsonl").write_text(
        json.dumps(
            {
                "canonical": True,
                "config_digest": cfg.digest(),
                "rows": [
                    {
                        "e_max": 0.1,
                        "executed": 4,
                        "denied": 0,
                        "certified_exposure": 0.1,
                        "aac": 1.0,
                        "gac": 0.0,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (rdir / "confidence_sensitivity.jsonl").write_text(
        json.dumps(
            {
                "n": cfg.confidence_samples,
                "canonical": True,
                "config_digest": cfg.digest(),
                "rows": [
                    {
                        "confidence": 0.95,
                        "action": "delete_file",
                        "family": "filesystem.single_file",
                        "recovery": "restore_from_snapshot",
                        "evidence_class": "VERIFIED_FIXTURE",
                        "admitted": True,
                        "evaluation_success": 1.0,
                        "false_admission": False,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (rdir / "drift.jsonl").write_text(
        json.dumps(
            {
                "cases_per_class": cfg.drift_cases_per_class,
                "canonical": True,
                "config_digest": cfg.digest(),
                "summary": {"cases": cfg.drift_cases_per_class},
                "outcomes": [
                    {
                        "drift_class": "target_moved",
                        "detected": True,
                        "implementation": "implemented",
                        "revocation_latency_ms": 0.5,
                        "detection_reason": "target identity changed",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return rdir


def test_build_all_produces_provenanced_tables_deterministically(tmp_path):
    rdir = _write_canonical_fixture(tmp_path)
    files = tables.build_all(results_dir=rdir)

    assert set(files) == {
        "cross_distribution.md",
        "ablations.md",
        "exposure_sweep.md",
        "confidence_sensitivity.md",
        "drift.md",
        "all_tables.md",
        "ablations.csv",
    }

    abl_provenance = files["ablations.md"].splitlines()[0]
    assert abl_provenance.startswith(f"<!-- crest-table schema={tables.TABLE_SCHEMA} ")
    assert f"config_digest={config.canonical().digest()}" in abl_provenance
    assert "canonical=true" in abl_provenance
    source_hash = hashlib.sha256((rdir / "ablations.jsonl").read_bytes()).hexdigest()
    assert f"ablations.jsonl=sha256:{source_hash}" in abl_provenance

    # Deterministic bytes: no wall-clock metadata in generated tables.
    assert tables.build_all(results_dir=rdir) == files


def test_write_all_stages_and_replaces_with_matching_hashes(tmp_path):
    rdir = _write_canonical_fixture(tmp_path)
    dest = tmp_path / "tables"
    dest.mkdir()
    (dest / "ablations.md").write_text("old content\n", encoding="utf-8")

    info = tables.write_all(dest=dest, results_dir=rdir)

    assert info["dir"] == str(dest)
    for name in info["files"]:
        on_disk = (dest / name).read_bytes()
        assert hashlib.sha256(on_disk).hexdigest() == info["sha256"][name]
    assert (dest / "ablations.md").read_text(encoding="utf-8").startswith("<!-- crest-table")
    # No staging leftovers.
    assert [p for p in dest.iterdir() if p.name.startswith(".crest-tables-")] == []


def test_missing_source_fails_without_touching_destination(tmp_path):
    rdir = _write_canonical_fixture(tmp_path)
    (rdir / "drift.jsonl").unlink()
    dest = tmp_path / "tables"
    dest.mkdir()
    sentinel = dest / "drift.md"
    sentinel.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(tables.MissingResultsError):
        tables.write_all(dest=dest, results_dir=rdir)

    assert sentinel.read_text(encoding="utf-8") == "sentinel\n"
    assert not (dest / "ablations.md").exists()
    assert [p for p in dest.iterdir() if p.name.startswith(".crest-tables-")] == []


def test_noncanonical_results_cannot_replace_canonical_tables(tmp_path):
    rdir = _write_canonical_fixture(tmp_path)
    record = json.loads((rdir / "ablations.jsonl").read_text(encoding="utf-8"))
    record["config"]["cases_per_measurement"] = 10
    record["config"]["canonical"] = False
    (rdir / "ablations.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    dest = tmp_path / "tables"
    dest.mkdir()
    sentinel = dest / "ablations.md"
    sentinel.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(tables.NonCanonicalResultsError) as excinfo:
        tables.write_all(dest=dest, results_dir=rdir)
    assert "ablations.jsonl" in str(excinfo.value)
    assert sentinel.read_text(encoding="utf-8") == "sentinel\n"

    # An explicit override is possible but marks the tables non-canonical.
    info = tables.write_all(dest=dest, results_dir=rdir, allow_noncanonical=True)
    assert info["files"]
    assert "canonical=false" in sentinel.read_text(encoding="utf-8")


def test_mismatched_config_digest_cannot_replace_canonical_tables(tmp_path):
    rdir = _write_canonical_fixture(tmp_path)
    record = json.loads((rdir / "ablations.jsonl").read_text(encoding="utf-8"))
    # Keep canonical flags and sample counts intact but record a configuration
    # digest that does not match the current canonical parameters.
    record["config"]["config_digest"] = "0" * 64
    (rdir / "ablations.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    dest = tmp_path / "tables"
    dest.mkdir()
    sentinel = dest / "ablations.md"
    sentinel.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(tables.NonCanonicalResultsError) as excinfo:
        tables.write_all(dest=dest, results_dir=rdir)
    assert "config_digest" in str(excinfo.value)
    assert sentinel.read_text(encoding="utf-8") == "sentinel\n"


def test_replace_failure_rolls_back_already_replaced_tables(tmp_path, monkeypatch):
    rdir = _write_canonical_fixture(tmp_path)
    dest = tmp_path / "tables"
    dest.mkdir()
    previous = {
        "ablations.md": "previous ablations\n",
        "all_tables.md": "previous all tables\n",
    }
    for name, text in previous.items():
        (dest / name).write_text(text, encoding="utf-8")

    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst):
        # Fail while moving the second newly staged table into place.
        if Path(src).parent.name.startswith(".crest-tables-new-"):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("simulated replacement failure")
        return real_replace(src, dst)

    monkeypatch.setattr(tables.os, "replace", flaky_replace)

    with pytest.raises(OSError, match="simulated replacement failure"):
        tables.write_all(dest=dest, results_dir=rdir)

    for name, text in previous.items():
        assert (dest / name).read_text(encoding="utf-8") == text
    assert sorted(p.name for p in dest.iterdir()) == sorted(previous)
    assert [p for p in dest.iterdir() if p.name.startswith(".crest-tables-")] == []


def test_malformed_results_fail_validation_and_preserve_previous_tables(tmp_path):
    rdir = _write_canonical_fixture(tmp_path)
    record = json.loads((rdir / "ablations.jsonl").read_text(encoding="utf-8"))
    del record["results"][0]["verification_seconds"]
    (rdir / "ablations.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    dest = tmp_path / "tables"
    dest.mkdir()
    sentinel = dest / "all_tables.md"
    sentinel.write_text("previous valid tables\n", encoding="utf-8")

    with pytest.raises(tables.TableValidationError):
        tables.write_all(dest=dest, results_dir=rdir)

    assert sentinel.read_text(encoding="utf-8") == "previous valid tables\n"
    assert [p for p in dest.iterdir() if p.name.startswith(".crest-tables-")] == []
