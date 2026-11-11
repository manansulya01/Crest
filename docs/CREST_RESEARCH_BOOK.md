# CREST Research Book: Risk-Adaptive Execution Assurance

## A Monograph on Building an AI Execution Control Plane That Knows When Its Evidence Is Insufficient

**Version:** 0.4.0 (research-grade)
**Date:** 2026-11-10
**Repository:** `feat/crest-v0.4-research-complete`
**License:** See repository

---

# Part I — The Problem

## 1. The Evolution of AI Inference

Large language models (LLMs) have transformed from research curiosities into production
infrastructure. In 2023–2024, the dominant pattern was simple: send a prompt to a model,
receive a response, display it to the user. By 2025, the pattern had evolved into
**agentic execution**: models call tools, modify files, query databases, send messages,
and make decisions on behalf of users.

This shift created a new class of problems. When a model merely generates text, an error
is a quality issue. When a model executes actions, an error is an **incident**. A wrong
answer in a chatbot is embarrassing; a wrong action in an autonomous agent is destructive.

The infrastructure for managing AI inference has not kept pace with this shift. Most
systems still treat inference as a single call: prompt in, response out, hope for the
best. There is no systematic mechanism for deciding whether the response is good enough
to act on, whether the evidence supporting it is trustworthy, or whether the cost of
verification is justified by the risk of the action.

## 2. Why Conventional Model Selection Is Insufficient

The first wave of AI infrastructure optimization focused on **routing**: send easy tasks
to cheap models and hard tasks to expensive ones. This is a reasonable starting point,
but it has fundamental limitations:

- **Task difficulty is not observable.** The system must predict difficulty from
  features (text length, topic, etc.), and these predictions are noisy. A task that
  looks simple may be adversarial; a task that looks complex may be trivial.
- **Cost-quality trade-offs are not linear.** A cheap model that is 80% accurate may
  be worthless for a task requiring 99% accuracy, and a 99% accurate model may be
  wasteful for a task tolerating 80%.
- **Verification is binary.** Most systems either verify always (expensive) or never
  (unsafe). There is no spectrum.
- **Evidence is treated as opaque.** A system that counts "the model said X" and "the
  verifier said X" as two independent confirmations is vulnerable to common-mode
  failure: if both use the same underlying model, their agreement is not independent
  evidence.

CREST was built to address these limitations, not by replacing routing, but by adding
a layer of **execution assurance** that asks: is the evidence sufficient to justify
this action, given its risk and cost?

## 3. The Economics of Inference

AI inference has a cost structure unlike traditional software:

- **Variable cost per request.** Unlike CPU-bound services with near-zero marginal
  cost, LLM inference costs scale with tokens processed. A 10-token classification
  costs fractions of a cent; a 10,000-token reasoning chain costs dollars.
- **Quality is not monotonic in cost.** A $0.001 model may be 70% accurate; a $0.01
  model may be 85%; a $0.10 model may be 90%. The marginal quality per dollar
  decreases, but the absolute quality matters more than the marginal cost.
- **Verification has its own cost-quality curve.** A cheap verifier (small model) may
  catch 60% of errors; an expensive verifier (large model) may catch 95%. The
  verification cost must be justified by the risk of the unverified error.
- **Budgets are hard constraints.** An agent with a $1.00 budget cannot spend $1.50
  on verification, even if verification would prevent a $10.00 error. The system must
  make the best decision within the budget.

## 4. The Quality, Latency, and Cost Problem

Every AI execution decision involves a three-way trade-off:

- **Quality:** How likely is the output to be correct?
- **Latency:** How long does execution take?
- **Cost:** How much does execution cost?

These three are not independent. Higher quality generally requires more compute
(higher cost, higher latency). But the relationship is not smooth: there are
discontinuities where a small increase in cost yields a large quality improvement
(e.g., adding a verifier to an unverified pipeline), and regions where large cost
increases yield marginal quality gains.

CREST's goal is not to optimize this trade-off in the abstract, but to make it
**explicit and auditable**: for every execution, record what was done, what it cost,
what evidence was collected, and why the decision was made. This allows downstream
analysis, learning, and accountability.

---

# Part II — The Research Landscape

## 5. Research Direction 1: Adaptive Verification

**Problem:** Verification is binary (always or never). There is no mechanism to
allocate verification effort based on task uncertainty, risk, or budget.

**Existing approaches:**
- FrugalGPT (Chen et al., 2023): cascade (try cheap, verify, escalate) with a
  single threshold.
