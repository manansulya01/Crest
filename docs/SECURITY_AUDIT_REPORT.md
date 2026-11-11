# CREST Security Audit Report

**Version:** 0.4.0
**Date:** 2026-11-10
**Scope:** Full codebase audit (src/, experiments/, tests/)
**Method:** Manual code review + automated tests + static analysis

## Summary

| Severity | Count | Status |
|---|---|---|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 2 | Documented, mitigated by design |
| Low | 4 | Documented |
| Informational | 5 | Documented |

## Findings

### M-1: Dev keys are file-backed (Medium)
**Component:** `src/crest/signing.py` — `ensure_dev_key`, `DevKeyProvider`
**Description:** Development signing keys are stored as PEM files in `.crest/keys/`. Anyone with write access to this directory can forge receipts.
**Mitigation:** Documented. Production requires external key custody (HSM/KMS). The `KeyProvider` abstraction supports this. `is_development_key=True` by default.
**Status:** Accepted risk for development. Production deployment requires HSM integration.

### M-2: No rate limiting on task submission (Medium)
**Component:** `src/crest/runtime.py` — `execute()`, `evaluate_and_admit()`
**Description:** No rate limiting on admission or execution requests. An attacker could exhaust resources via repeated requests.
**Mitigation:** Budget enforcement (`e_max`) limits total exposure. Retry limits (`max_retries`) bound retry amplification. No explicit rate limiter.
**Status:** Accepted risk for local use. Production deployment should add rate limiting.

### L-1: Redaction is best-effort (Low)
**Component:** `src/crest/redaction.py`
**Description:** Pattern-based redaction may miss custom secret formats.
**Mitigation:** Documented as "best-effort, not a complete secret scanner." Additional patterns can be added.
**Status:** Accepted limitation.

### L-2: No cryptographic audit chaining (Low)
**Component:** `src/crest/ledger.py`
**Description:** Audit log is append-only SQLite. No hash chaining or tamper-evidence.
**Mitigation:** Append-only design prevents accidental deletion. Filesystem permissions protect against unauthorized access. Production should add hash chaining.
**Status:** Accepted limitation.

### L-3: TOCTOU race in path resolution (Low)
**Component:** `src/crest/paths.py` — `canonical_within()`
**Description:** Between `resolve()` and file operation, a symlink could be created. Python's `resolve()` follows symlinks, so the check is on the resolved path, but the file operation uses the resolved path, so the race is limited.
**Mitigation:** `resolve()` is called immediately before use. The race window is small. Production should use `O_NOFOLLOW`.
**Status:** Accepted limitation.

### L-4: No OS-level isolation (Low)
**Component:** All adapters
**Description:** Python-level checks do not provide OS-level sandboxing.
**Mitigation:** Documented. Dangerous operations require admitted context. Production should use OS-level isolation (containers, seccomp, etc.).
**Status:** Accepted limitation.

### I-1 through I-5: Informational
- I-1: `echo` shell command could leak data (allowlisted).
- I-2: `python --version` executes a subprocess (allowlisted, no user input).
- I-3: Dev key files are written with `chmod 0o600` (best-effort on Windows).
- I-4: Error messages may contain file paths (not secrets).
- I-5: No input size limits on task parameters.

## Positive findings

- Filesystem adapter uses `canonical_within` for all path operations.
- Shell adapter uses allowlist-only execution, no shell interpretation.
- Receipts use Ed25519 signatures (standard, audited library).
- Budget enforcement is checked before execution.
- Fail-closed on corrupt state, unknown tools, scope violations.
- Redaction applied to audit/CLI surfaces.
- No silent model substitution.
- Unknown usage never represented as known cost.
- State machine prevents invalid capability transitions.

## Conclusion

No critical or high-severity vulnerabilities found. The system is suitable for **Level 2 — Local Development Ready** and **Level 3 — Supervised Personal Use Ready** with the documented limitations. Production deployment (Level 4) requires HSM key custody, OS-level isolation, rate limiting, and cryptographic audit chaining.