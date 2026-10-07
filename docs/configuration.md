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
  # minimum acceptable evidence class for a receipt to authorize execution
  min_evidence_class: "VERIFIED_FIXTURE"
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
input path. Unknown config sections are rejected (typo/tamper fail closed).

Trust boundary (explicit):

- A *running* runtime uses the `CrestConfig` it parsed at startup. Editing
  `crest.yaml` on disk does not broaden the live session; the change takes
  effect only on restart / new runtime.
- Receipts are bound to `policy_version`. Changing `policy.version` in
  crest.yaml does not silently carry old evidence forward: the next
  admission is denied with `POLICY_DENIED` until re-verified under the new
  policy.
- Filesystem write access to crest.yaml and to `.crest/keys/` is *operator*
  trust; the agent runtime assumes only that the agent cannot write them.
  Production key custody (HSM/KMS/rotation) is external to this repository.
