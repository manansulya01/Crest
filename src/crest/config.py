"""Configuration: the *policy* boundary. Invariants in this module are
non-overridable; only the declared fields are configurable, and none of it
can be written by the agent/learner."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_SHELL_ALLOWLIST = [
    "pwd", "ls", "dir", "git status", "git diff", "python --version", "echo",
]


@dataclass(frozen=True)
class CrestConfig:
    workspace_root: Path
    e_max: float = 1.0
    exposure_window_seconds: float = 3600.0
    min_recovery_success_rate: float = 0.95
    max_recovery_p99_ms: float = 10000.0
    allowed_action_classes: tuple[str, ...] = (
        "create_file", "modify_file", "move_file", "delete_file", "create_record", "modify_record", "delete_record", "delete_directory",
        "git_create_branch", "git_modify_file", "git_commit", "shell_command",
    )
    receipt_ttl_seconds: float = 3600.0
    require_receipt: bool = True
    allow_fixture_evidence: bool = True
    shell_allowlist: tuple[str, ...] = tuple(DEFAULT_SHELL_ALLOWLIST)
    state_dir: Path | None = None
    audit_path: Path | None = None
    dry_run: bool = False

    @property
    def resolved_state_dir(self) -> Path:
        return self.state_dir or (Path(self.workspace_root) / ".crest")

    @property
    def resolved_audit_path(self) -> Path:
        return self.audit_path or (self.resolved_state_dir / "audit.jsonl")


def load(path: Path | str) -> CrestConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    root = Path(data.get("workspace", {}).get("root", "."))
    exposure = data.get("exposure", {})
    admission = data.get("admission", {})
    revocation = data.get("revocation", {})
    runtime = data.get("runtime", {})
    shell_raw = data.get("shell", {}).get("allowlist")
    state_raw = data.get("state", {}).get("dir")
    audit_raw = data.get("audit", {}).get("path")
    return CrestConfig(
        workspace_root=root,
        e_max=float(exposure.get("max_window_exposure", 1.0)),
        exposure_window_seconds=float(exposure.get("window_seconds", 3600.0)),
        min_recovery_success_rate=float(admission.get("min_recovery_success_rate", 0.95)),
        max_recovery_p99_ms=float(admission.get("max_recovery_p99_ms", 10000.0)),
        allowed_action_classes=tuple(admission.get("allowed_action_classes", CrestConfig.allowed_action_classes)),
        receipt_ttl_seconds=float(admission.get("max_receipt_age_seconds", 3600.0)),
        require_receipt=bool(admission.get("require_receipt", True)),
        allow_fixture_evidence=bool(admission.get("allow_fixture_evidence", True)),
        shell_allowlist=tuple(shell_raw) if shell_raw else tuple(DEFAULT_SHELL_ALLOWLIST),
        state_dir=Path(state_raw) if state_raw else None,
        audit_path=Path(audit_raw) if audit_raw else None,
        dry_run=bool(runtime.get("dry_run", False)),
    )


def default_yaml(root: Path) -> str:
    return f"""workspace:
  root: {root.as_posix()}
exposure:
  max_window_exposure: 1.0
  window_seconds: 3600
admission:
  require_receipt: true
  require_verified_recovery: true
  # V0 receipts are VERIFIED_FIXTURE: they prove reversibility of the
  # tested fixture, not general recoverability. Set false to demand
  # VERIFIED_GENERAL receipts once such verification exists.
  allow_fixture_evidence: true
  max_receipt_age_seconds: 3600
  min_recovery_success_rate: 0.95
  max_recovery_p99_ms: 10000
revocation:
  enabled: true
  immediate: true
runtime:
  dry_run: false
shell:
  allowlist:
    - pwd
    - ls
    - dir
    - git status
    - git diff
    - python --version
    - echo
"""
