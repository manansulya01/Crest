"""Offline validation harness for Cycle 4.

Consumes a recorded dataset (list of dicts conforming to
experiments/datasets/cycle4/schema.json) and reproduces policy metrics without
network access.

No live calls are made. No provider is contacted.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from experiments.benchmark.evidence_integrity import (
    DEFAULT_CONFIG,
    Calibration,
    EvidenceItem,
    Task,
    calibrate,
    claim_confidence,
    decide,
    policy_no_verify,
    policy_single_cheap,
    policy_single_strong,
    policy_fixed_cascade,
    policy_strong_high_risk_gate,
)

POLICY_REGISTRY = {
    "no_verify": policy_no_verify,
    "single_cheap": policy_single_cheap,
    "single_strong": policy_single_strong,
    "fixed_cascade": policy_fixed_cascade,
    "strong_high_risk_gate": policy_strong_high_risk_gate,
}


@dataclass
class RecordedExample:
    task_id: str
    risk_class: str
    ground_truth_label: str  # correct | incorrect | indeterminate
    generator_output: Optional[str]
    verifier_output: Optional[str]
    provenance: Dict[str, Any]
    category: str = "A"
    input_text: str = ""
    reference: str = ""

    @property
    def truth(self) -> Optional[bool]:
        if self.ground_truth_label == "correct":
            return True
        if self.ground_truth_label == "incorrect":
            return False
        return None


def load_recorded_dataset(path: Path) -> List[RecordedExample]:
    """Load a JSONL or JSON array of recorded examples."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        rows = json.loads(text)
    examples = []
    for row in rows:
        examples.append(RecordedExample(
            task_id=row["task_id"],
            risk_class=row["risk_class"],
            ground_truth_label=row["ground_truth_label"],
            generator_output=row.get("generator_output"),
            verifier_output=row.get("verifier_output"),
            provenance=row.get("provenance", {}),
            category=row.get("category", "A"),
            input_text=row.get("input", ""),
            reference=row.get("reference", ""),
        ))
    return examples


def _verdict_from_output(output: Optional[str]) -> Optional[bool]:
    if output is None:
        return None
    lowered = output.strip().lower()
    if "correct" in lowered and "incorrect" not in lowered:
        return True
    if "incorrect" in lowered:
        return False
    return None


def example_to_task(example: RecordedExample, index: int) -> Task:
    """Map a recorded example to a simulator Task.

    Ancestry is derived from provenance: if the generator and verifier share a
    model family, they are treated as one cluster. This is a design choice
    documented in the Cycle 4 protocol.
    """
    family = example.provenance.get("source_family", "unknown")
    verdict = _verdict_from_output(example.verifier_output)
    ancestry = (family,) if family != "unknown" else None

    cheap = EvidenceItem(
        evidence_id=f"{example.task_id}:cheap_judge:0",
        kind="cheap_judge",
        family=family,
        ancestry=ancestry,
        scope=(0, 1),
        verdicts=(verdict, verdict),
        cost=DEFAULT_CONFIG.costs["cheap_judge"],
    )
    items = [cheap]

    # If a strong verifier output exists, add it as a separate item with the
    # same family ancestry (shared failure mode) unless provenance says otherwise.
    strong_family = example.provenance.get("strong_family", family)
    strong_ancestry = (strong_family,) if strong_family != "unknown" else None
    if example.provenance.get("strong_output") is not None:
        strong_verdict = _verdict_from_output(example.provenance["strong_output"])
        items.append(EvidenceItem(
            evidence_id=f"{example.task_id}:strong_judge:0",
            kind="strong_judge",
            family=strong_family,
            ancestry=strong_ancestry,
            scope=(0, 1),
            verdicts=(strong_verdict, strong_verdict),
            cost=DEFAULT_CONFIG.costs["strong_judge"],
        ))

    risk = example.risk_class if example.risk_class in ("low", "med", "high") else "med"
    return Task(
        task_id=example.task_id,
        seed=0,
        split="evaluation",
        risk=risk,
        difficulty=0.5,
        subclaim_correct=(True, True),  # placeholder; not used by policies
        det_applicable=False,
        ext_available=False,
        evidence=items,
    )


def run_offline(
    examples: Sequence[RecordedExample],
    policy_names: Sequence[str] = ("single_strong", "strong_high_risk_gate"),
    calibration: Optional[Calibration] = None,
) -> Dict[str, List]:
    """Run the named policies on recorded examples. Returns decisions per policy."""
    if calibration is None:
        calibration = Calibration(
            prior_subclaim=0.75,
            rel_det=0.99,
            rel_cheap=0.65,
            rel_strong=0.65,
            rel_ext=0.85,
            rel_format=0.60,
            rel_unknown=0.50,
        )
    results: Dict[str, List] = {name: [] for name in policy_names}
    for index, example in enumerate(examples):
        task = example_to_task(example, index)
        for name in policy_names:
            policy = POLICY_REGISTRY[name]
            result = policy(task, calibration, DEFAULT_CONFIG)
            results[name].append({
                "task_id": example.task_id,
                "decision": result.decision,
                "cost": result.cost,
                "confidence": result.confidence,
                "ground_truth": example.ground_truth_label,
            })
    return results


def stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]