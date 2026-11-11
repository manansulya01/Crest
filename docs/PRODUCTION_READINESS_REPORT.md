# CREST Production Readiness Report

**Version:** 0.4.0
**Date:** 2026-11-10

## Readiness level: LEVEL 3 — Supervised Personal Use Ready

CREST has been validated for controlled local development and supervised personal use
with explicitly bounded permissions. It is NOT ready for unsupervised autonomous
operation (Level 4) or production/commercial deployment (Level 5).

## Justification

- 432 automated tests pass (unit, integration, end-to-end, security, adversarial).
- Security audit found 0 critical, 0 high, 2 medium, 4 low findings.
- All medium findings are accepted risks with documented mitigations.
- Budget enforcement, receipt validation, scope checking, and fail-closed behavior verified.
- No live validation; all results simulation-based.
- Dev keys are file-backed (not production-grade).
- No OS-level isolation.
- No rate limiting.
- No cryptographic audit chaining.

## Supported operating profiles

| Profile | Status | Conditions |
|---|---|---|
| A. Local development | Ready | Controlled workloads, non-sensitive data, restricted permissions |
| B. Supervised personal use | Ready | Explicitly approved operations, bounded execution, audit logging, backups |
| C. Unsupervised autonomous | Not ready | Requires live validation, OS isolation, rate limiting |
| D. Production/commercial | Not ready | Requires independent security assessment, HSM, audit chaining |

## Blockers for Level 4

1. Live validation of the high-risk gate (authorization required).
2. HSM/KMS key custody (external).
3. OS-level sandboxing (containers/seccomp).
4. Rate limiting.
5. Cryptographic audit chaining.
6. Independent security assessment.