<!-- crest-table schema=1 config_digest=34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf canonical=true sources=ablations.jsonl=sha256:e74b5cf10ebd7a400d9183bc92eca03c6373ab6aa27b641375be53b1546ddda3;confidence_sensitivity.jsonl=sha256:4152de91ed4a4b21471021247d83873eca4f7517b0be87bcc3c6a0e18d4bb0c5;cross_distribution.jsonl=sha256:fd96aec907d5a63d5b90035edde4e3858409c17d0f6573f0cbc43b6edc398a1e;drift.jsonl=sha256:e126aa8a593ac8089478aac84511a596f3f09ad14a742b41f91d96f77a84d083;exposure_sweep.jsonl=sha256:5de7a436a2d7e2a5aa5a6fb3cc63f00ae8cddf5188ce388a2021ffd8cb1aa7f6 -->

| mode | action | family | recovery | evidence class | admitted | eval success | false admission | false rejection | cost (s) |
|---|---|---|---|---|---|---|---|---|---|
| fixture_only | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 4.215 |
| fixture_only | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 2.95 |
| fixture_only | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 9.534 |
| fixture_only | delete_file | filesystem.directory_tree | overfit_distractor_gate | VERIFIED_FIXTURE | True | 0.25 | True | False | 8.405 |
| fixture_only | modify_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 6.0 |
| fixture_only | modify_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 3.237 |
| fixture_only | modify_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 7.715 |
| fixture_only | modify_file | filesystem.directory_tree | overfit_distractor_gate | VERIFIED_FIXTURE | True | 0.25 | True | False | 11.866 |
| family_evidence | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 21.282 |
| family_evidence | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 16.398 |
| family_evidence | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 26.33 |
| family_evidence | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 12.535 |
| family_evidence | modify_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 10.932 |
| family_evidence | modify_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 8.989 |
| family_evidence | modify_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 17.076 |
| family_evidence | modify_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 14.955 |
| generalized_evidence | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 14.449 |
| generalized_evidence | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 10.831 |
| generalized_evidence | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 19.739 |
| generalized_evidence | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 14.099 |
| generalized_evidence | modify_file | filesystem.single_file | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 13.004 |
| generalized_evidence | modify_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 12.746 |
| generalized_evidence | modify_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 25.573 |
| generalized_evidence | modify_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 14.371 |
