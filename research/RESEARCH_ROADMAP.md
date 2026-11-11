# CREST Research Roadmap

## Current state (2026-11-05, after Cycle 4)

- HEAD: `a0fb2d3` — uncommitted (Cycle 2, 3, 4 work).
- Full suite: 424 passed.
- Cycle 3 result (NARROW): high-risk acceptance veto reduces risk-weighted loss by 25.9% vs the strong verifier at 81% coverage.
- Cycle 4 result: validation design complete. Claim reconstructed and audited. Dataset protocol, statistical analysis, live probe protocol, and offline harness delivered. Pre-registered promotion criteria defined. **No live calls made. No spending.** Status: READY FOR AUTHORIZATION.

## Research directions (ranked)

### 1. Live verification of the high-risk gate (highest value, BLOCKED on authorization)
Implement the high-risk gate as a minimal runtime component and run the capped
live probe (≤ $0.05, 10–20 tasks, `gemini-3.5-flash-lite`) to measure real
judge FPR/FNR and error correlation with the generator. This decides whether the
gate is real or a simulation artifact.

### 2. Proof-Carrying Execution (unstarted)
Every successful execution emits a compact machine-checkable certificate.
Cheap to build on existing digest machinery; meaningful only if live verifier
reliability is known.

### 3. Compositional Guarantees (unstarted)
Compose per-step receipts into an end-to-end guarantee. Depends on #2 and on #1.

### 4. Autonomous Recovery with failure classification (unstarted)
Classify failures and apply targeted recovery. Highest product-adjacent leverage;
strongly constrained by live evidence.

### 5. Honest stopping: abandon routing claims
Routing-based cost reduction is falsified for this task class. Do not invest
further in routing policy complexity.

## Next cycle

Cycle 4 live execution — requires explicit authorization. If unauthorized, stop
at the evidence boundary and record the blocker. Do not run any further spend
without approval.
