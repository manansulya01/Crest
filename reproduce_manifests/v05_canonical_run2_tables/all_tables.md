<!-- crest-table schema=1 config_digest=34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf canonical=true sources=ablations.jsonl=sha256:3931382f1ae9d8f5fa980b837ff91b3f45de9bba73e56a1aee7740d37b2bf0da;confidence_sensitivity.jsonl=sha256:3e1576bf35ef77ffa8eaa2349b8bda7b83e73d02ebe0196a4a10e8ddc92010bd;cross_distribution.jsonl=sha256:c12394f7b269304f84d4559c140542383c9ff16bfedb234d9f11084dc30a263e;drift.jsonl=sha256:eb307a7ac70129698a40508d413e321bad8a724d3ae4765f8b228fca05671bec;exposure_sweep.jsonl=sha256:803b0d18a9b4e22e939d30abf23bb2d0bcec6606c82b64a9f1aa0f15c487e0a1 -->

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
| fixture_only | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 4.185 |
| fixture_only | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 2.901 |
| fixture_only | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 9.411 |
| fixture_only | delete_file | filesystem.directory_tree | overfit_distractor_gate | VERIFIED_FIXTURE | True | 0.25 | True | False | 7.499 |
| fixture_only | modify_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 4.024 |
| fixture_only | modify_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 2.75 |
| fixture_only | modify_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 7.744 |
| fixture_only | modify_file | filesystem.directory_tree | overfit_distractor_gate | VERIFIED_FIXTURE | True | 0.25 | True | False | 10.878 |
| family_evidence | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 10.625 |
| family_evidence | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 8.035 |
| family_evidence | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 16.774 |
| family_evidence | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 3.776 |
| family_evidence | modify_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 10.253 |
| family_evidence | modify_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 8.302 |
| family_evidence | modify_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 15.738 |
| family_evidence | modify_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 8.607 |
| generalized_evidence | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 2.995 |
| generalized_evidence | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 7.4 |
| generalized_evidence | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 13.986 |
| generalized_evidence | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 12.993 |
| generalized_evidence | modify_file | filesystem.single_file | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 10.725 |
| generalized_evidence | modify_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 8.171 |
| generalized_evidence | modify_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 16.807 |
| generalized_evidence | modify_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 13.528 |

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
| directory_structure_changed | True | implemented | 2.6174 | target_moved_or_renamed: nested/a.txt no longer  |
| directory_structure_changed | True | implemented | 2.817 | target_moved_or_renamed: nested/a.txt no longer  |
| directory_structure_changed | True | implemented | 3.0875 | target_moved_or_renamed: nested/a.txt no longer  |
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
