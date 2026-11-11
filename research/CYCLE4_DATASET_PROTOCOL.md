# Cycle 4 — Dataset Protocol

**Status:** Design only. No live calls. No private data.

## 1. Purpose

Evaluate whether the Strong High-Risk Gate's simulated advantage survives real
model errors. The dataset must support independent correctness labels, generator
and verifier reliability estimation, and error-dependence measurement.

## 2. Task categories (objectively checkable)

| Category | Description | Ground-truth method | Risk classes |
|---|---|---|---|
| A. Arithmetic | Multi-step arithmetic with integer results | Independent computation | low/med/high |
| B. Structured extraction | Extract fields from a supplied passage | Manual validation + schema check | low/med/high |
| C. Classification | Label a short text into a predefined taxonomy | Predefined label + adjudication rule | low/med/high |
| D. Source-grounded QA | Answer a question using only a supplied passage | Verify claims against passage | med/high |
| E. Constraint satisfaction | Produce a schedule/plan meeting stated constraints | Independent constraint checker | med/high |
| F. Multi-step reasoning | Reasoning with independently checkable intermediate steps | Check each step | high |
| G. Ambiguous (indeterminate) | Tasks with no objectively correct answer | Label INDETERMINATE | low/med/high |

Prefer categories A–F. Use G only to test abstention behavior.

## 3. Ground-truth labeling

- Deterministic checks wherever possible (arithmetic, extraction, constraints).
- For source-grounded tasks, verify every factual claim against the supplied passage.
- For ambiguous tasks, label INDETERMINATE; do not force a correct/incorrect label.
- Ground truth must **not** come from the model being evaluated.
- Human review: 2 annotators + adjudicator; report Cohen's κ. No personal/sensitive data.

## 4. Dataset splits

| Split | Purpose | Size (target) | Touch policy |
|---|---|---|---|
| Development | Policy construction, threshold exploration | 200 | Free |
| Calibration | Reliability estimation | 200 | Free |
| Policy-selection | Select among candidate gates | 200 | Free |
| Sealed evaluation | Final reported metrics | 500+ | **Touch once, at the end** |

Prevent duplicate and near-duplicate examples from crossing splits (hash-based
deduplication on input text).

## 5. Per-example schema

See `experiments/datasets/cycle4/schema.json`.

Required fields:
- `task_id` (stable, SHA-256-derived)
- `category` (A–G)
- `risk_class` (low/med/high)
- `input` (task text)
- `reference` (expected output or passage)
- `correctness_criteria` (human-readable)
- `ground_truth_label` (correct/incorrect/indeterminate)
- `label_confidence` (0.0–1.0)
- `label_method` (deterministic/human_adjudicated)
- `generator_output` (recorded, nullable)
- `verifier_output` (recorded, nullable)
- `gate_decision` (recorded, nullable)
- `provenance` (source family, model ID, prompt hash)
- `split` (development/calibration/policy-selection/sealed)
- `evaluation_date` (ISO 8601, nullable)

## 6. Data hygiene

- No API keys, credentials, or private information in the dataset.
- No personal or sensitive data.
- Hash-based deduplication across splits.
- Document contamination risks (e.g., benchmark tasks that may appear in model training data).
- Record model version, prompt template hash, and decoding parameters for every recorded output.

## 7. Minimum dataset size

For the primary endpoint (risk-weighted loss reduction ≥15% at ≥80% coverage),
a paired comparison with ~500 sealed tasks provides ~80% power to detect a
15% relative reduction assuming a baseline loss of ~0.70/task and σ ≈ 1.5.
See `research/CYCLE4_STATISTICAL_ANALYSIS.md` for the full calculation.

If fewer than 500 tasks are available, the result is `INCONCLUSIVE`, not a
pass or fail.