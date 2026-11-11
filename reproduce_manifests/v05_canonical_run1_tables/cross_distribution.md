<!-- crest-table schema=1 config_digest=34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf canonical=true sources=ablations.jsonl=sha256:e74b5cf10ebd7a400d9183bc92eca03c6373ab6aa27b641375be53b1546ddda3;confidence_sensitivity.jsonl=sha256:4152de91ed4a4b21471021247d83873eca4f7517b0be87bcc3c6a0e18d4bb0c5;cross_distribution.jsonl=sha256:fd96aec907d5a63d5b90035edde4e3858409c17d0f6573f0cbc43b6edc398a1e;drift.jsonl=sha256:e126aa8a593ac8089478aac84511a596f3f09ad14a742b41f91d96f77a84d083;exposure_sweep.jsonl=sha256:5de7a436a2d7e2a5aa5a6fb3cc63f00ae8cddf5188ce388a2021ffd8cb1aa7f6 -->

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
