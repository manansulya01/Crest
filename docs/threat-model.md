# Threat model

- Agent: proposes tool calls only; cannot reach config store internals or
  receipt payloads except through public reads.
- ToolGate: every caller goes through runtime; no public adapter entry point
  that skips admission -> adapter contexts are non-functional without admission.
- Verification: deterministic; agent proposes recovery programs but cannot
  alter verifier input/expectations after the fact.
- Integrity: all receipt-protected fields are hash-bound; any tampering is
  detected before admission, and audit is append-only.
- Replay: receipts are expired with TTL from config and the exposure ledger is
  persistent so cumulative exposure cannot be reset.