- Hybrid LLM (ICLR 2024): routes based on predicted difficulty, binary
  verification.
- Selective classification (Geifman & El-Yaniv): abstains when uncertain.

**CREST contribution:** Adaptive verification allocates verification across tiers
(T0 structural, T1 consistency, T2 cheap-model judge, T3 strong-model judge)
based on task risk, uncertainty, and budget. Implemented in
`experiments/benchmark/adaptive_verification.py`.

**Result:** Simulated quality improvement, but cost-quality trade-offs were not
sufficient to establish real-world superiority. Status: unverified hypothesis.

## 6. Research Direction 2: Value of Verification (VoV)

**Problem:** When should you verify? Verification costs money; skipping it risks
errors. The optimal policy depends on the cost of errors, the cost of verification,
and the reliability of the verifier.

**Mechanism:** Multi-tier verification with action selection by expected reduction
in decision risk per unit cost. The controller estimates the value of information
of each verification action and selects the highest-value action within budget.

**Results (simulation, 5 seeds × 200 tasks):**
| Strategy | Success | Cost/success |
|---|---:|---:|
| Always T0 | 0.751 | 1.33 |
| Always T3 | 0.951 | 7.36 |
| Fixed cascade | 0.907 | 2.85 |
| **VoV** | **0.968** | **3.30** |
| SEA | 0.921 | 2.82 |

VoV strictly dominates always-T3 (higher success, less than half the cost). It beats
the fixed cascade on success (+6.1pp) but not on cost-per-success (3.30 vs 2.85).
Under perfectly correlated verifier errors, VoV's edge narrows (0.935/3.18).

**Prior art:** Value of Information (Howard, 1966), SPRT (Wald, 1945), FrugalGPT.
**Classification:** New integration, not a new fundamental mechanism.

## 7. Research Direction 3: Sequential Evidence Accumulation (SEA)

**Problem:** Can sequential likelihood-ratio accumulation produce a compelling
advantage over a fixed cascade?

**Mechanism:** Bayesian/SPRT-style accumulation of log-likelihood-ratio evidence
from sequential verifier verdicts. Asymmetric-loss stopping bounds:
`L ≥ +log(FA/FR)` (accept), `L ≤ −log(FA/FR)` (escalate), where FA scales with
task risk.

**Result:** 0.921 success / 2.82 cost-per-success — matches the fixed cascade on
cost (2.85) and modestly beats its quality. Strictly worse than VoV on quality.
Requires calibrated base rates per risk class and calibrated verifier FPRs.

**Prior art:** SPRT (Wald, 1945), sequential probability ratio tests.
**Classification:** New integration. Retained as a principled reference baseline.

## 8. Research Direction 4: Verifier Reliability and Error Correlation

**Problem:** The cheap verifier's actual reliability and its error correlation
with the generator are unknown. No live provider calls were made in Cycles 1–3.

**Key finding:** Correlated verifier errors erode the gains of adaptive
verification. Under perfectly correlated errors, VoV's edge narrows and SEA
degrades toward the cascade. The simulation shows that the quality-frugality
trade-off is unavoidable.

**Status:** Blocked on live validation (spending authorization required).

## 9. Research Direction 5: Evidence Integrity and Provenance

**Problem:** Multiple agreeing checks do not imply independent evidence. Two
verifiers may share an underlying model, source, prompt, or bias.

**Mechanism:** Represent evidence as a structured object with explicit provenance,
dependencies, scope, and limitations. Cluster evidence by ancestry; one cluster
contributes at most one independent unit of support. Unknown provenance is pooled
into a weak cluster (reliability capped at 0.5). Aggregate assurance per
subclaim; claim confidence is the weakest link.

**Prior art:** Provenance semirings (Green et al., 2007), GSN assurance cases
(Kelly & Weaver, 2004), common-cause Bayesian networks (Li et al.; Sun et al.,
2021), LLM-as-judge reliability (Zheng et al., 2023; Landesberg et al., 2025).

**Classification:** New integration. The novelty is the runtime combination of
provenance discounting, unknown-dependency conservatism, scope gating, and a
risk-weighted execution decision.

## 10. Research Direction 6: Risk-Adaptive Verification and High-Risk Veto

**Problem:** Can a risk-adaptive gate reduce harmful acceptance decisions?

**Mechanism (Strong High-Risk Gate):** Trust the strong verifier on low/medium-risk
tasks (full coverage). On high-risk tasks, require provenance-aware sufficiency
(≥ 0.98 confidence) before acceptance; otherwise abstain (INDETERMINATE).

