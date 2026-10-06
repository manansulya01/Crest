"""Generate research tables (Markdown + CSV) from experiment JSONL artifacts.

No numbers are invented: every cell comes from a result file under
experiments/results/.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

RESULTS = Path(__file__).resolve().parents[1] / "results"
TABLES = Path(__file__).resolve().parents[1] / "tables"
RESULTS.parent.mkdir(parents=True, exist_ok=True)


def _load(name: str) -> list[dict[str, Any]]:
    path = RESULTS / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def cross_distribution_table() -> str:
    rows = _load("cross_distribution.jsonl")
    if not rows:
        return "_no cross-distribution results_\n"
    dist_keys = list(rows[0]["distributions"].keys())
    header = "| action | family | recovery | " + " | ".join(dist_keys) + " |"
    sep = "|---|---|---|" + "---|" * len(dist_keys)
    out = [header, sep]
    for r in rows:
        cells = [f"{r['distributions'][k]['success_rate']:.2f}" for k in dist_keys]
        out.append(f"| {r['action']} | {r['family']} | {r['recovery_kind']} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def ablation_table() -> str:
    rows = _load("ablations.jsonl")
    rows = rows[0]["results"] if rows and "results" in rows[0] else rows
    if not rows:
        return "_no ablation results_\n"
    out = [
        "| mode | action | family | recovery | evidence class | admitted | eval success | false admission | false rejection | cost (s) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| {r['mode']} | {r['action']} | {r['family']} | {r['recovery']} | {r['evidence_class']} | "
            f"{r['admitted']} | {r['evaluation_success']:.2f} | {r['false_admission']} | {r['false_rejection']} | {r['verification_seconds']} |"
        )
    return "\n".join(out) + "\n"


def exposure_sweep_table() -> str:
    rows = _load("exposure_sweep.jsonl")
    rows = rows[0]["rows"] if rows and "rows" in rows[0] else rows
    if not rows:
        return "_no exposure sweep results_\n"
    out = ["| E_max | executed | denied | certified exposure | AAC | GAC |", "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['e_max']} | {r['executed']} | {r['denied']} | {r['certified_exposure']} | {r['aac']} | {r['gac']} |")
    return "\n".join(out) + "\n"


def confidence_table() -> str:
    rows = _load("confidence_sensitivity.jsonl")
    rows = rows[0]["rows"] if rows and "rows" in rows[0] else rows
    if not rows:
        return "_no confidence sensitivity results_\n"
    out = ["| confidence | action | family | recovery | evidence class | admitted | eval success | false admission |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['confidence']} | {r['action']} | {r['family']} | {r['recovery']} | {r['evidence_class']} | "
                   f"{r['admitted']} | {r['evaluation_success']:.2f} | {r['false_admission']} |")
    return "\n".join(out) + "\n"


def drift_table() -> str:
    rows = _load("drift.jsonl")
    rows = rows[0] if rows else None
    if not rows:
        return "_no drift results_\n"
    out = ["| drift class | detected | implementation | detection latency (ms) | reason |", "|---|---|---|---|---|"]
    for o in rows["outcomes"]:
        lat = o["revocation_latency_ms"]
        out.append(f"| {o['drift_class']} | {o['detected']} | {o['implementation']} | {lat if lat is not None else '-'} | {o['detection_reason'][:48]} |")
    out.append("")
    out.append("summary: " + json.dumps(rows["summary"]))
    return "\n".join(out) + "\n"


def write_all() -> Path:
    TABLES.mkdir(parents=True, exist_ok=True)
    sections = {
        "cross_distribution.md": cross_distribution_table(),
        "ablations.md": ablation_table(),
        "exposure_sweep.md": exposure_sweep_table(),
        "confidence_sensitivity.md": confidence_table(),
        "drift.md": drift_table(),
    }
    combined = ["# Crest V0.4 result tables (generated)", ""]
    for name, body in sections.items():
        combined.append(f"## {name[:-3].replace('_', ' ')}")
        combined.append(body)
        (TABLES / name).write_text(body, encoding="utf-8")
    out = TABLES / "all_tables.md"
    out.write_text("\n".join(combined), encoding="utf-8")

    # CSV of ablation rows for spreadsheets
    rows = _load("ablations.jsonl")
    if rows:
        ab = rows[0]["results"] if "results" in rows[0] else rows
        with (TABLES / "ablations.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(ab[0].keys()))
            writer.writeheader()
            writer.writerows(ab)
    return out


if __name__ == "__main__":
    print(f"wrote {write_all()}")