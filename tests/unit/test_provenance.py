"""Tests for the scientific-content digest boundary.

Raw experiment files contain wall-clock observations and machine provenance.
These tests pin down exactly what is excluded: timing, timestamps, and
machine identity are excluded; parameters, sample counts, classifications,
metrics, and failures are retained.
"""
from __future__ import annotations

import json

from experiments.generalization import provenance


def _write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_normalize_json_excludes_timing_and_machine_metadata_only():
    value = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "git_commit": "abc",
        "branch": "main",
        "os": "Windows",
        "python_version": "3.12",
        "crest_version": "0.4.0",
        "verifier_version": "v1",
        "config": {"n": 20, "canonical": True},
        "results": [
            {
                "verification_seconds": 1.25,
                "passed": True,
                "success_rate": 0.99,
            }
        ],
        "nested": {"seconds": 2.0, "revocation_latency_ms": 3.0, "kept": 4},
    }
    assert provenance.normalize_json(value) == {
        "config": {"n": 20, "canonical": True},
        "results": [{"passed": True, "success_rate": 0.99}],
        "nested": {"kept": 4},
    }


def test_scientific_jsonl_digest_is_stable_across_timings(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_jsonl(
        first,
        [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "config": {"n": 20, "canonical": True},
                "rows": [{"passed": 3, "seconds": 1.0}],
            }
        ],
    )
    _write_jsonl(
        second,
        [
            {
                "timestamp": "2026-10-19T12:00:00+00:00",
                "config": {"n": 20, "canonical": True},
                "rows": [{"passed": 3, "seconds": 9.5}],
            }
        ],
    )
    assert provenance.scientific_jsonl_digest(
        first
    ) == provenance.scientific_jsonl_digest(second)


def test_scientific_jsonl_digest_changes_with_meaningful_content(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_jsonl(
        first,
        [
            {
                "config": {"n": 20, "canonical": True},
                "rows": [{"passed": 3, "seconds": 1.0}],
            }
        ],
    )
    _write_jsonl(
        second,
        [
            {
                "config": {"n": 20, "canonical": True},
                "rows": [{"passed": 2, "seconds": 1.0}],
            }
        ],
    )
    assert provenance.scientific_jsonl_digest(
        first
    ) != provenance.scientific_jsonl_digest(second)


def test_scientific_jsonl_digest_returns_none_for_missing_or_bad_file(tmp_path):
    missing = tmp_path / "missing.jsonl"
    assert provenance.scientific_jsonl_digest(missing) is None
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n", encoding="utf-8")
    assert provenance.scientific_jsonl_digest(bad) is None


def test_markdown_normalization_ignores_timing_and_provenance():
    first = (
        "<!-- crest-table schema=1 config_digest=x canonical=true "
        "sources=a=sha256:1 -->\n\n"
        "| action | cost (s) | class |\n"
        "|---|---|---|\n"
        "| delete | 1.25 | VERIFIED_FAMILY |\n"
    )
    second = (
        "<!-- crest-table schema=1 config_digest=x canonical=true "
        "sources=a=sha256:2 -->\n\n"
        "| action | cost (s) | class |\n"
        "|---|---|---|\n"
        "| delete | 9.50 | VERIFIED_FAMILY |\n"
    )
    assert provenance.scientific_artifact_digest(
        "ablations.md", first
    ) == provenance.scientific_artifact_digest("ablations.md", second)


def test_markdown_normalization_preserves_meaningful_cells():
    first = (
        "| action | cost (s) | class |\n"
        "|---|---|---|\n"
        "| delete | 1.25 | VERIFIED_FAMILY |\n"
    )
    changed = (
        "| action | cost (s) | class |\n"
        "|---|---|---|\n"
        "| delete | 1.25 | VERIFIED_FIXTURE |\n"
    )
    assert provenance.scientific_artifact_digest(
        "ablations.md", first
    ) != provenance.scientific_artifact_digest("ablations.md", changed)


def test_combined_markdown_handles_multiple_timing_headers():
    first = (
        "<!-- crest-table schema=1 -->\n\n"
        "## ablations\n"
        "| action | cost (s) | class |\n"
        "|---|---|---|\n"
        "| delete | 1.0 | GENERAL |\n\n"
        "## drift\n"
        "| class | detection latency (ms) | detected |\n"
        "|---|---|---|\n"
        "| moved | 2.5 | yes |\n"
    )
    second = (
        "<!-- crest-table schema=1 -->\n\n"
        "## ablations\n"
        "| action | cost (s) | class |\n"
        "|---|---|---|\n"
        "| delete | 8.0 | GENERAL |\n\n"
        "## drift\n"
        "| class | detection latency (ms) | detected |\n"
        "|---|---|---|\n"
        "| moved | 7.5 | yes |\n"
    )
    assert provenance.scientific_artifact_digest(
        "all_tables.md", first
    ) == provenance.scientific_artifact_digest("all_tables.md", second)


def test_artifact_digest_is_line_ending_independent():
    text = (
        "| action | cost (s) | class |\n"
        "|---|---|---|\n"
        "| delete | 1.0 | GENERAL |\n"
    )
    crlf = text.replace("\n", "\r\n")
    assert provenance.scientific_artifact_digest(
        "ablations.md", text
    ) == provenance.scientific_artifact_digest("ablations.md", crlf)


def test_csv_normalization_ignores_verification_seconds():
    first = (
        "mode,action,verification_seconds,evidence_class\n"
        "fixture_only,delete,1.0,VERIFIED_FIXTURE\n"
    )
    second = (
        "mode,action,verification_seconds,evidence_class\n"
        "fixture_only,delete,99.0,VERIFIED_FIXTURE\n"
    )
    assert provenance.scientific_artifact_digest(
        "ablations.csv", first
    ) == provenance.scientific_artifact_digest("ablations.csv", second)


def test_timing_values_collects_only_observations(tmp_path):
    path = tmp_path / "rows.jsonl"
    _write_jsonl(
        path,
        [
            {
                "rows": [
                    {"verification_seconds": 1.0, "passed": 1},
                    {"verification_seconds": 2.0, "passed": 2},
                ],
                "seconds": 3.0,
                "passed": 3,
            }
        ],
    )
    assert provenance.timing_values(path) == {
        "seconds": [3.0],
        "verification_seconds": [1.0, 2.0],
    }
