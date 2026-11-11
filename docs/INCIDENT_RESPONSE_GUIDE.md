# CREST Incident Response Guide

## If you suspect a security issue

1. Stop all CREST processes immediately.
2. Revoke all capabilities: `crest revoke --all`
3. Rotate signing keys (delete `.crest/keys/` and re-run `crest init`).
4. Review audit log: `crest audit`
5. Check for unauthorized file modifications: `git diff` and `git status`.
6. Preserve evidence (do not delete `.crest/` or logs).
7. Report the issue with: timestamp, commands run, audit log excerpt, and reproduction steps.

## If budget is exceeded

1. CREST should fail-closed (no execution without budget).
2. Check `.crest/` state for corruption.
3. Run `crest doctor` to diagnose.
4. If state is corrupt, restore from backup.

## If a receipt is compromised

1. Revoke the affected capability.
2. Run `crest verify` to re-issue.
3. Check audit log for unauthorized executions.
4. Rotate keys if compromise is confirmed.

## Emergency contacts

This is a research project. There is no production support. Report issues via the project's issue tracker.