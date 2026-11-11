<!-- crest-table schema=1 config_digest=34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf canonical=true sources=ablations.jsonl=sha256:3931382f1ae9d8f5fa980b837ff91b3f45de9bba73e56a1aee7740d37b2bf0da;confidence_sensitivity.jsonl=sha256:3e1576bf35ef77ffa8eaa2349b8bda7b83e73d02ebe0196a4a10e8ddc92010bd;cross_distribution.jsonl=sha256:c12394f7b269304f84d4559c140542383c9ff16bfedb234d9f11084dc30a263e;drift.jsonl=sha256:eb307a7ac70129698a40508d413e321bad8a724d3ae4765f8b228fca05671bec;exposure_sweep.jsonl=sha256:803b0d18a9b4e22e939d30abf23bb2d0bcec6606c82b64a9f1aa0f15c487e0a1 -->

| action | family | recovery | adversarial_shift | iid_holdout | level2_holdout | level3_holdout | parameter_shift | structural_shift | training | verification |
|---|---|---|---|---|---|---|---|---|---|---|
| delete_file | filesystem.single_file | restore_from_snapshot | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| delete_file | filesystem.single_file | overfit_distractor_gate | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| delete_file | filesystem.single_file | noop_fault | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| delete_file | filesystem.directory_tree | restore_from_snapshot | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| delete_file | filesystem.directory_tree | overfit_distractor_gate | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 |
| delete_file | filesystem.directory_tree | noop_fault | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| modify_file | filesystem.single_file | restore_from_snapshot | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| modify_file | filesystem.single_file | overfit_distractor_gate | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| modify_file | filesystem.single_file | noop_fault | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| modify_file | filesystem.directory_tree | restore_from_snapshot | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| modify_file | filesystem.directory_tree | overfit_distractor_gate | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 |
| modify_file | filesystem.directory_tree | noop_fault | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
