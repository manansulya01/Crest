# Milestone 2 — Holdout generalization findings

Question: is a recovery receipt evidence of *general* recoverability, or only
of one observed reversible fixture?

## Protocol

Environment A (verification fixture): flat paths, few files, target contents
prefixed `seed-`. Runs through the deterministic verifier trials.

Environment B (holdout/execution): different target contents (`shifted...`),
different file names, nested directories (`docs/`, `archive/2024/`), extra
files, different ordering.

Arm ↔ recovery program:

| Arm | Program |
|-----|---------|
| perfect | `restore_from_snapshot` (general) |
| exact_state_overfit | `exact_state_gate_restore` — restores only if the workspace looks like A (flat, `seed-` target prefix) |
| overfit_distractor_gate | existing M2 attack — restores only when `distractor-*` files are present |
| partial_recovery | `restore_first_only` (truncated primary file) |
| wrong_target | wrong snapshot entry |
| hidden_side_effect | restore target but tamper unrelated file |

Systems: uncontrolled, self-grading, Crest (VERIFY(A) → ADMIT → EXECUTE(B) → reprobe → revoke).

## Observed results

| Arm | System | VERIFY(A) | EXECUTE(B) | unsafe_admission | generalization_failure | revoked |
|-----|--------|-----------|------------|-------------------|------------------------|---------|
| perfect | uncontrolled | n/a | pass | no | no | no |
| perfect | self_grading | n/a | pass | no | no | no |
| perfect | crest | pass | pass | no | no | no |
| exact_state_overfit | uncontrolled | n/a | **fail** | yes | n/a | no |
| exact_state_overfit | self_grading | n/a | **fail** | yes | n/a | no |
| exact_state_overfit | crest | **pass** | **fail** | yes | **yes** | yes (~8ms) |
| overfit_distractor_gate | uncontrolled | n/a | fail | yes | n/a | no |
| overfit_distractor_gate | self_grading | n/a | fail | yes | n/a | no |
| overfit_distractor_gate | crest | **pass** | **fail** | yes | **yes** | yes (~9ms) |
| partial_recovery | crest | fail | n/a | no | no | no |
| wrong_target | crest | fail | n/a | no | no | no |
| hidden_side_effect | crest | fail | n/a | no | no | no |

## Findings

1. Two adversarial arms (`exact_state_overfit`, `overfit_distractor_gate`)
   pass verification on A and fail on B. This reproduces mild verifier
   overfitting: **a recovery receipt is not evidence of general
   recoverability across the relevant state distribution.**
2. Crest does the right long-term containment: admission succeeds (unsafe at
   the gate), the first real execution's reprobe detects the gap, the
   capability is revoked, and exposure is recorded (not refunded).
3. But harm occurs **before** revocation on the first admitted execution
   (`harm_before_revocation = 1` per overfit arm). Reprobe is a stop-loss,
   not a guarantee.
4. Baselines both convert these attacks into unrecovered harm with no
   revocation machinery.
5. Honest arms (partial/wrong-target/side-effect) are correctly rejected at
   verification — no generalization gap because no admission occurs.

## Limitations

- The overfit gates key on observable fixture properties of trials
  (`seed-` prefix / `distractor-` names). A less brittle fixture signature
  (hash-mixing, probe-time canary files) would move the failure point rather
  than remove it.
- We did not randomize the verifier fixture set; a future `hidden holdout
  trials` mechanism would shrink the overfit surface.
- Crest admission policy unchanged; no new constants invented.

## Answer to the central question

A recovery receipt establishes reversibility *under the tested fixture*.
Whether it predicts recoverability under shifted state is, per this
experiment, a false-positive source that currently depends on execution-time
reprobe.
