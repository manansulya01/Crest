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
replace the tables. The 2026-10-21 release-gate pass closed the remaining
gaps: a canonical full run initially exposed that the CLI passed one sample
count to every arm (confidence n=6 and cross-distribution n=8 were being run
at n=20); canonical `--full` now passes no overrides. The complete pipeline
then ran successfully twice, and the committed tables were regenerated with
provenance headers. See §28 for exact runs, digests, and limits.

## 19. Final completion score
- This audit does not compute a score. The only score in the repository is the
  V0.4 table in `docs/completion-v0.4-final.md` ("~89/100, weighted judgment") —
  an evidence-annotated judgment rubric, not a mechanically reproducible
  calculation, so it is referenced but not recomputed here.
- Qualitative assessment: the local batch is implemented and automatically
  verified (276 tests at that time; 291 after §28); the honest gaps are
  external infrastructure (key custody, distributed budget), environment
  drift, composition gating, probabilistic sampling, and longitudinal
  evaluation.

## 20. Exact remaining blockers
- HSM/KMS key custody and remote attestation (external infrastructure).
- Distributed (multi-host) exposure accounting.
- Environment drift detection.
- Composition verification as an admission gate.
- Probabilistic seeded sampling across families.
- Longitudinal evaluation against real agent workloads.
- Raw-byte reproducibility of tables across machines: the canonical n=20
  pipeline and table regeneration are now complete, but timing/latency columns
  are wall-clock observations. Scientific content and `result_digest` are
  stable; raw bytes and `performance_digest` are not (§28).
- Generalization evidence remains fixture/holdout-scale; nothing above that is claimed.

## 21. Exact commands to reproduce everything
```powershell
# from the repository root, source tree on PYTHONPATH
$env:PYTHONPATH="src"
python -m pytest -q -p no:cacheprovider                          # 291 passed
python -m pytest tests/unit/test_provenance.py tests/unit/test_reproduce_manifest.py tests/unit/test_tables_integrity.py tests/unit/test_experiment_config.py tests/unit/test_evidence_prereqs.py tests/cli -q -p no:cacheprovider  # 58 passed
python -m crest.cli --version                                    # crest 0.4.0
python -m crest.cli doctor --deep                                # DEEP_OK + MIGRATIONS_OK, exit 0
python -m crest.cli benchmark                                    # timings in §11
python -m crest.cli research reproduce                           # quick; reads stored results, writes no artifacts
python -m crest.cli research reproduce --full                    # canonical 20/8/6/3; rewrites tables only on success
python -m crest.cli experiment tables                            # exit 0 on canonical results; exit 2 if non-canonical
```
- Digest checks: compare `result_digest` across two consecutive full manifests
  (must be equal), `performance_digest` (expected to differ), and
  `config.sha256` with `Get-FileHash crest.yaml -Algorithm SHA256`.
- Package build: `python -m pip wheel --no-deps --no-build-isolation -w <dir> .`
  → crest-0.4.0-py3-none-any.whl (107,051 bytes), exit 0.
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
- ~~"The committed experiment tables match the current full-run defaults"~~
  — now justified for scientific content: the tables were regenerated at
  n=20/8/6/3 on 2026-10-21, normalized scientific content matches the prior
  committed tables, and provenance headers are present (§28). Raw bytes still
  vary with wall-clock timing.
- ~~"The canonical n=20 pipeline was executed end-to-end"~~ — now justified:
  it completed twice on 2026-10-21 with identical `result_digest` (§28).

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
> Historical pass; current release-gate verification is in §28.

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

> Historical record. The canonical full-pipeline, table-reconciliation, and
> digest-stability gaps listed under "Limits" were closed on 2026-10-21;
> see §28.

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
- Manifest schema 2 (superseded by schema 3 in §28) records the experiment
  configuration, source hashes and sizes, artifact hashes from bytes,
  experiment statuses, code revision, dirty-tree state, timestamps, and a
  normalized `result_digest` that excludes evaluation timestamps and artifact
  paths.
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
  digests over identical stored JSONL are stable. (Superseded by the
  schema-3 scientific/performance digest split and the two stable canonical
  runs in §28.)
