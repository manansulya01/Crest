# Crest

Research prototype: **can independently verified recoverability become the mechanism by which an agent earns autonomous capabilities?**

```text
LEARN (untrusted) -> VERIFY (independent) -> RECEIPT -> ADMIT (constitutional)
     -> EXECUTE -> OBSERVE / REPROBE -> REVOKE on evidence failure
```

## Core claim (narrow, honest)

If the verifier's certified exposure bound is valid and constitutional admission rules are enforced, the admission layer will not authorize actions whose *certified* exposure exceeds the configured budget.

Whether certified exposure bounds realized harm, and whether recovery evidence transfers usefully, are **empirical questions this repository is built to test** — not assumptions baked into the code.

## Trust separation

| Plane | Role | Can |
|-------|------|-----|
| Intelligence (`learner.py`) | proposes recovery programs | propose only |
| Evidence (`verifier.py`) | executes, fault-injects, measures | produce receipts |
| Constitutional (`constitution.py`, `admission.py`, `runtime.py`) | owns `E_max`, TTL, admission, ledger, revocation | grant/revoke authority |

The learner holds no reference to the constitution, ledger, or admission state. Recovery *programs* are data identified by digest; only handlers registered in the verifier's process execute them.

## Quickstart

```bash
pip install -e .
python examples/milestone1_demo.py
python -m pytest
```

## Milestone 1 (implemented)

`delete_file` + heuristic proposer + sandbox workspace + independent verifier (normal and repeated execution) + content-addressed receipt + deterministic admission + execution-time re-probe with asymmetric revocation.

## What is NOT yet implemented (Milestone 2+)

Fault injection in the verifier (recovery command failure, partial execution, stale snapshots), distribution-shift arms, adversarial learner experiments, AAC metric collection, baseline/self-grading arms, statistical analysis. See `docs/`.

## Layout

```
src/crest/     actions.py workspace.py recovery.py learner.py verifier.py
               receipts.py constitution.py admission.py ledger.py
               capabilities.py runtime.py hashing.py
tests/unit/    tests/security/ (invariant tests) tests/integration/
experiments/   baseline/ self_grading/ crest/ adversarial/ distribution_shift/
examples/      milestone1_demo.py
```

## Non-goals (V0)

No cryptographic signatures (content hashes only; trust assumptions documented), no distributed systems, no production agent platform, no UI.
