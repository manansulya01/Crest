# CREST Invention Ledger

## Classification key
- **Established prior art**: Known technique with published evidence.
- **New integration**: Combining existing techniques in a new way.
- **New mechanism**: A genuinely new technical approach.
- **New experimentally demonstrated capability**: A mechanism with reproducible evidence.
- **Unverified research hypothesis**: An idea not yet tested.

---

## Entry 1: Adaptive Verification (AV)

**Date:** 2026-11-03
**Status:** Unverified research hypothesis → New experimentally demonstrated capability (pending experiment)

### Unsolved problem
Verification of AI outputs is currently binary: either always run (expensive) or never run (unsafe). There is no mechanism to allocate verification effort based on task uncertainty, risk, or available evidence. This means either wasting compute on easy tasks or missing errors on hard tasks.

### Why existing approaches are insufficient
- **FrugalGPT** (Chen et al., 2023): Uses a cascade (try cheap, verify, escalate) but verification is a single threshold — no adaptation to task risk or uncertainty.
- **Hybrid LLM** (ICLR 2024): Routes based on predicted difficulty, but verification is binary (accept/reject).
- **CREST cascade experiment**: Structural verification (schema check) cannot detect semantic errors. Model-based verification is expensive. No middle ground exists.
- **TensorZero** (archived): Had structured inference with schema enforcement, but no adaptive verification.

### Proposed mechanism
Adaptive Verification allocates verification effort across a spectrum:
1. **Tier 0 (free):** Schema/structural check (JSON parse, required fields, types).
2. **Tier 1 (cheap):** Cross-field consistency check (e.g., sum + tax == total).
3. **Tier 2 (moderate):** Semantic check via a smaller/cheaper model (e.g., ask a cheap model "does this answer look correct?").
4. **Tier 3 (expensive):** Full model-based verification (ask a strong model to verify).

The tier is selected based on:
- Task risk (from task metadata or historical failure rate).
- Uncertainty (from model confidence or output entropy).
- Budget remaining (from the budget guard).
- Historical verification yield (does verification at this tier catch errors?).

### Technical distinctiveness
Unlike FrugalGPT's cascade (which always runs the same verification), Adaptive Verification
dynamically selects verification depth based on task characteristics and budget constraints.
This is a control-theoretic approach: verification is a resource to be allocated optimally.

### Falsifiable hypothesis
H1: Adaptive Verification achieves the same task success as "always verify at Tier 3"
    with lower total verification cost, by using cheaper tiers for low-risk tasks.

H0: Adaptive Verification does not reduce verification cost without reducing success rate.

### Prior art closest
- FrugalGPT (cascade with fixed verification)
- Adaptive computation time (Graves, 2016) — allocates compute per token
- Conformal prediction — provides uncertainty estimates for routing
- Selective classification — abstains when uncertain

### Measurable property
Verification cost per task (in cost units) at equal task success rate.

### Failure conditions
- If verification tiers cannot distinguish easy from hard tasks, adaptive allocation
  provides no benefit.
- If Tier 0/1 verification is too weak to catch errors, the system must escalate
  to expensive tiers, eliminating savings.
- If the cost of determining uncertainty exceeds the savings from adaptive allocation,
  the mechanism is not economical.

### Experimental plan
See docs/v1.1-adaptive-verification-experiment.md (created).

---

## Entry 2: Value-of-Verification (VoV) controller

**Date:** 2026-11-03
**Status:** Experimentally demonstrated in simulation only — **not promoted to production**

### Mechanism
Multi-tier verification (T0 structural, T1 consistency, T2 cheap-model judge, T3 strong-model judge) with action selection by expected reduction in decision risk per unit cost, and an uncertainty estimate that incorporates verifier false-positive rates (residual uncertainty) to avoid accepting on weak evidence.

### Closest prior art
- FrugalGPT (cascade with fixed verification)
- Adaptive computation time (Graves, 2016)
- Selective classification (Geifman & El-Yaniv)
- Value of Information (Howard, 1966)
- Sequential Probability Ratio Test (Wald, 1945) — closest to the SEA successor

### Classification
**New integration**, not a new fundamental mechanism. Nearest neighbours on all axes already exist in the literature.

### Reproducible results (fixed seeds, after cross-process determinism fix)
5 seeds × 200 evaluation tasks:

| Strategy | Success | Cost/success |
|---|---|---|
| always-T0 | 0.751 | 1.33 |
| always-T3 | 0.951 | 7.36 |
| fixed cascade | 0.907 | 2.85 |
| **VoV** | **0.968** | **3.30** |
| SEA (sequential) | 0.921 | 2.82 |

### What it beats and what it does not
- Strictly dominates **always-T3** (higher success, less than half the cost). This is the important, honest win.
- Beats fixed cascade on **success** (+6.1pp) but **not** on cost-per-success (3.30 vs 2.85).
- Loses to a hypothetical "accept after T2, never escalate" on cost-per-success (≈2.2, but at ~0.66 success and 10% false-acceptance) — the quality-frugality trade-off is unavoidable.
- Narrows but persists under **perfectly correlated verifier errors** (0.935 success / 3.18 cps; matches always-T3 at less than half cost).

### Falsified claims
- Original report numbers were **not reproducible across processes** because Python's `hash()` on strings is randomized per interpreter; fixed via SHA-256-based `_stable_seed`. Corrected numbers above.
- "VoV dominates the cascade" is false — it dominates only the strong baseline.
- Any claim of live-provider or real-world superiority is **unverified** (strong model unavailable; T2 judge simulated).

### Decision
**Do not promote.** Keep as research; validate only after a live T2-judge correlation check (needs explicit spending authorization).

---

## Entry 3: Sequential Evidence Accumulation (SEA)