- No external replication, independent implementation, or production
  deployment was performed.

## 28. Canonical reproduction release gate (2026-10-21)

Starting state: branch `feat/crest-v0.4-research-complete`, HEAD
`3b7fd042682a1d96a5eb42a70dd79f43da1ef69b`, clean working tree. Canonical
configuration digest:
`34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf`.

### Defect found by the first canonical run

The first `crest research reproduce --full` attempt ran all five experiments
successfully but could not regenerate tables (exit 2). The CLI was passing the
ablation sample count (`n=20`) to every arm, so confidence sensitivity ran at
n=20 instead of its canonical 6 and cross-distribution at 20 samples per
distribution instead of 8. `tables.write_all` correctly refused the
non-canonical sources and preserved the committed tables. Manifest
`reproduce_20261019T121457_235704Z.json` recorded digest
`11ad6cad8abff8727c7e54ba5ea2e7ac06a1ac6622efdb60825d52fa468d0999` with
`tables.status=failed`; no table was overwritten.

Fix: canonical full runs pass no sample overrides, so each module resolves its
own value from `experiments/configs/experiment.yaml` (ablations 20,
cross-distribution 8, confidence 6, drift 3 cases/class, exposure budgets
0.1/0.25/0.5/1.0). Explicit `--samples N` still overrides the sample-count
arms uniformly and is recorded as non-canonical.

### Canonical full runs

Two complete canonical runs were executed from the same working tree:

| run | manifest | duration | experiments | tables | result_digest | performance_digest |
|---|---|---|---:|---|---|---|
| A | `reproduce_20261021T090912_017948Z.json` | 18.66 min | all 5 `ok` | `written` | `38e71b6d67e4ead7dfdf55c63af0ae9f8da05ec115c7fb7ad259525f3e998905` | `a9721fccfbdb61a762d61384c3a8c0b96f119138ec34a6c91b8b28b8f80101af` |
| B | `reproduce_20261021T092527_213635Z.json` | 15.50 min | all 5 `ok` | `written` | `38e71b6d67e4ead7dfdf55c63af0ae9f8da05ec115c7fb7ad259525f3e998905` | `9f2f0ceb1dcfbab58174f25ff59ed1139da653d9c7d4459180f1f18aab14d224` |

Both runs produced conclusion `SUPPORTED` with C1-C5, C8, and C9 scientific
criteria equal; C5 false-admission count 2. Only C6/C7 wall-clock criteria
differed (run A: 14.033 s / 7.472 s; run B: 12.489 s / 6.588 s).

Across A and B:
- all five raw JSONL hashes differed;
- all five normalized `scientific_sources` digests were equal;
- all seven raw table hashes differed;
- all seven normalized table `content_sha256` values were equal;
- `result_digest` was identical; `performance_digest` differed.

### Digest schema (manifest version 3)

`result_digest` is SHA-256 over canonical JSON containing:
- conclusion verdict, reason, and criteria with
  `C6_general_cost_mean_seconds` and `C7_fixture_cost_mean_seconds` removed;
- `experiment_config` (including config digest and canonical flag);
- `conclusion_details.data_config`;
- normalized source digests (`scientific_sources`), which exclude run
  timestamps, `verification_seconds`, distribution `seconds`, drift
  `revocation_latency_ms`, and machine/code provenance fields
  (`git_commit`, `branch`, `os`, `python`, `python_version`, `crest_version`,
  `verifier_version`);
- normalized table content hashes (`content_sha256`), which remove the
  provenance header and timing/latency cells;
- experiment statuses and failures.

It does not include raw file bytes, sizes, paths, run timestamps, run duration,
or timing values. Those remain in the manifest and are covered by the separate
`performance_digest`, which hashes run duration, C6/C7, per-source timing
arrays, raw source hashes, and raw artifact hashes/sizes.

### Table reconciliation

