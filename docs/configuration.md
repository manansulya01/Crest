# Configuration

`crest.yaml` at project root; all fields optional with conservative defaults.

```yaml
workspace:
  root: .
exposure:
  max_window_exposure: 1.0
  window_seconds: 3600
admission:
  require_receipt: true
  require_verified_recovery: true
  allow_fixture_evidence: true
  max_receipt_age_seconds: 3600
  min_recovery_success_rate: 0.95
  max_recovery_p99_ms: 10000
revocation:
  enabled: true
  immediate: true
runtime:
  dry_run: false
shell:
  allowlist: [pwd, ls, dir, git status, git diff, python --version, echo]
```

Security invariants are hard-coded: the agent cannot change them through any
input path; only editing this file and restarting runtime changes policy.
