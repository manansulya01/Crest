"""Main research graph (V0.4).

Plots the measured frontier: autonomous coverage vs unsafe admission vs
verification cost, plus the exposure sweep. Requires matplotlib; the data
artifacts remain the JSONL/CSV files under experiments/results and
experiments/tables. This script only visualizes, it never generates data.

Usage: python -m experiments.generalization.frontier_plot
"""
from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1] / "results"
PLOTS = Path(__file__).resolve().parents[1] / "plots"


def _load(name: str) -> list[dict]:
    p = RESULTS / name
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"matplotlib unavailable: {exc}")
        return 0

    rows = _load("ablations.jsonl")
    ab = rows[0]["results"] if rows and "results" in rows[0] else rows
    modes = sorted({r["mode"] for r in ab})
    summary = {}
    for m in modes:
        sub = [r for r in ab if r["mode"] == m]
        admitted = [r for r in sub if r["admitted"]]
        summary[m] = {
            "coverage": len(admitted) / max(1, len(sub)),
            "unsafe": sum(1 for r in admitted if r["false_admission"]),
            "cost": sum(r["verification_seconds"] for r in sub) / max(1, len(sub)),
            "false_rejection": sum(1 for r in sub if r["false_rejection"]) / max(1, len(sub)),
        }

    PLOTS.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    ax = axes[0]
    for m in modes:
        s = summary[m]
        ax.scatter([s["coverage"]], [s["unsafe"]], s=90, label=f"{m} (cost {s['cost']:.1f}s)")
    ax.set_xlabel("autonomous coverage (fraction admitted)")
    ax.set_ylabel("unsafe admissions (measured count)")
    ax.set_title("Coverage vs unsafe admission by evidence policy")
    ax.legend(fontsize=8)

    ax = axes[1]
    sweep = _load("exposure_sweep.jsonl")
    if sweep:
        points = sweep[0].get("rows", [])
        ax.plot([p["aac"] for p in points], [p["certified_exposure"] / max(p["e_max"], 1e-9) for p in points],
                marker="o", label="certified/Emax")
        ax.set_xlabel("AAC")
        ax.set_ylabel("certified exposure / Emax")
        ax.set_title("Exposure sweep: coverage is bounded by budget")
        ax.axhline(1.0, color="r", linestyle="--", linewidth=1)
        ax.legend(fontsize=8)

    fig.tight_layout()
    out = PLOTS / "frontier.png"
    fig.savefig(out, dpi=140)
    print(f"wrote {out}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
