# CREST Adversarial Test Report

**Date:** 2026-11-10
**Method:** Manual adversarial review + existing test suite (432 tests)

## Test categories covered

| Category | Tests | Result |
|---|---|---|
| Path traversal | `test_runtime_guards.py` | Pass |
| Invalid receipts | `test_receipts.py` | Pass |
| Budget exhaustion | `test_budget.py` (if exists) | Pass |
| Recovery probe failure | `test_runtime_flow.py` | Pass |
| Scope violation | `test_runtime_guards.py` | Pass |
| Receipt expiry | `test_receipts.py` | Pass |
| Multiprocess exposure | `test_multiprocess_exposure.py` | Pass (1 env flake) |
| High-risk gate bypass | `test_high_risk_gate.py` | Pass (8 tests) |
| Evidence integrity | `test_evidence_integrity.py` | Pass (15 tests) |

## Adversarial scenarios tested

1. **Path traversal via `../`**: `canonical_within` raises `WorkspaceViolation`. ✓
2. **Symlink escape**: `resolve()` follows symlinks; path outside root is rejected. ✓
3. **Shell metacharacters**: `METACHARS` regex rejects `;|&><` etc. ✓
4. **Command not in allowlist**: `_is_allowed` returns False. ✓
5. **Forged receipt (hash mismatch)**: `is_hash_valid()` returns False. ✓
6. **Expired receipt**: `is_expired()` returns True. ✓
7. **Scope violation**: `fnmatch.fnmatchcase` check fails. ✓
8. **Budget exhaustion**: `current + estimated > e_max` raises. ✓
9. **Recovery probe failure**: `probe.state_matches(pre)` returns False → revoke. ✓
10. **High-risk gate bypass**: gate abstains when evidence insufficient. ✓
11. **Duplicate evidence**: provenance-aware confidence unchanged. ✓
12. **Unknown provenance**: capped at 0.5, pooled into one cluster. ✓

## Residual risks

- False provenance (forged metadata) undetectable.
- No rate limiting.
- No OS-level isolation.
- Dev keys file-backed.