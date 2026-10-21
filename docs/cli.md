# CLI

```
crest init [--root P]
crest status
crest config
crest capabilities list|show <id>|revoke <id> [--reason R]
crest receipts list|show <id>
crest audit [--limit N]
crest policy check --tool T --operation O [--arg k=v]...
crest verify --action A --recovery KIND [--scope S] [--target T] [--trials N] [--seed N]
crest exec <tool> <operation> [--arg k=v]... [--dry-run]
crest verify-generalized --action A --recovery KIND [--families a,b] [--scope S]
crest evidence list
crest doctor
crest benchmark [admission|security|generalization|drift|all]
crest report
crest experiment {cross-distribution|ablations|exposure-sweep|confidence|drift|tables|conclusion|holdout}
crest research reproduce [--full] [--samples N]
```

Exit codes: 0 ok; 3 denied/security failure; 4 not found; 2 operational
error (invalid config, corrupt store, unknown sections — clean `ERROR:`
message, no traceback). argparse errors: 2.

`research reproduce` reports execution success (0) or operational failure
(2); the scientific verdict is reported separately in its manifest. Quick
mode never writes research artifacts; `--full` regenerates
`experiments/tables/*` only for canonical runs whose experiments all
succeeded. `--samples N` requires `--full`, applies to the ablations,
cross-distribution, and confidence arms, marks the run non-canonical (even
when N equals the canonical value), and can never replace the canonical
tables. Manifests use schema 3: `result_digest` covers scientific content
(normalized source and table content, configuration, evidence, failures)
while `performance_digest` covers run duration, timing/latency observations,
and raw byte hashes. Canonical parameters, exact digest coverage, and
provenance details are documented in `docs/research-v0.4.md`.

Examples:

```bash
crest exec filesystem create_file --arg path=tmp/a.txt --arg content=hello
crest exec shell command --arg command="git status"
crest exec git create_branch --arg name=feat/x
```