**Results (holdout, 5 seeds × 500 tasks):**
| Policy | Success | Coverage | FAR | Loss/task |
|---|---:|---:|---:|---:|
| single_strong | 0.741 | 1.000 | 0.076 | 0.699 |
| **strong_high_risk_gate** | **0.610** | **0.813** | **0.059** | **0.518** |
| provenance_aware | 0.259 | 0.285 | 0.058 | 0.569 |

25.9% risk-weighted loss reduction, 22.9% FAR reduction, at matched decided-quality
(0.750 vs 0.741) and 81% coverage. 10% higher cost.

**Decision:** NARROW. The gate works as a high-risk veto but not as a general
policy.

## 11. Research Direction 7: Cost-Constrained Execution

**Problem:** Budgets are hard constraints. An agent with a $1.00 budget cannot
spend $1.50 on verification.

**CREST approach:** Budget reservation before inference (no inference without
budget reservation). Cost tracking with `cost_known` flag (unknown usage is never
represented as known cost). Budget exhaustion blocks further attempts. Retry
limits with backoff. Implemented in `src/crest/inference.py`.

**Key invariant:** No silent model substitution. Unknown usage must not be
represented as known cost.

## 12. Research Direction 8: Statistical Validation and Sealed Evaluation

**Problem:** Simulation results can be circular or overfit. Need rigorous
evaluation with proper splits.

**CREST approach:** Calibration/evaluation split disjointness. Held-out task IDs
isolated. SHA-256-based deterministic seeds (never Python `hash()`). Wilson
confidence intervals. Pre-registered success criteria. Adversarial conditions
(duplicate, shared-source, unknown provenance, false provenance, scope mismatch,
distribution shift, cost exhaustion, correlated failure, stale evidence).

## 13. Research Direction 9: Evidence Provenance

**Problem:** Can evidence provenance be represented with enough precision to
identify when several apparent confirmations ultimately depend on the same
original information?

**CREST approach:** Evidence items carry ancestry (source family), scope (which
subclaims they cover), reliability, and freshness. Dependency clusters are
derived from ancestry. The formal model (E1/E2/E3) defines the aggregation rules.

## 14. Research Direction 10: Dependency-Aware Inference

**Problem:** How should a system update confidence when evidence sources are
dependent, partially independent, or have unknown relationships?

**CREST approach:** Bayesian aggregation over ancestry clusters. Unknown
dependencies are pooled into a single weak cluster (never treated as independent).
The min (weakest-link) rule for claim confidence. Risk-dependent thresholds.

## 15. Research Direction 11: Safety Engineering and Assurance Cases

**Problem:** Can AI execution decisions be supported by structured arguments
connecting claims, evidence, assumptions, and rebuttals?

**CREST approach:** Goal Structuring Notation (GSN)-inspired claim-evidence-
assumption structure. Each execution produces an auditable record of what was
claimed, what evidence supported it, what was assumed, and why the decision was
made. Implemented via receipts (`src/crest/receipts.py`) and the audit log.

## 16. Research Direction 12: Information Theory and Causal Reasoning

**Problem:** Can CREST measure whether a new verification result provides
genuinely new information or merely repeats what it already knows?

**CREST approach:** The provenance clustering mechanism (E1) directly addresses
this: a duplicate source provides zero new information. The information gain of
acquiring evidence from a new source family is higher than from a known source.
This is implicit in the cluster model (one unit per cluster).

## 17. Research Direction 13: Formal Methods and Software Verification

**Problem:** Can the system distinguish claims established by deterministic checks
from claims supported only by probabilistic model judgments?

**CREST approach:** Deterministic checks (det_rule, reliability ~0.99) are
categorically stronger than probabilistic judgments (cheap judge, ~0.65). The
simulator models this distinction: a deterministic check on the numeric subclaim
is treated as near-certain, while judge verdicts are probabilistic. The
provenance model preserves this distinction.

## 18. Research Direction 14: AI Verification and Multi-Agent Reliability

**Problem:** When does agreement among AI systems constitute useful independent
evidence, and when is it merely correlated repetition?

**CREST approach:** The core finding of Cycle 3. Agreement is useful only when
the verifiers are independent (different source families). Shared-family
agreement is discounted to a single unit. The simulation shows that this
discounting reduces false acceptance under shared-source attacks.

## 19. Research Direction 15: Distributed Systems and Trust

