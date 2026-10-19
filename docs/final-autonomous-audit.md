# Final Autonomous Audit

Scope: this document audits the CREST V0.5 hardening batch on branch
`feat/crest-v0.4-research-complete`. Every number below was measured in this
repository during the audit; nothing is estimated or copied from logs that do
not exist in the repository.

## 1. Starting commit
f76fc76 — branch `feat/crest-v0.4-research-complete`.

## 2. Ending commit
The hardening series this audit covers ended at `5f6483e`; this batch adds one
commit on top of it. A commit cannot contain its own hash, so the batch commit
is identified as `git log -1 --format=%H -- docs/final-autonomous-audit.md`
(the hash is also recorded in the batch's hand-off report).

## 3. Commits created
- Hardening series after f76fc76 (pre-existing, verified with
  `git log --oneline f76fc76..5f6483e`): `9f84f67`, `ad74399`, `11d3aa2`, `5f6483e`.
- This batch: one commit containing the changes listed in §24.

## 4. Tests before
- At starting commit `f76fc76`: 194 passed, exit 0 (detached worktree,
  `PYTHONPATH=<worktree>/src python -m pytest -q -p no:cacheprovider`).
- At pre-batch baseline `5f6483e`: 202 passed, exit 0 (same method).
- `5f6483e` plus the uncommitted batch before this pass: 219 passed (this session).

## 5. Tests after
243 passed, exit 0
(`$env:PYTHONPATH="src"; python -m pytest -q -p no:cacheprovider`, 217.64s).
Net +41 tests versus `5f6483e`; +24 were added in this pass. No tests were
deleted, skipped, or weakened.

## 6. Security issues discovered
- Scope drift detection was missing (found and implemented in `5f6483e`).
- The fail-closed execution guards committed in `5f6483e` crashed instead of
  denying (found and fixed in this batch):
  - `SCOPE_DRIFT` branch: `UnboundLocalError: cannot access local variable
    'exposure_before'` (`agent_runtime.py:488` pre-fix);
  - `CAPABILITY_NOT_FOUND` branch: `UnboundLocalError: cannot access local
    variable 'rel_target'` (`agent_runtime.py:477` pre-fix);
  - post-reservation re-check: `EXECUTION_FAILED:'NoneType' object has no
    attribute 'scope'`.
  All three were reproduced mechanically against a detached `5f6483e` worktree
  before fixing.
- `research reproduce` result digests were volatile: the evaluation timestamp
  (`conclusion_details.generated_at`) was part of the hashed payload, so two
  equivalent runs produced different digests (`b2ede470…` vs `7665ade1…` observed).
- `doctor --deep` branches and the reproduce manifest had no automated tests.

## 7. Security issues fixed
- Scope drift detection (`5f6483e`): the target is re-checked against the
  admitted scope after the admission decision; drift revokes and audits.
- The three fail-closed crashes above now deny with the correct reason, revoke
  where a capability still exists, and write audit entries.
- Result-digest normalization: volatile fields are excluded from the digest
  payload; verdict, criteria, artifact hashes, full-experiment status, and
  failures remain covered.

## 8. Security issues remaining
- Environment drift is not implemented.
- Composition verification is measurement-only (no admission gate).
- Probabilistic (seeded-random) sampling across families is not implemented.
- Receipt key custody is development-grade (`DevKeyProvider`); no HSM/KMS.
- Exposure reservation is single-host SQLite (`BEGIN IMMEDIATE`), not distributed.
- No longitudinal evaluation against real agent workloads.

## 9. Evidence improvements
- Pre-existing batch tests: capability state-machine matrix
  (`tests/security/test_state_machine.py`), deep verifier-gaming probes
  (`tests/security/test_verifier_gaming_deep.py`), composition experiment
  coverage (`tests/security/test_composition_experiments.py`).
- Added in this pass: deep-doctor diagnostics, 11 tests
  (`tests/security/test_doctor_deep.py`); execution-window fail-closed guards,
  5 tests (`tests/security/test_runtime_guards.py`); digest stability, 6 tests
  (`tests/unit/test_reproduce_manifest.py`); CLI version/help and
  `doctor --deep` exit codes, 2 tests (`tests/cli/test_cli_v0.py`).

## 10. New experiments
- `crest research reproduce` writes a machine-readable manifest per run:
  python/crest versions, pip-freeze package list, git commit and dirty flag,
  config path + sha256, artifact path/sha256/size, verdict, failures, and a
  stable result digest. `--full` additionally runs the five experiment suites.

## 11. Benchmark results
Measured 2026-10-18 with `python -m crest.cli benchmark`:
- admission_check_ms_mean: 3.21 (300 samples)
- denied_check_ms_mean: 1.658 (200 samples)
- generalization_verify_seconds: 4.162 (evidence_class `VERIFIED_FIXTURE`,
  fixtures_tested 20, holdout_fixtures 10)
- drift_check_ms_mean: 2.653 (100 samples)

These are wall-clock timings on one machine and are not portable. The original
V0.4 `benchmark.log` is absent from the repository, so no comparison is claimed.

## 12. Drift coverage
- Implemented: IDENTITY, CONTENT, TYPE, PERMISSION, TOPOLOGY
  (`agent_runtime._check_pinned_identity`, `src/crest/drift.py`) and SCOPE_DRIFT
  (execute-time re-check).
- Missing: ENVIRONMENT_DRIFT.

## 13. Composition results
- Composition remains measurement-only (`CrestRuntime.check_composition`);
  `tests/security/test_composition_experiments.py` and
  `tests/unit/test_composition.py` pass. No admission-gate integration exists.

## 14. Multi-process exposure results
- `Store.try_reserve_exposure` performs check-and-record under `BEGIN IMMEDIATE`;
  `tests/security/test_multiprocess_exposure.py` passes (two processes cannot
  both over-reserve). Single-host SQLite only.

## 15. Agent integration status
- Unchanged in this batch; nothing new was implemented or claimed.

## 16. Sandbox status
- Unchanged in this batch; no sandbox isolation was added or claimed.

## 17. Key-management status
- `KeyProvider` / `DevKeyProvider` / `DeterministicKeyProvider` exist in
  `src/crest/signing.py`; `tests/security/test_key_provider.py` passes.
  No HSM/KMS or remote attestation.

## 18. Reproducibility status
Verified on 2026-10-18 by running `crest research reproduce` twice:
- config digest: `1078e785…82f` in both runs, equal to the sha256 of the
  `crest.yaml` file bytes (`Get-FileHash`).
- result digest: `dd35ac9c…d98f` in both runs (identical). Before this batch
  the digest changed on every run because `generated_at` was hashed.
- `working_tree_dirty: true` (honest; the tree has uncommitted work).
- artifacts: `conclusion.json` metadata (sha256 + size) verified against the
  file; the `tables` artifact matched the run-time generated file (verified
  against a backup taken before restoring the working-tree copy).
- `package_versions` come from the active environment; in this development
  environment the editable `crest` install points at a different checkout, so
  `crest_version` (0.4.0, `src/crest/__init__.py`) is the authoritative version.

Parameter note (resolved 2026-10-19): the mismatch between the full-run
default (`n=10`) and the published tables (`n=20`) is fixed at its source.
`experiments/configs/experiment.yaml` is now the single canonical
configuration, loaded by `experiments/generalization/config.py`
(`config_digest=34a98f8b…`); the CLI and every experiment module resolve
their defaults through it. Canonical values are n=20 for ablations, 8 samples
per distribution for cross-distribution, n=6 for confidence sensitivity, and
3 cases per drift class. Table generation validates each source's recorded
configuration (including its config digest) and refuses non-canonical result
files; reduced runs (`--samples N`) are marked non-canonical and can never
replace the tables. The committed tables were produced at these parameters
but were not regenerated in this pass: they predate the generated provenance
header, and their wall-clock timing columns are not byte-stable. See §27 for
the exact verification runs and the limits of that verification.

## 19. Final completion score
- This audit does not compute a score. The only score in the repository is the
  V0.4 table in `docs/completion-v0.4-final.md` ("~89/100, weighted judgment") —
  an evidence-annotated judgment rubric, not a mechanically reproducible
  calculation, so it is referenced but not recomputed here.
- Qualitative assessment: the local batch is implemented and automatically
  verified (276 tests); the honest gaps are external infrastructure (key
  custody, distributed budget), environment drift, composition gating,
  probabilistic sampling, and longitudinal evaluation.

## 20. Exact remaining blockers
- HSM/KMS key custody and remote attestation (external infrastructure).
- Distributed (multi-host) exposure accounting.
- Environment drift detection.
- Composition verification as an admission gate.
- Probabilistic seeded sampling across families.
- Longitudinal evaluation against real agent workloads.
- Full canonical n=20 end-to-end regeneration and byte-level reconciliation of
  the committed `experiments/tables/*` were not performed in this pass (§27).
  The parameters are reconciled and table replacement is gated/validated, but
  timing columns make byte-identical regeneration machine-dependent.
- Generalization evidence remains fixture/holdout-scale; nothing above that is claimed.

## 21. Exact commands to reproduce everything
```powershell
# from the repository root, source tree on PYTHONPATH
$env:PYTHONPATH="src"
python -m pytest -q -p no:cacheprovider                          # 276 passed
python -m pytest tests/security/test_runtime_guards.py -q -p no:cacheprovider   # 5 passed
python -m pytest tests/security/test_doctor_deep.py -q -p no:cacheprovider      # 11 passed
python -m pytest tests/unit/test_reproduce_manifest.py -q -p no:cacheprovider   # 17 passed
python -m pytest tests/unit/test_experiment_config.py tests/unit/test_evidence_prereqs.py tests/unit/test_tables_integrity.py -q -p no:cacheprovider  # 22 passed
python -m crest.cli --version                                    # crest 0.4.0
python -m crest.cli doctor --deep                                # DEEP_OK + MIGRATIONS_OK, exit 0
python -m crest.cli benchmark                                    # timings in §11
python -m crest.cli research reproduce                           # quick; reads stored results, writes no artifacts
python -m crest.cli research reproduce --full                    # canonical n=20/8/6/3; rewrites tables only on success
python -m crest.cli experiment tables                            # exit 2 for non-canonical stored results
```
- Digest checks: compare `result_digest` across two consecutive manifests
  (must be equal) and compare `config.sha256` with
  `Get-FileHash crest.yaml -Algorithm SHA256`.
- Package build: `python -m pip wheel --no-deps --no-build-isolation -w <dir> .`
  → crest-0.4.0-py3-none-any.whl (94,505 bytes), exit 0.
- Lint/format/type checks: not configured in this repository (no tool config in
  `pyproject.toml`; tools not installed) — not run, not claimed.

## 22. Claims that are now justified
- Scope drift is implemented and exercised by tests.
- The execution window is fail-closed for capability disappearance and scope
  change: deny + revoke + audit, no crash (pre-fix failure modes reproduced).
- Deep doctor diagnostics detect the conditions they claim, and exit non-zero
  when they find ERROR-level conditions.
- Reproduce manifests are digest-stable for equivalent runs (config file digest
  and normalized result digest, verified across two runs plus unit tests).
- Dirty-tree reporting reflects `git status` truthfully.

## 23. Claims that remain unjustified
- Production readiness: no hardware-backed custody, no distributed policy or
  budget, no sandbox isolation (unchanged).
- Environment-drift robustness; non-filesystem/git environment families.
- Composition as an admission gate; probabilistic sampling.
- Longitudinal reliability on real agent workloads.
- Cross-machine portability of the §11 wall-clock numbers.
- "The committed experiment tables match the current full-run defaults" — the
  parameters now match (n=20/8/6/3, §18), but the committed table bytes predate
  the provenance header and were not regenerated in this pass. A canonical
  full run would rewrite them, and wall-clock timing columns are not
  byte-stable across runs or machines.
- "The canonical n=20 pipeline was executed end-to-end in this pass" — it was
  not; verification used the deterministic n=20 anchor plus a reduced n=2 full
  integration run in a detached worktree (§27).

## 24. Change provenance
Pre-existing uncommitted work (present before this audit pass):
- `src/crest/cli.py` — `research reproduce` manifest + `--version`
- `src/crest/doctor.py` — `diagnose_deep` / `doctor --deep`
- `README.md` — scope-drift bullet; `.gitignore` — `.crest/` + `crest.yaml`
- `docs/final-autonomous-audit.md`, `docs/v0.5-readiness.md` (drafts)
- `tests/__init__.py` (empty), `tests/security/test_state_machine.py`,
  `tests/security/test_verifier_gaming_deep.py`,
  `tests/security/test_composition_experiments.py`

Introduced in this audit pass:
- `src/crest/agent_runtime.py` — fail-closed crash fixes (§6)
- `src/crest/cli.py` — result-digest normalization + helpers
- `tests/security/test_runtime_guards.py`, `tests/security/test_doctor_deep.py`,
  `tests/unit/test_reproduce_manifest.py`, `tests/cli/test_cli_v0.py` (2 added tests)
- `.gitignore` — `reproduce_manifests/` entry; completed audit + readiness docs.
- Excluded from the commit: `reproduce_manifests/` (run output, ignored),
  `experiments/tables/*` regenerated by verification runs (restored to HEAD),
  `.crest/` runtime state, `crest.yaml`.

## 25. Verification performed this pass
- Focused suites: 38 passed (6 files, 36.70s); 11 passed (multiprocess exposure,
  key provider, composition; 2.26s); 5 passed (runtime guards, 1.07s).
- Baseline suites in detached worktrees: `f76fc76` → 194 passed; `5f6483e` → 202 passed.
- Full suite on the final tree: 243 passed, exit 0 (217.64s).
- Pre-fix reproduction of §6 defects against `5f6483e` (`UnboundLocalError` /
  `EXECUTION_FAILED`); the fixed tree passes the same tests.
- `research reproduce` twice: exit 0, SUPPORTED, identical digests (§18).
- `doctor --deep`: exit 0, DEEP_OK + MIGRATIONS_OK on the healthy local state;
  corrupted-store exit 1 covered by `tests/cli/test_cli_v0.py`.
- CLI smoke: `--version` → `crest 0.4.0`; `--help` and `status` exit 0;
  `benchmark` exit 0 (§11).
- Wheel build: `crest-0.4.0-py3-none-any.whl`, 94,505 bytes, exit 0.
- `git diff --check`: clean (run before the commit).

## 26. Implementation vs automated verification vs manual review
- Implementation (code in this repository): reproduce manifest + digest
  normalization (`cli.py`); deep doctor (`doctor.py`); fail-closed guards and
  scope drift (`agent_runtime.py`).
- Automated verification (tests in this repository): the suites in §25; the §6
  pre-fix failure modes were reproduced mechanically against `5f6483e`.
- Manual review (not machine-checked): diff inspection, manifest cross-checks,
  module inventory, and the limits lists in §8/§20/§23.
- Not provided by any of the above: external replication, HSM custody,
  real-workload longitudinal evaluation.

## 27. Reproduction-integrity follow-up (2026-10-19)

Implemented in this pass:
- One canonical experiment configuration
  (`experiments/configs/experiment.yaml`), loaded by
  `experiments/generalization/config.py`; the CLI and all experiment modules
  resolve sample counts and bounds through it. Canonical digest:
  `34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf`.
- `research reproduce --full` runs experiments, then the conclusion, then
  tables, so tables describe the same run. `--samples N` requires `--full`;
  any explicit override (even one equal to the canonical value) marks the run
  non-canonical and never replaces canonical tables. Failed experiments skip
  table regeneration and exit 2.
- Tables are generated purely, validated, staged, hash-checked from staged
  bytes, and replaced with rollback of already-replaced files on failure.
  Canonical replacement requires each source's recorded canonical flag,
  sample counts, and config digest to match the current canonical config.
- Manifest schema 2 records the experiment configuration, source hashes and
  sizes, artifact hashes from bytes, experiment statuses, code revision,
  dirty-tree state, timestamps, and a normalized `result_digest` that excludes
  evaluation timestamps and artifact paths.
- New tests: `tests/unit/test_experiment_config.py` (9),
  `tests/unit/test_evidence_prereqs.py` (6),
  `tests/unit/test_tables_integrity.py` (7), and 11 added cases in
  `tests/unit/test_reproduce_manifest.py` (17 total).

Verified (PowerShell, repository root, `$env:PYTHONPATH="src"`):

| check | result |
|---|---|
| new tests | 39 passed (7.77 s) |
| `tests/unit tests/cli` | 99 passed (94.69 s) |
| full suite | **276 passed**, exit 0 (221.26 s) |
| canonical n=20 anchor | `VERIFIED_FAMILY`; 40 fixtures, 20 holdout, 0 failures; 2.74 s |
| quick reproduce ×2 (stored n=10 results) | identical digest `6d6077b2…49fdb`; `SUPPORTED` with the C8 caveat; tables `not_run` |
| `crest experiment tables` (stored n=10) | exit 2, `experiments/tables/` unchanged |
| reduced full run (`--full --samples 2`, detached worktree) | exit 0; all 5 experiments `ok`; source `cli-override`, `canonical: false`; tables `skipped`; digest `f4adfa59…` (timing-dependent) |
| quick ×2 after reduced run (worktree) | identical digest `c007894c…` |
| `crest experiment tables` (reduced results) | exit 2, tables unchanged |
| wheel build | `crest-0.4.0-py3-none-any.whl`, 103,401 bytes, exit 0 |
| `git diff --check` | clean |

Limits:
- The canonical n=20 full pipeline was not executed end-to-end in this pass.
  The deterministic n=20 anchor and the reduced n=2 integration run exercise
  the classification path, ordering, and gating separately.
- The committed `experiments/tables/*` files were not regenerated. They were
  produced at the canonical parameters but predate the provenance header.
- Full-run digests are not stable across runs or machines: conclusion cost
  criteria and table timing columns are wall-clock measurements. Quick-mode
  digests over identical stored JSONL are stable.
- No external replication, independent implementation, or production
  deployment was performed.
