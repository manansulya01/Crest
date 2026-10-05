# Crest Research V0.3

## Research question

Can independently verified recovery evidence be graded by *scope of
generalization* rather than treated as binary, and can the admission layer
refuse to grant broader autonomy than the evidence supports?

## Hypothesis

Fixture-grade evidence over-admits; grading receipts by their evidence class
(fixture vs family vs general) and holding autonomy to that class should
reduce unsafe admissions without hiding the fact that generalization is
small.

## Evidence model

- `VERIFIED_FIXTURE`: recovery proven on one literal fixture.
- `VERIFIED_FAMILY`: recovery proven across a declared environment family
  with a holdout split.
- `VERIFIED_GENERAL`: recovery proven across ≥ 2 families with sufficient
  holdout coverage and zero observed failures.

No transition from a weaker class to a stronger one is made without a fresh
verification pass.

## Bounds

Admission uses a one-sided Wilson upper confidence bound on the failure
rate; zero observed failures still yields a nonzero upper bound.
Classification is conservative: all-zeros does not imply safety — it implies
sampling sufficiency relative to holdout.

## Admission rule

```text
ADMIT(A, S, R) iff ValidReceipt ∧ ScopeMatch ∧ EvidenceValid
  ∧ EvidenceClass ≥ Constitution.min_evidence_class
  ∧ SuccessRate ≥ min_recovery_success_rate
  ∧ ledger_total + exposure ≤ Emax
```

Certified exposure is an accounting input, not an observed-harm guarantee.

## Revocation

Re-probe on filesystem execution; drift detection compares evidence family
against workspace topology; expiry via TTL; re-admission requires fresh
verification.

## Falsification criteria (standing honesty boundary)

- If systematic unsafe admissions follow VERIFIED_FAMILY/GENERAL admission,
  the generalization split is insufficient; weaken the classification rules.
- If GeneralizationVerifier costs become prohibitive, record and treat as a
  practical limit.
- If a holdout split cannot distinguish overfit recovery, only fixture-grade
  caps remain valid.

## What remains

- Probabilistic (not merely deterministic) sampling across families
- Adversarial fault-model coverage
- Multi-agent / session exposure consistency
