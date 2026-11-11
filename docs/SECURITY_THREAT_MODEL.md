# CREST Security Threat Model

**Version:** 0.4.0
**Date:** 2026-11-10
**Scope:** Local execution control plane for AI agent tool use

## Assets

| Asset | Sensitivity | Location |
|---|---|---|
| Workspace files | High | User filesystem |
| Audit ledger | Medium | `.crest/` SQLite |
| Receipts | Medium | `.crest/` |
| Signing keys | High | `.crest/keys/` (dev keys) |
| Configuration | Low | `crest.yaml` |
| Budget state | Medium | In-memory / persisted |

## Trust boundaries

1. **Agent → Runtime:** Agent requests are untrusted input. The runtime must validate all parameters.
2. **Runtime → Adapter:** Adapters execute only through admitted contexts. Direct invocation fails closed.
3. **Adapter → Filesystem/Shell:** Operations are confined to workspace root via `canonical_within`.
4. **Runtime → External providers:** No external calls by default. Provider boundaries documented but not implemented.
5. **Evidence → Receipt:** Receipts are signed with Ed25519. Verification checks hash binding and signature.

## Attacker profiles

| Profile | Capabilities | Likelihood |
|---|---|---|
| Malicious task submitter | Can submit arbitrary task parameters | Medium |
| Prompt injection | Can embed instructions in retrieved content | High |
| Malicious tool output | Can return crafted tool results | Medium |
| Local process | Can read/write files in workspace | Low (requires local access) |
| Resource exhaustion | Can submit oversized or repeated requests | Medium |

## Attack scenarios and mitigations

| Scenario | Impact | Existing protection | Residual risk |
|---|---|---|---|
| Path traversal | Read/write outside workspace | `canonical_within` resolves and checks containment | TOCTOU race with symlinks; mitigated by `resolve()` |
| Command injection | Arbitrary code execution | Allowlist-only shell adapter, metachar rejection | Allowlist is small; `echo` could leak data |
| Forged receipt | Unauthorized action execution | Ed25519 signature + hash binding | Dev keys are file-backed; anyone with filesystem write access can forge |
| Replay attack | Re-execute old action | Receipt expiry + target scope check | No nonce/sequence number in receipt |
| Budget bypass | Exceed cost limits | Pre-execution budget check | Race condition under concurrent execution (not locked) |
| Privilege escalation | Gain unauthorized capabilities | State machine (PROPOSED→VERIFYING→VERIFIED→ADMITTED→ACTIVE) | State transitions are in-memory; no persistence across restarts |
| Secret exposure | Leak credentials | Redaction patterns (best-effort) | Redaction is not exhaustive; custom secret formats may leak |
| Prompt injection | Override authorization | No model is involved in authorization; runtime is deterministic | Tool outputs fed to agents may contain injection, but runtime doesn't process them |
| Resource exhaustion | Denial of service | Budget limits, retry limits | No rate limiting on task submission |
| Audit tampering | Hide evidence | Append-only SQLite | No cryptographic chaining; SQLite is modifiable by anyone with file access |

## Known limitations

1. **Dev keys are file-backed.** Anyone with write access to `.crest/keys/` can forge receipts. Production requires external key custody (HSM/KMS).
2. **No OS-level isolation.** Python-level checks do not provide OS-level sandboxing.
3. **Redaction is best-effort.** Custom secret formats may not be caught.
4. **No rate limiting.** Task submission is not rate-limited.
5. **No cryptographic audit chaining.** Audit log is append-only SQLite, not tamper-evident.
6. **False provenance undetectable.** Provenance metadata is not authenticated.