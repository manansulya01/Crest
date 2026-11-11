<!-- crest-table schema=1 config_digest=34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf canonical=true sources=ablations.jsonl=sha256:e74b5cf10ebd7a400d9183bc92eca03c6373ab6aa27b641375be53b1546ddda3;confidence_sensitivity.jsonl=sha256:4152de91ed4a4b21471021247d83873eca4f7517b0be87bcc3c6a0e18d4bb0c5;cross_distribution.jsonl=sha256:fd96aec907d5a63d5b90035edde4e3858409c17d0f6573f0cbc43b6edc398a1e;drift.jsonl=sha256:e126aa8a593ac8089478aac84511a596f3f09ad14a742b41f91d96f77a84d083;exposure_sweep.jsonl=sha256:5de7a436a2d7e2a5aa5a6fb3cc63f00ae8cddf5188ce388a2021ffd8cb1aa7f6 -->

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
