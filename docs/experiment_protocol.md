# Experiment protocol

For every experiment run, record as JSON/JSONL:
- git commit, configuration, random seed
- verifier version, environment version, test-suite version, timestamp
- per-action admissions/denials, revoked capabilities and reasons
- realized vs certified exposure, recovery success rates, latencies
- AAC(t) trace, realized exposure trace, intervention events

Arms:
- A baseline agent: no capability admission
- B self-grading agent: learner grades its own recovery (expected to fail)
- C Crest: independent verifier + constitutional admission

Adversarial cases to implement before drawing conclusions:
false recovery, partial recovery, propagation, distribution shift, stale
evidence, learner deception/overfitting, repeated-action accumulation,
composition of individually-safe actions.

No hard-coded results; the harness must record failures faithfully.
