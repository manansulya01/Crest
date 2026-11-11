<!-- crest-table schema=1 config_digest=34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf canonical=true sources=ablations.jsonl=sha256:e74b5cf10ebd7a400d9183bc92eca03c6373ab6aa27b641375be53b1546ddda3;confidence_sensitivity.jsonl=sha256:4152de91ed4a4b21471021247d83873eca4f7517b0be87bcc3c6a0e18d4bb0c5;cross_distribution.jsonl=sha256:fd96aec907d5a63d5b90035edde4e3858409c17d0f6573f0cbc43b6edc398a1e;drift.jsonl=sha256:e126aa8a593ac8089478aac84511a596f3f09ad14a742b41f91d96f77a84d083;exposure_sweep.jsonl=sha256:5de7a436a2d7e2a5aa5a6fb3cc63f00ae8cddf5188ce388a2021ffd8cb1aa7f6 -->

# Crest V0.4 result tables (generated)

## cross distribution
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

## ablations
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

## exposure sweep
| E_max | executed | denied | certified exposure | AAC | GAC |
|---|---|---|---|---|---|
| 0.1 | 0 | 4 | 0.0 | 0.0 | 0.0 |
| 0.25 | 1 | 3 | 0.2 | 0.5 | 0.0 |
| 0.5 | 2 | 2 | 0.4 | 0.5 | 0.0 |
| 1.0 | 3 | 1 | 0.8 | 1.0 | 0.0 |

## confidence sensitivity
| confidence | action | family | recovery | evidence class | admitted | eval success | false admission |
|---|---|---|---|---|---|---|---|
| 0.9 | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False |
| 0.9 | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.17 | False |
| 0.9 | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False |
| 0.9 | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.17 | False |
| 0.95 | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False |
| 0.95 | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.17 | False |
| 0.95 | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False |
| 0.95 | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.17 | False |
| 0.99 | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False |
| 0.99 | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.17 | False |
| 0.99 | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False |
| 0.99 | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.17 | False |
| 0.999 | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False |
| 0.999 | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.17 | False |
| 0.999 | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False |
| 0.999 | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.17 | False |

## drift
| drift class | detected | implementation | detection latency (ms) | reason |
|---|---|---|---|---|
| target_moved | False | implemented | - | no drift detected |
| target_moved | False | implemented | - | no drift detected |
| target_moved | False | implemented | - | no drift detected |
| target_renamed | False | implemented | - | no drift detected |
| target_renamed | False | implemented | - | no drift detected |
| target_renamed | False | implemented | - | no drift detected |
| directory_structure_changed | True | implemented | 2.6305 | target_moved_or_renamed: nested/a.txt no longer  |
| directory_structure_changed | True | implemented | 2.7441 | target_moved_or_renamed: nested/a.txt no longer  |
| directory_structure_changed | True | implemented | 2.7085 | target_moved_or_renamed: nested/a.txt no longer  |
| additional_distractors | None | unimplemented | - | no drift detected |
| additional_distractors | None | unimplemented | - | no drift detected |
| additional_distractors | None | unimplemented | - | no drift detected |
| scope_changed | None | unimplemented | - | no drift detected |
| scope_changed | None | unimplemented | - | no drift detected |
| scope_changed | None | unimplemented | - | no drift detected |
| file_content_changed | None | unimplemented | - | no drift detected |
| file_content_changed | None | unimplemented | - | no drift detected |
| file_content_changed | None | unimplemented | - | no drift detected |
| symlink_introduced | None | unimplemented | - | no drift detected |
| symlink_introduced | None | unimplemented | - | no drift detected |
| symlink_introduced | None | unimplemented | - | no drift detected |
| git_state_changed | None | unimplemented | - | no drift detected |
| git_state_changed | None | unimplemented | - | no drift detected |
| git_state_changed | None | unimplemented | - | no drift detected |

summary: {"cases": 24, "detection_rate_implemented": 0.3333, "false_negative_rate_implemented": 0.6667, "implemented_classes": ["directory_structure_changed", "target_moved", "target_renamed"], "unimplemented_classes": ["additional_distractors", "file_content_changed", "git_state_changed", "scope_changed", "symlink_introduced"]}
