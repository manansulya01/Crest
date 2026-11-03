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
See docs/v1.1-adaptive-verification-experiment.md (to be created).