**Date:** 2026-11-04
**Status:** Unverified research hypothesis tested — negative/narrow result; retained as a mechanism reference

### Mechanism
Bayesian/SPRT-style accumulation of log-likelihood-ratio evidence from sequential verifier verdicts; asymmetric-loss stopping bounds `L ≥ +log(FA/FR)` (accept) and `L ≤ −log(FA/FR)` (escalate), where FA scales with task risk and FR is the escalation cost. Risk-class priors calibrated on the calibration split only.

### Results
5 seeds × 200 evaluation tasks: **0.921 success, 2.82 cost per success** — matches the fixed cascade on cost (2.85) and modestly beats its quality; strictly worse than VoV on quality (VoV 0.968).

### Classification
**New integration** of sequential testing with risk-weighted verification allocation. Not a breakthrough; confirms the cascade is already near the achievable cost boundary on this simulator.

### Failure conditions / limitations
- Requires a calibrated base rate per risk class and approximately calibrated verifier FPRs.
- Under correlated verifier errors the LLR over-counts evidence; gains erode.
- Simulation-only; no live validation.

### Decision
Retain as a principled reference / comparison point. Do not pursue as product lead.

---

## Entry 4: Evidence Integrity Gate (EIG)

**Date:** 2026-11-04
**Status:** Experimentally demonstrated in simulation — **NARROW** result; high-risk veto only.

### Unsolved problem

Multiple agreeing checks do not imply independent evidence. Two verifiers may share an underlying model, a source, a prompt, or a bias, and a system that counts them as independent confirmations can become confidently wrong. CREST needed a mechanism that reasons about what evidence establishes, where it came from, and whether the combined evidence is sufficient for a particular decision.

### Proposed mechanism

A provenance-aware evidence-integrity gate:

1. Represent evidence as items with ancestry (source family), claim scope (which subclaims they cover), reliability, and freshness.
2. Cluster evidence by ancestry; one cluster contributes at most one independent unit of support (common-cause discount).
3. Pool unknown-provenance items into a single weak cluster with reliability capped at 0.5 (never assume independence).
4. Aggregate assurance per required subclaim; claim confidence is the weakest link (scope gating).
5. Apply risk-dependent accept/reject thresholds.
6. **Narrow gate:** use the strong verifier normally on low/medium risk; require provenance-aware sufficiency (≥ 0.98) before accepting on high risk.

### Closest prior art

- Provenance semirings (Green, Karvounarakis, Tannen, PODS 2007).
- GSN assurance cases (Kelly & Weaver, 2004).
- Common-cause Bayesian networks (Li et al.; Sun et al., 2021).
- LLM-as-judge reliability (Zheng et al. 2023; Landesberg et al. 2025; JudgeBench).
- Quorum/BFT (Cowling et al. 2006).

Classification: **new integration**. The novelty is the runtime combination of provenance discounting, unknown-dependency conservatism, scope gating, and a risk-weighted execution decision.

### Reproducible results (holdout, 5 seeds × 500 evaluation tasks)

| Policy | Success | Coverage | FAR | Loss/task |
|---|---:|---:|---:|---:|
| single_strong | 0.741 | 1.000 | 0.076 | 0.699 |
| fixed_cascade | 0.758 | 1.000 | 0.192 | 0.890 |
| **strong_high_risk_gate** | **0.610** | **0.813** | **0.059** | **0.518** |
| provenance_aware | 0.259 | 0.285 | 0.058 | 0.569 |
| provenance_sequential | 0.235 | 0.264 | 0.067 | 0.585 |

The gate reduces risk-weighted loss by **25.9%** vs the strong verifier, at matched decision quality among decided tasks (0.750 vs 0.741) and 81% coverage, with 22.9% lower false acceptance.

### What it beats and what it does not

- Beats `single_strong` on risk-weighted loss (0.518 vs 0.699) and FAR (0.059 vs 0.076) at matched decided-quality and ≥80% coverage.
- Does **not** beat `single_strong` on raw success or coverage (0.610 vs 0.741; 81% vs 100%).
- The fully provenance-aware policy (Candidate B) is too conservative (28.5% coverage) and is not recommended as a general policy.
- Under unknown provenance, the fully provenance-aware policies collapse to 0% coverage; the narrow gate survives (81% coverage, 7.6% FAR).

### Falsified claims / limitations

- "Evidence integrity replaces the strong verifier" is false — it is a veto, not a replacement.
- False provenance (forged ancestry metadata) is a trust assumption the mechanism cannot detect.
- The 2.8pp FAR increase under the shared-model condition slightly exceeds the 2pp safety threshold.
- Simulation-only; no live validation.

### Decision

**NARROW.** Adopt the high-risk veto for further validation (Cycle 4 live probe). Do not build the full Evidence Integrity Engine until the live correlation structure is known.

---

## Entry 5: Cycle 4 — Live Validation Readiness

**Date:** 2026-11-04
**Status:** Ready for authorization — no live calls made.

### What was done

- Reconstructed and audited the Cycle 3 claim (`research/CYCLE4_CLAIM_RECONSTRUCTION.md`).
- Designed a labeled evaluation dataset protocol (`research/CYCLE4_DATASET_PROTOCOL.md`, `experiments/datasets/cycle4/schema.json`).
- Designed the statistical analysis (`research/CYCLE4_STATISTICAL_ANALYSIS.md`).
- Designed the live probe protocol (`research/CYCLE4_LIVE_PROBE_PROTOCOL.md`).
- Built an offline validation harness (`experiments/benchmark/cycle4_validation.py`, `cycle4_metrics.py`) with 7 tests.
- Defined pre-registered promotion criteria.
- No live calls, no spending, no commits, no pushes.

### Decision

**READY FOR AUTHORIZATION.** The experiment is designed; execution requires explicit user authorization.
