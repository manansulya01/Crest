# CREST Research Roadmap

## Current state (2026-11-03)

- HEAD: de08a67 (verified)
- Full test suite: 368 passed
- Key findings:
  - Routing hypothesis falsified (non-circular simulation, 5 signal strengths × 5 seeds)
  - Cascade with structural verification adds nothing (can't catch semantic errors)
  - Admission policy is mathematically sound but too conservative
  - Constraint-enforcement layer (budget, verification, audit) is the most defensible capability
  - Product discovery: NARROW to verified execution with auditable evidence trails

## Research directions (ranked by potential impact × feasibility)

### 1. Adaptive Verification (IN PROGRESS)
- **Problem:** Verification is binary (always run or never run). No middle ground.
- **Hypothesis:** Allocating verification effort based on task uncertainty/risk reduces
  verification cost without reducing task success.
- **Feasibility:** High (builds on existing verification infrastructure).
- **Testability:** High (can simulate with existing fake models + verification tiers).
- **Status:** Protocol to be written, experiment to be run.

### 2. Proof-Carrying Execution
- **Problem:** No compact, machine-checkable certificate for why a result was accepted.
- **Hypothesis:** Every successful execution can produce a certificate (digest of
  request, response, validation checks, budget reservation) that can be verified
  independently without re-executing.
- **Feasibility:** Medium (builds on existing digest infrastructure).
- **Testability:** High (can verify certificates independently).
- **Status:** Not started.

### 3. Compositional Guarantees
- **Problem:** Guarantees from individual steps don't compose into end-to-end guarantees.
- **Hypothesis:** If each step produces a verified receipt, the composition of
  receipts provides an end-to-end guarantee.
- **Feasibility:** Medium.
- **Testability:** Medium.
- **Status:** Not started.

### 4. Autonomous Recovery
- **Problem:** Failures are handled by indiscriminate retries, not principled recovery.
- **Hypothesis:** Classifying failures (transient, semantic, budget, validation) and
  applying targeted recovery strategies improves success rate and reduces cost.
- **Feasibility:** High (builds on existing retry logic).
- **Testability:** High.
- **Status:** Partially implemented (retry logic exists, but no failure classification).

## Next cycle

Focus on Adaptive Verification (direction 1). Create experiment protocol, implement
prototype, run experiment, report results.