All seven committed tables were regenerated by the canonical runs. After
normalizing timing/latency cells and removing the provenance header, every
table's scientific content is identical to the previously committed table
(row order, schemas, classifications, admissions, counts, rates, and drift
outcomes). The deliberate changes are the added provenance header and new
wall-clock timing values.

Final raw table hashes (run B, unchanged by a subsequent canonical
`crest experiment tables` invocation):

| table | raw sha256 | normalized content sha256 | bytes |
|---|---|---|---:|
| `ablations.csv` | `437059f34da6f8eca74575fba51013dec263cac827087fbd44f63a95a8345804` | `14dd038779de6e2b305cd16d5f63c4cecec40082c66eafc656e65899b9a28dfd` | 3355 |
| `ablations.md` | `510b7e81490c62ed776ec6d1bcb9e6094bb442f2822cd7b01eb6fa7bc22cefe5` | `816a8580a5cf65f99663ae7c71b9e96af02a21d1d179e7cf4b66a15b25ad3bc2` | 4156 |
| `all_tables.md` | `98f1bd04f352bbbbf83ab4669cc2d8cb9d71c6d363065655fa3d01a0ca100358` | `c41b32c0d13227ce756d9f11f0c9a6051e46762c937631843d35ecd19a59f7f5` | 10308 |
| `confidence_sensitivity.md` | `6331fa061b291704d64fbe70b6400391c609500cda26ee35a15892cafb332e84` | `839a0f035d02619697f165584dcdd6442b07b57c48c9742bc2cc19ea3882179f` | 2543 |
| `cross_distribution.md` | `b9d499e7d82a4bdb9244f4c6a6331e8583e60535ad6b4bd1b84a28e564121e26` | `6696bdb5e5045fe8ec000b778a0c6f7ed060f744a1a8d37acf626c3b876199b3` | 2238 |
| `drift.md` | `1afc25e905a6fca5dd0e1dacd44ea45a4ef23d31310df2597513542f97062575` | `84bbf9970566d6a9102b72d1c4749f9315962fd6eed6166fcf66222b72bcf1f2` | 2801 |
| `exposure_sweep.md` | `1b6e31e369ea92c1ab86c09543bf2a7ebf8811c3770c1e31a59cb8f3b456b52c` | `c870891f018f9de246d76af07c9900891a9ee1705932504e141d073ab0dbcb8c` | 822 |

Provenance headers in the Markdown tables match the actual raw source hashes;
artifact `sha256` values were verified against the bytes on disk.

### Verification performed

| check | result |
|---|---|
| focused tests (config, evidence, provenance, tables, manifests, CLI) | 58 passed, 15.48 s |
| full suite | **291 passed**, exit 0, 142.53 s |
| canonical full run A | exit 0; all 5 experiments `ok`; tables `written`; 18.66 min |
| canonical full run B | exit 0; all 5 experiments `ok`; tables `written`; 15.50 min |
| repeated-run digest comparison | identical `result_digest`; different `performance_digest`; raw hashes differ |
| quick reproduce x2 over canonical stored results | exit 0 both; identical `result_digest` `1174168bb24ca6195b5ef4193a06dd931813baf9bde8ca6791ef33bef6bf56d8`; tables `not_run` |
| `crest experiment tables` on canonical results | exit 0; all table bytes unchanged |
| `crest --version` | `crest 0.4.0` |
| wheel | `crest-0.4.0-py3-none-any.whl`, 107,051 bytes, exit 0; provenance module included |
| `git diff --check` | clean |

### Limits

- The runs were on one Windows machine. Cross-machine reproducibility of raw
  timing bytes and `performance_digest` is not claimed.
- `working_tree_dirty` was `true` during the full runs because the
  implementation was not yet committed; `git_commit` records the baseline
  `3b7fd042...`, and the manifest is honest about the dirty state.
- No external replication, independent implementation, production deployment,
  or real-workload longitudinal evaluation was performed.
- Generalization evidence remains fixture/holdout-scale.
