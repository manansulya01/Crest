# Cycle 4 — Statistical Analysis Plan

## 1. Primary endpoint

Risk-weighted loss per task at a predefined minimum coverage of 80%.

The gate is compared against the strongest simple baseline (single strong verifier)
using a paired analysis where both policies are evaluated on the same tasks.

## 2. Secondary endpoints

- False acceptance rate (FAR).
- False rejection rate (FRR).
- Coverage (1 − abstention rate).
- Selective risk (FAR among accepted tasks).
- Cost per task and cost per successful decision.
- Latency (if measured).
- Abstention frequency and escalation frequency.
- Error dependence between generator and verifier.

## 3. Uncertainty

- Binary outcomes: Wilson 95% confidence intervals.
- Paired policy comparisons: paired bootstrap (10,000 resamples) or paired
  permutation test. Report the 95% CI of the difference in loss.
- Do not treat repeated generations of the same task as independent examples.
  If a task is evaluated multiple times, cluster by task ID.
- Account for task-category imbalance by reporting per-category results.

## 4. Minimum sample size

Assumptions (from simulation and literature):
- Baseline risk-weighted loss ≈ 0.70/task (single_strong).
- Minimum detectable improvement: 15% relative (0.105/task).
- σ of per-task loss ≈ 1.5 (from simulation).
- Paired design, two-sided α = 0.05, power = 0.80.

Required paired samples: n ≈ (1.96 + 0.84)^2 × σ^2 / δ^2 ≈ 7.84 × 2.25 / 0.0110 ≈ 1600.

With task clustering (effective sample size reduced by intra-task correlation),
recommend **at least 2000 sealed tasks** for a definitive claim. With 500 tasks,
the study is a feasibility probe only (INCONCLUSIVE if underpowered).

## 5. Multiple comparisons

If more than two policies are compared, apply Holm-Bonferroni correction.
The primary comparison (gate vs single_strong) is the only confirmatory test;
all others are exploratory.

## 6. Decision rule (pre-registered)

Promote to live validation only if ALL of:
1. Coverage ≥ 80%.
2. Risk-weighted loss reduction ≥ 15% relative to single_strong (paired, 95% CI
   excludes zero).
3. FAR does not increase by more than 2pp.
4. Decided-task accuracy within 2pp of single_strong.
5. Cost overhead ≤ 20%.
6. Reproducible across repeated analysis runs.

If criteria 1–2 pass but 3–6 fail: REDESIGN.
If criteria 1–2 fail: REJECT or NARROW.
If sample size is insufficient to decide: INCONCLUSIVE.