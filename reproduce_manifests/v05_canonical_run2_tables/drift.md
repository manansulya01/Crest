<!-- crest-table schema=1 config_digest=34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf canonical=true sources=ablations.jsonl=sha256:3931382f1ae9d8f5fa980b837ff91b3f45de9bba73e56a1aee7740d37b2bf0da;confidence_sensitivity.jsonl=sha256:3e1576bf35ef77ffa8eaa2349b8bda7b83e73d02ebe0196a4a10e8ddc92010bd;cross_distribution.jsonl=sha256:c12394f7b269304f84d4559c140542383c9ff16bfedb234d9f11084dc30a263e;drift.jsonl=sha256:eb307a7ac70129698a40508d413e321bad8a724d3ae4765f8b228fca05671bec;exposure_sweep.jsonl=sha256:803b0d18a9b4e22e939d30abf23bb2d0bcec6606c82b64a9f1aa0f15c487e0a1 -->

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
