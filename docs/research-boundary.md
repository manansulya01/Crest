# Research boundary

Proven today (M1/M2 + runtime v0 invariant tests):

- Recovery evidence (fixture-verifier success) drives admission decisions
  through independent verification.
- Reprobe-based revocation contains fixture-overfit recovery proposals.
- Asymmetric revocation plus cumulative exposure budget survive the M2 attack
  suite.

Not proven:

- That receipts predict recoverability under unseen environments (M2
  holdout falsification demonstrated the contrary risk on our attacks).
- That certified exposure bounds true-world harm; Crest bounds *certified*
  exposure, an accounting input, not an observed-harm guarantee.
- That fixture verification scales to real agent environments.

V0.3 changed fixture-level receipts into a graded evidence hierarchy, but the
hierarchy still inherits from deterministic seed-based families — stronger
than V0.2, weaker than broad production, and honest about the gap.
