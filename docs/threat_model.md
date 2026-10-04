# Threat model (V0)

Adversary: the learner (any LLM/policy/heuristic) proposing recovery programs
and, in experiments, deliberately overfitting to verifier tests.

The learner must not be able to:
- approve its own recovery procedure
- modify `E_max`, constitutional rules, exposure ledger, or admission state
- manufacture a valid receipt (hash binding + admission path checks)
- disable revocation or skip verification
- directly grant capability

In scope for V0: in-process adversary via the public `propose()` API plus
direct (but rejected) injection attempts exercised in `tests/security/`.

Out of scope for V0: side channels, timing attacks, memory tampering,
supply-chain compromise of the verifier, cryptographic forgery guarantees.
