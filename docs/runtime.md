# Runtime

`CrestRuntime` is the control plane.

- `from_config(path)` opens the SQLite store; corrupt stores raise
  `SecurityStateCorrupt` and refuse to operate.
- `check(...)` evaluates without executing; decision is written to audit.
- `execute(...)` evaluates, records, dispatches, captures exposure, re-probes
  filesystem recovery, and may revoke.
- `verify_and_admit(...)` runs independent verification, stores the receipt,
  and admits the capability. Revocation requires calling `verify_and_admit` or
  the research lifecycle again; there is no appeal path.
- `revoke(...)` is immediate and terminal; there is no undo of revocation.