**Problem:** Can evidence integrity borrow useful ideas from distributed systems
without incorrectly treating AI model outputs as independent replicas?

**CREST approach:** Byzantine fault tolerance assumes independent replicas and
majority agreement. AI verifiers are stochastic, correlated, and non-identical —
majority vote logic does not transfer directly. CREST borrows the *concept* of
fault domains (source families) but uses probabilistic aggregation instead of
quorum voting. Quorum size ≥3 still cannot detect a shared-cause error; this is
why provenance tracking is necessary.

---

# Part III — The Opportunity

## 20. Research Synthesis

Across 4 research cycles, CREST has:

1. **Falsified routing** as a cost-reduction strategy (Cycle 1). Task features
   cannot predict difficulty well enough to route cheaply.
2. **Demonstrated VoV** as a mechanism that dominates always-T3 (Cycle 2), but
   not the fixed cascade on cost-per-success.
3. **Invented the evidence-integrity gate** (Cycle 3), which reduces risk-weighted
   loss by 25.9% as a high-risk veto.
4. **Prepared for live validation** (Cycle 4) without making any live calls.

The key insight: **the value is not in making better predictions, but in knowing
when you don't have enough evidence to make a prediction.** The high-risk gate
works by abstaining when evidence is insufficient, not by being smarter.

## 21. Identified Gaps

- No live validation of any claim. All results are simulation.
- The strong model (`gemini-3.8-flash`) is unavailable.
- The T2-judge probe (Cycle 2) remains blocked on spending authorization.
- The full Evidence Integrity Engine is too conservative for general use.
- False provenance (forged metadata) is undetectable without authenticated
  provenance.

## 22. Design Hypotheses

- H1: A high-risk acceptance veto reduces harmful acceptances in real systems.
- H2: Provenance-derived independence is a better predictor of verification
  value than model agreement count.
- H3: Unknown provenance should be treated as weak evidence (capped at 0.5),
  not as independent support.
- H4: Scope gating (per-subclaim assurance) prevents false acceptance on
  partially supported claims.

## 23. Original Technical Contribution

The **Strong High-Risk Gate**: a risk-adaptive execution assurance mechanism that
applies provenance-aware sufficiency checking only to high-risk accepts, preserving
the strong verifier's coverage on lower-risk tasks. This is a new integration of:
- Provenance-derived independence discounting (E1)
- Unknown-dependency conservatism (E2)
- Claim-level scope gating (E3)
- Risk-dependent acceptance thresholds
- A narrow veto that does not replace the base verifier

## 24. Why CREST Takes This Direction

CREST's differentiation is not in routing (falsified) or in general verification
(too expensive). It is in **knowing when evidence is insufficient** — a capability
that is both technically novel (as an integration) and practically valuable (it
reduces harmful acceptances by 23% at 81% coverage).

---

# Part IV — The Architecture

## 25. Overall Architecture

```
Task → Plan → Execute → Capture Evidence → Build Provenance → Evaluate Sufficiency → Decide → Record Outcome
```

CREST is an execution control plane, not a model gateway. It sits between the
agent and the tools, deciding whether an action is justified by the available
evidence.

## 26. Key Components

- **Runtime** (`src/crest/runtime.py`): Admission control, budget management,
  receipt validation.
- **Inference** (`src/crest/inference.py`): Budget reservation, retries,
  cost tracking, `cost_known` flag.
- **Evidence** (`src/crest/evidence.py`): Evidence capture and classification.
- **Receipts** (`src/crest/receipts.py`): Content-addressed, versioned receipts
  with Ed25519 signatures.
- **Policy** (`src/crest/policy.py`): Evidence classes, Wilson bounds, admission
  thresholds.
- **Admission** (`src/crest/admission.py`): Capability admission decisions.
- **Ledger** (`src/crest/ledger.py`): Audit trail, persistence.
- **Gateway** (`src/crest/gateway.py`): Tool gateway, MCP-style interface.
- **Verifier** (`src/crest/verifier.py`): Verification logic.
- **Recovery** (`src/crest/recovery.py`): Failure recovery.
- **Redaction** (`src/crest/redaction.py`): Secret redaction.

## 27. Execution Lifecycle

1. Agent requests an action.
2. CrestRuntime checks admission: is the capability granted? Is the receipt valid?
   Is the budget sufficient? Is the scope correct?
3. If admitted, the adapter executes the action.
4. Evidence is captured and stored.
5. Audit record is written.
6. Result is returned to the agent.

