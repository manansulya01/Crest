# Security model (v0)

Trust assumptions:

- The agent is untrusted and proposes tool calls only.
- Independent verification is the sole evidence source.
- The constitution and ledger are agent-inaccessible (frozen config, runtime-
  private store).

Guarantee (conditional):

If admitted actions' receipts accurately bound recoverability, the runtime
enforces: receipt validity + scope + expiry + exposure budget before every
execution, records exposure permanently, revokes on probe failure, and never
allows a revoked/expired capability to execute.

Non-guarantees:

- V0 receipts are fixture-specific evidence. Probe/reprobe failures indicate
  limits, but admission is NOT proof of general recoverability.
- No cryptographic attestation; receipts are content-addressed, forgeries are
  caught by hash validation not signatures.
- The shell adapter allows read-only functionality only.
