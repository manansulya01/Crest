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
- That a budget bounds true-world harm; Crest bounds *certified* exposure,
  an accounting input, not an observed-harm guarantee.
- That fixture verification scales to real agent environments.
