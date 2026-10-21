<!-- crest-table schema=1 config_digest=34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf canonical=true sources=ablations.jsonl=sha256:afeffa6dee08b2d7025ea3c3c108697c05e275a2d30ea46a66574ec2049209ca;confidence_sensitivity.jsonl=sha256:1209b43eb1f4830af7f3d35fb7c5781ac4b972ec2e5daf93f4dae76c1b922225;cross_distribution.jsonl=sha256:ee01edbc95b38f88839b06f9a48318eed8f179b17858d729090fd8ce4e29b509;drift.jsonl=sha256:cd67eda1b53280065962ce876ad19eaf8cec94a51055e62a3a5261ccbb715982;exposure_sweep.jsonl=sha256:3a5d28ae2a72ff0b7dac9250af11cb731b7e57286ae41e6418b17e0f573c1840 -->

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
| fixture_only | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 5.261 |
| fixture_only | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 3.054 |
| fixture_only | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 9.333 |
| fixture_only | delete_file | filesystem.directory_tree | overfit_distractor_gate | VERIFIED_FIXTURE | True | 0.25 | True | False | 9.46 |
| fixture_only | modify_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 4.303 |
| fixture_only | modify_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 2.842 |
| fixture_only | modify_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FIXTURE | True | 1.00 | False | False | 9.192 |
| fixture_only | modify_file | filesystem.directory_tree | overfit_distractor_gate | VERIFIED_FIXTURE | True | 0.25 | True | False | 9.262 |
| family_evidence | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 11.612 |
| family_evidence | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 8.452 |
| family_evidence | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 17.488 |
| family_evidence | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 14.919 |
| family_evidence | modify_file | filesystem.single_file | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 12.349 |
| family_evidence | modify_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 9.526 |
| family_evidence | modify_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_FAMILY | True | 1.00 | False | False | 18.443 |
| family_evidence | modify_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 15.911 |
| generalized_evidence | delete_file | filesystem.single_file | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 11.272 |
| generalized_evidence | delete_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 9.297 |
| generalized_evidence | delete_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 18.085 |
| generalized_evidence | delete_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 14.884 |
| generalized_evidence | modify_file | filesystem.single_file | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 4.239 |
| generalized_evidence | modify_file | filesystem.single_file | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 8.007 |
| generalized_evidence | modify_file | filesystem.directory_tree | restore_from_snapshot | VERIFIED_GENERAL | True | 1.00 | False | False | 18.121 |
| generalized_evidence | modify_file | filesystem.directory_tree | overfit_distractor_gate | UNVERIFIED | False | 0.25 | False | False | 16.009 |

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
| directory_structure_changed | True | implemented | 0.5787 | target_moved_or_renamed: nested/a.txt no longer  |
| directory_structure_changed | True | implemented | 0.5988 | target_moved_or_renamed: nested/a.txt no longer  |
| directory_structure_changed | True | implemented | 0.6504 | target_moved_or_renamed: nested/a.txt no longer  |
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
