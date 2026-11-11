# Cycle 4 — Claim Reconstruction and Audit

**Date:** 2026-11-04
**Cycle 3 report:** `docs/v1.3-evidence-integrity-experiment.md`
**Cycle 3 code:** `experiments/benchmark/evidence_integrity.py`
**Cycle 3 tests:** `tests/unit/test_evidence_integrity.py`

## 1. Reproduction of the Cycle 3 claim

The Strong High-Risk Gate was re-run on the holdout seeds {2024, 2025, 2026, 2027, 2028}
(2500 tasks) and reproduced the reported numbers:

| Policy | Success | Coverage | FAR | Loss/task |
|---|---:|---:|---:|---:|
| single_strong | 0.741 | 1.000 | 0.076 | 0.699 |
| strong_high_risk_gate | 0.610 | 0.813 | 0.059 | 0.518 |
| provenance_aware | 0.259 | 0.285 | 0.058 | 0.569 |

The holdout numbers match the development numbers within sampling noise. The
result is reproducible across seeds.

## 2. Definition audit

### Success
In the simulator, `success = (decision == ACCEPT and truth) or (decision ==
REJECT and not truth)`. This is **decision accuracy**, not accepted-and-correct
rate. The report also reports `accepted_and_correct_rate` (= accepts that are
correct / n) separately. The headline "Success" column is decision accuracy, which
means abstention (INDETERMINATE) counts as a failure. This penalizes
conservative policies. A more natural metric for a selective system would be
accepted-and-correct rate plus coverage. Both are reported; the primary
criterion uses risk-weighted loss, not success.

### False acceptance (FAR)
`FAR = P(ACCEPT | truth = False) = false_accepts / n_bad`. This is the standard
definition. The gate's FAR of 5.88% means 5.88% of bad claims are accepted.

### Coverage
`coverage = (n - indeterminate) / n`. The gate's 81.3% coverage means 18.7% of
tasks are abstained.

### Loss function
Risk-weighted: `loss = fa_cost[risk]` for false accept, `fr_cost[risk]` for false
reject, `indet_cost[risk]` for INDETERMINATE. Values: low (4/2/1), med (12/4/1.5),
high (50/8/2). The high-risk false-acceptance cost (50) is 25× the indeterminate
cost (2), which strongly rewards abstention on high-risk tasks. This is a
deliberate design choice: high-risk false acceptance is the most expensive error.

### Risk-class distribution
Approximately 50% low, 30% med, 20% high, sampled independently of difficulty.
Risk is observable to the policy (it is a task metadata field).

### Gate observable inputs
The gate sees: verdicts, scope, ancestry metadata (or UNKNOWN), risk class,
and calibrated priors (prior_subclaim, rel_det, rel_cheap, rel_strong, rel_ext,
rel_format, rel_unknown). It does **not** see latent difficulty, ground-truth
correctness, subclaim correctness, or family quality. Verified by
`test_policies_do_not_read_ground_truth`.

### Threshold selection
The accept/reject thresholds (A3_current: 0.85/0.92/0.98 accept, 0.15/0.08/0.03
reject) were selected after exploring 4 accept × 3 reject variants on development
seeds {42, 123, 456}. The holdout seeds {2024–2028} were not examined before
threshold selection, but the thresholds were tuned on development data. This is a
form of threshold optimization on development data. The holdout result (25.9%
loss reduction) mitigates but does not eliminate this concern. The live
experiment must pre-register thresholds before any data is examined.

### Strongest baseline
`single_strong` (loss 0.699) is the strongest non-oracle baseline. `fixed_cascade`
(0.890) is weaker. The gate is compared against `single_strong`.

### Abstention accounting
The loss function charges indeterminate cost (1.0–2.0), so abstention is
penalized but much less than false acceptance (4–50). This correctly models a
world where abstaining is costly but far less costly than a harmful acceptance.
The gate's 18.7% abstention rate costs ~0.37 per task in indeterminate loss,
while avoiding false accepts saves ~0.18 per task. The net is favorable because
high-risk false accepts are weighted 50×.

## 3. What is reproducible

- All numbers in the Cycle 3 report reproduce on holdout seeds.
- The simulator is deterministic across processes (SHA-256 seeds).
- The gate's advantage is consistent across all 5 holdout seeds (gate loss <
  single_strong loss in every seed).
- The 15 focused tests pass.

## 4. What is not established

1. **Real model behavior.** The simulation assumes a specific common-cause
   structure (shared family quality). Real LLM judges may have more complex,
   less structured correlations.
2. **The threshold is not pre-registered on truly unseen data.** It was selected
   on development seeds.
3. **The 2.8pp FAR increase under shared-model condition** slightly exceeds the
   2pp safety threshold.
4. **False provenance** is a trust assumption the mechanism cannot detect.
5. **Cost and latency** are simulated, not measured.

## 5. Implications for Cycle 4

The live experiment must:
- Use a pre-registered threshold (no tuning on evaluation data).
- Measure real judge FPR/FNR and error correlation with the generator.
- Test whether the gate's advantage survives real model errors.
- Distinguish feasibility evidence from statistically supported claims.
- Report sample-size limitations honestly.