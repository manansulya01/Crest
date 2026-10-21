<!-- crest-table schema=1 config_digest=34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf canonical=true sources=ablations.jsonl=sha256:afeffa6dee08b2d7025ea3c3c108697c05e275a2d30ea46a66574ec2049209ca;confidence_sensitivity.jsonl=sha256:1209b43eb1f4830af7f3d35fb7c5781ac4b972ec2e5daf93f4dae76c1b922225;cross_distribution.jsonl=sha256:ee01edbc95b38f88839b06f9a48318eed8f179b17858d729090fd8ce4e29b509;drift.jsonl=sha256:cd67eda1b53280065962ce876ad19eaf8cec94a51055e62a3a5261ccbb715982;exposure_sweep.jsonl=sha256:3a5d28ae2a72ff0b7dac9250af11cb731b7e57286ae41e6418b17e0f573c1840 -->

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
