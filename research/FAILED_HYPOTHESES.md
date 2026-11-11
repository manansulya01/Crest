# CREST — Failed / Falsified Hypotheses

Negative results are preserved deliberately. Each entry lists the claim, why it
failed, and what survives.

## 1. CREST pre-inference routing / model selection beats baselines

**Claim:** Routing tasks to cheap vs strong models based on task features lowers
cost at equal quality.

**Verdict: Falsified** for this workload class.

- Non-circular simulation (`experiments/benchmark/simulation.py`, 5 signal strengths × 5 seeds × 200 tasks): CREST never beats the simple cost-aware baseline on cost-per-success; escalation rate pinned at 100% because nobody passes the 0.05 admission threshold with a nonzero cheap-model failure rate.
- Fake-mode 50% saving was **circular** (the routing feature `multi_topic` is exactly the condition under which the fake cheap model fails). See `docs/v0.9-simulation-audit.md`.

**Survives:** the measurement pipeline and budget/audit machinery; nothing about routing quality.

## 2. Cascade (verify-then-escalate) strictly dominates pre-routing

**Claim:** Verify-then-escalate beats pre-inference routing because features are imperfect.

**Verdict: Narrowly true on quality only, not on cost-per-success.**

- Cascade success 0.907 vs VoV 0.968; cascade cps 2.85 vs VoV 3.30.
- Structural verification cannot detect semantic errors (wrong category in valid JSON), so cascades without a model judge cannot protect quality either.

## 3. VoV dominates the fixed cascade

**Claim (original VoV report):** VoV is the best strategy.

**Verdict: False as stated.**

- Dominates always-T3 strictly (0.968/3.30 vs 0.951/7.36) — genuine win.
- vs fixed cascade: +6.1pp success but +16% cost-per-success. Not dominant.
- Prior numerical claims were **not reproducible** because of `hash()` randomization; fixed with SHA-256 `_stable_seed`.

## 4. Adaptive / sequential verification works without calibrated verifier reliabilities

**Claim:** More evidence is always better.

**Verdict: Only partially true.**

- Adaptive Verification and SEA both depend on approximately calibrated verifier false-positive/false-negative rates and a class-level base rate.
- Under perfectly correlated verifier errors, LLR over-counts evidence; VoV's edge narrows (0.935/3.18) and SEA degrades toward the cascade.
- Any live deployment must measure the cheap-model judge's error rate **and its correlation with the generator's errors**; if correlation ≈ independence, gains are real; if not, escalate directly and skip the fake adaptivity.

## 5. More calibration samples always help admission

**Verdict: True but bounded.**

- With zero observed failures one needs ≥52 calibration successes per class at 95% one-sided and threshold 0.05 (Wilson bound; verified numerically: n=51 → 0.0504, n=52 → 0.0495).
- If the true failure rate exceeds ~5%, no amount of data admits the class — correct behaviour, but it means routing value is inherently capped by model quality.

## 6. Structural verification is sufficient for safety

**Verdict: Falsified.**

- The fake cheap model emits valid JSON with wrong field values; schema checks pass, semantic errors pass through.
- Required for any pass claim: a model judge (with measured reliability) or an external ground-truth constraint.

## 8. Full Evidence Integrity Engine as a general decision policy

**Claim:** A provenance-aware aggregator that discounts duplicate and shared-source
evidence makes better execution decisions than a strong verifier at comparable
cost.

**Verdict: Failed as a general policy; narrowed to a high-risk veto.**

- Full provenance-aware policy: safe (FAR 5.8%) but too conservative (28.5%
  coverage, 71.5% INDETERMINATE, 3.55 cost/task). It does not replace a
  strong verifier; it abstains.
- The high-risk veto (apply provenance-aware sufficiency only to high-risk
  accepts) achieves 81.3% coverage and 25.9% loss reduction, but only as a
  narrow overlay.
- Unknown provenance collapses the fully provenance-aware policies to 0%
  coverage; the narrow gate survives (81% coverage, 7.6% FAR).
- False provenance (forged ancestry metadata) is a trust assumption the
  mechanism cannot detect.

**Survives:** the high-risk veto concept and the provenance-discounting
subroutine.

## 9. Unknown provenance as independent evidence

**Claim:** Evidence with missing lineage could be treated as weakly independent
support.

**Verdict: Rejected by design (conservative rule).**

- The simulator pools all unknown-provenance items into a single weak cluster
  with reliability capped at 0.5. Treating them as independent would inflate
  confidence.
- Authenticated provenance metadata is a prerequisite for any stronger claim.

## 10. Contradiction-driven investigation as a standalone policy

**Claim:** Acquiring evidence only to resolve specific contradictions would be
cheaper than blanket sufficiency checking.

**Verdict: Negative result — too low coverage.**

- Coverage 8–18%, loss 0.61–0.63 per task (cheap), but the policy abstains on
  most tasks because it never gathers evidence when there is no contradiction,
  even when confidence is low.
- Useful as a subroutine (deciding which evidence to buy) but not as the
  top-level decision policy.
