# Architecture

```
learner.propose(action, env)      # untrusted, arbitrary output
        |
        v
verifier.verify(action, recovery, test_suite)   # deterministic, executes handlers
        |
        v
CapabilityReceipt (content-addressed, hash-bound fields)
        |
        v
admission.admit(receipt, current_exposure, constitution)   # deterministic
        |
        v
Capability state machine: FORBIDDEN -> PROPOSED -> VERIFYING -> VERIFIED
                          -> ADMITTED -> ACTIVE -> REVOKED -> VERIFYING
        |
        v
runtime.execute(...)  # re-checks receipt, scope, expiry, budget every call
        |
        v
probe: run action+recovery in a scratch copy; mismatch -> revoke
```

Exposure ledger is append-only; recovery never refunds exposure.