## 28. Decision-Making

Decisions are: ACCEPT, REJECT, REQUEST_MORE_EVIDENCE, ESCALATE, INDETERMINATE.
Each decision is accompanied by a reason and an audit record.

## 29. Data Flow

```
agent request → ToolGateway → CrestRuntime.check() → admission decision
  → adapter execution → evidence capture → audit write → result
```

## 30. Failure Handling

- Fail-closed on corrupt state, unknown tools, scope violations, budget exhaustion.
- Revocation is immediate; re-admission requires fresh verification.
- Scope drift detection: target must remain within admitted scope.

## 31. Mathematical Formulation

See `research/EVIDENCE_INTEGRITY_FORMAL_MODEL.md` for the full formal model.
Key equations:

- Cluster contribution: `P(at least one correct independent source) = 1 − (1 − a)^m`
  where `m` = number of independent clusters, `a` = per-source accuracy.
- Unknown-provenance cap: confidence from unknown sources ≤ 0.5.
- Scope gating: claim confidence = min over required subclaims.
- Decision: `ACCEPT if confidence ≥ threshold[risk]`, else `REJECT if ≤ reject_threshold`, else `INDETERMINATE`.

---

# Part V — Implementation

## 32. Engineering Decisions

- **Python 3.11+**, setuptools, PyYAML only. Minimal dependencies.
- **SQLite** for persistence, append-only audit log.
- **Content-addressed receipts** with Ed25519 signatures (dev keys in `.crest/keys/`).
- **Deterministic seeds** via SHA-256 (never Python `hash()`).
- **Fail-closed** on all error paths.
- **No silent model substitution.** Unknown usage is never represented as known cost.

## 33. Important Modules

See Section 26. Key modules: `runtime.py`, `inference.py`, `evidence.py`,
`receipts.py`, `policy.py`, `admission.py`, `ledger.py`.

## 34. Trade-offs

- Determinism vs. flexibility: SHA-256 seeds ensure reproducibility but limit
  randomization.
- Safety vs. usability: fail-closed prevents harm but may block legitimate actions.
- Cost vs. quality: the high-risk gate improves safety at 10% higher cost.

## 35. Difficult Problems and Solutions

- **Reproducibility:** Python's `hash()` is randomized per process. Fixed with
  SHA-256-based `_stable_seed`.
- **Correlated verifier errors:** Majority voting overcounts. Fixed with
  provenance clustering.
- **Unknown provenance:** Treating unknown sources as independent inflates
  confidence. Fixed with the 0.5 cap and single-cluster pooling.
- **Scope mismatch:** Evidence about one property doesn't establish another.
  Fixed with per-subclaim aggregation (weakest link).

---

# Part VI — Experiments

## 36. Experimental Design

All experiments are simulation-based with explicit assumptions. No live calls.
Four research cycles:

- Cycle 1: Adaptive verification (unverified hypothesis).
- Cycle 2: VoV and SEA (VoV dominates always-T3; does not beat fixed cascade
  on cost-per-success).
- Cycle 3: Evidence integrity (NARROW: high-risk veto, 25.9% loss reduction).
- Cycle 4: Validation readiness (dataset protocol, statistical design, live
  probe protocol, offline harness).

## 37. Baselines

- no_verify, single_det, single_cheap, single_strong, majority_vote,
  fixed_cascade, naive_count, blind_bayes, provenance_aware, blind_sequential,
  provenance_sequential, contradiction_driven, strong_high_risk_gate, oracle.

## 38. Benchmark Results

See `docs/v1.3-evidence-integrity-experiment.md` for full results. Summary:

| Policy | Success | Coverage | FAR | Loss/task |
|---|---:|---:|---:|---:|
| single_strong | 0.741 | 1.000 | 0.076 | 0.699 |
| strong_high_risk_gate | 0.610 | 0.813 | 0.059 | 0.518 |
| provenance_aware | 0.259 | 0.285 | 0.058 | 0.569 |

## 39. Ablations

- Duplicate attack: provenance-aware confidence unchanged when duplicate added.
- Shared-family: one cluster, not two.
- Unknown provenance: capped at 0.5, pooled into one cluster.
- Scope mismatch: out-of-scope evidence ignored.
- Distribution shift: gate degrades gracefully.
- Cost exhaustion: 0% accept, 100% INDETERMINATE.

## 40. Statistical Analysis

Wilson 95% CIs. Paired bootstrap (10,000 resamples). Pre-registered criteria.
Minimum 2000 sealed tasks for definitive claim.

## 41. Interpretation

The high-risk gate reduces risk-weighted loss by 25.9% at 81% coverage and matched
decided-quality. The benefit comes from abstaining on high-risk tasks where
evidence is insufficient, not from being smarter. This is a narrow but real
advantage.

---

# Part VII — Final Results

## 42. What Works

- Execution control plane with budget enforcement, receipt validation, audit log.
- Adaptive verification (simulated).
- VoV (dominates always-T3).
- Evidence-integrity gate (25.9% loss reduction as high-risk veto).
- Reproducible experiments with sealed evaluation.
- 424 tests passing.

## 43. What Was Demonstrated

- Simulation evidence for adaptive verification, VoV, SEA, and the evidence-integrity gate.
- Reproducibility across processes (SHA-256 seeds).
- Adversarial robustness of the gate (duplicate, shared-source, unknown provenance,
  scope mismatch, distribution shift, cost exhaustion).

## 44. What Remains Limited

- No live validation. All results are simulation.
- Strong model unavailable.
- T2-judge probe blocked on spending authorization.
- False provenance undetectable.
- Full Evidence Integrity Engine too conservative.

## 45. What Is Genuinely Novel

The Strong High-Risk Gate: a new integration of provenance-derived independence
discounting, unknown-dependency conservatism, scope gating, and risk-dependent
acceptance thresholds, applied as a narrow high-risk veto. Not a new fundamental
mechanism, but a new combination with demonstrated (simulated) advantage.

## 46. What CREST Contributes

CREST contributes a framework for **risk-adaptive execution assurance**: the idea
that AI systems should track not just whether verification passed, but whether
the evidence supporting a decision is sufficient, independent, and in scope — and
should abstain when it is not.

---

# Part VIII — Complete Technical Reference

## 47. Installation

```bash
pip install -e .
cd your-project
crest init --root .
```

## 48. Configuration

See `crest.yaml` for configuration options. Key settings: budget, policy,
verification tiers.

## 49. Usage

```bash
crest verify --action modify_file --recovery restore_from_snapshot --target README.md --scope '*'
crest exec filesystem modify_file --arg path=README.md --arg content='hello'
crest status
crest audit
crest policy check --tool filesystem --operation delete_file --arg path=README.md
crest doctor
```

## 50. API

```python
from crest.runtime import CrestRuntime
from crest.gateway import ToolGateway, ToolRequest

rt = CrestRuntime.from_config("crest.yaml")
gw = ToolGateway(rt)
r = gw.execute(ToolRequest(agent_id="agent-1", tool="filesystem", operation="modify_file",
                           arguments={"path": "a.txt", "content": "x"}))
```

## 51. CLI Reference

See `src/crest/cli.py` for the full CLI. Commands: `init`, `verify`, `exec`,
`status`, `audit`, `policy`, `doctor`, `experiment`.

## 52. Examples

See `examples/runtime_demo.py` for a full pipeline demo including revocation.

## 53. Benchmark Reproduction

```bash
$env:PYTHONPATH="src;."
python experiments/benchmark/evidence_integrity.py
python -m pytest -q -p no:cacheprovider
```

## 54. Troubleshooting

- **Tests fail:** Ensure `PYTHONPATH="src;."` is set.
- **Import errors:** Install with `pip install -e .`.
- **Budget errors:** Check `crest.yaml` budget settings.
- **Receipt validation failures:** Ensure `.crest/keys/` exists (dev keys).

---

# References

1. Green, T.J., Karvounarakis, G., Tannen, V. "Provenance Semirings." PODS 2007.
2. Kelly, T., Weaver, R. "The Goal Structuring Notation." 2004.
3. Chen, L., et al. "FrugalGPT." 2023.
4. Wald, A. "Sequential Analysis." 1945 (SPRT).
5. Howard, R.A. "Information Value Theory." 1966.
6. Zheng, L., et al. "Judging LLM-as-a-Judge." 2023.
7. Geifman, Y., El-Yaniv, R. "Selective Classification." 2017.
8. Graves, A. "Adaptive Computation Time." 2016.
9. Li, et al. "Bayesian Network for Common Cause Failure." 2022.
10. Sun, et al. "Reliability Analysis under Common Cause Failures." RESS, 2021.

---

*This document was produced as part of the CREST research program. All experimental
results are simulation-based unless explicitly labeled otherwise. No live provider
calls were made during any research cycle.*