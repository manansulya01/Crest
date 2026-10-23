"""Configuration: the *policy* boundary. Invariants in this module are
non-overridable; only the declared fields are configurable, and none of it
can be written by the agent/learner."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .inference import InferencePolicy
from .policy import EvidencePolicy, FamilyPolicy, GeneralPolicy, StatisticsPolicy

DEFAULT_SHELL_ALLOWLIST = [
    "pwd", "ls", "dir", "git status", "git diff", "python --version", "echo",
]


@dataclass(frozen=True)
class ResourceLimits:
    """Bounds on verification work, to avoid verification-induced DoS."""
    max_verification_seconds: float = 300.0
    max_verification_cases: int = 500
    max_holdout_cases: int = 500
    max_shift_cases: int = 200
    max_fixture_files: int = 5000
    max_adapter_output_bytes: int = 256 * 1024
    max_shell_output_bytes: int = 64 * 1024
    max_argument_bytes: int = 64 * 1024


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
    min_evidence_class: str = "VERIFIED_FIXTURE"
    shell_allowlist: tuple[str, ...] = tuple(DEFAULT_SHELL_ALLOWLIST)
    state_dir: Path | None = None
    audit_path: Path | None = None
    dry_run: bool = False
    policy_version: str = "policy-v1"
    mode: str = "production"  # production | research
    inference_policy: InferencePolicy = field(default_factory=InferencePolicy)
    evidence_policy: EvidencePolicy = field(default_factory=EvidencePolicy)
    limits: "ResourceLimits" = field(default_factory=lambda: ResourceLimits())

    @property
    def resolved_state_dir(self) -> Path:
        return self.state_dir or (Path(self.workspace_root) / ".crest")

    @property
    def resolved_audit_path(self) -> Path:
        return self.audit_path or (self.resolved_state_dir / "audit.jsonl")

    def validate(self) -> None:
        problems = []
        if self.e_max <= 0:
            problems.append("e_max must be positive")
        if self.exposure_window_seconds <= 0:
            problems.append("exposure_window_seconds must be positive")
        if not 0 < self.min_recovery_success_rate <= 1:
            problems.append("min_recovery_success_rate in (0,1]")
        if self.max_recovery_p99_ms <= 0:
            problems.append("max_recovery_p99_ms must be positive")
        if self.receipt_ttl_seconds <= 0:
            problems.append("receipt_ttl_seconds must be positive")
        if self.min_evidence_class not in ("UNVERIFIED", "VERIFIED_FIXTURE", "VERIFIED_FAMILY", "VERIFIED_GENERAL"):
            problems.append(f"invalid min_evidence_class {self.min_evidence_class}")
        if self.mode not in ("production", "research"):
            problems.append("mode must be production or research")
        if self.limits.max_verification_cases <= 0 or self.limits.max_holdout_cases <= 0 or self.limits.max_shift_cases <= 0:
            problems.append("verification case limits must be positive")
        if self.limits.max_verification_seconds <= 0:
            problems.append("max_verification_seconds must be positive")
        try:
            self.evidence_policy.validate()
        except ValueError as exc:
            problems.append(str(exc))
        # production mode must not be configured with an internally
        # inconsistent evidence policy (already validated above); research
        # mode additionally permits experimental minima.
        if problems:
            raise ValueError("invalid CrestConfig: " + "; ".join(problems))


def load(path: Path | str) -> CrestConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("config must be a YAML mapping")
    allowed_sections = {"workspace", "exposure", "admission", "revocation", "runtime", "shell", "state", "audit", "evidence", "statistics", "limits", "policy", "inference"}
    unknown = set(data) - allowed_sections
    if unknown:
        raise ValueError(f"unknown config sections (typo or tampering): {sorted(unknown)}")
    root = Path(data.get("workspace", {}).get("root", "."))
    exposure = data.get("exposure", {})
    admission = data.get("admission", {})
    revocation = data.get("revocation", {})
    runtime = data.get("runtime", {})
    shell_raw = data.get("shell", {}).get("allowlist")
    state_raw = data.get("state", {}).get("dir")
    audit_raw = data.get("audit", {}).get("path")
    ev_raw = data.get("evidence", {})
    stats_raw = data.get("statistics", {})
    limits_raw = data.get("limits", {})
    policy = EvidencePolicy(
        fixture_requires_exact_scope=bool(ev_raw.get("fixture", {}).get("requires_exact_scope", True)),
        family=FamilyPolicy(
            minimum_verification_cases=int(ev_raw.get("family", {}).get("minimum_verification_cases", 10)),
            minimum_holdout_cases=int(ev_raw.get("family", {}).get("minimum_holdout_cases", 10)),
            maximum_failure_upper_bound=float(ev_raw.get("family", {}).get("maximum_failure_upper_bound", 0.05)),
        ),
        general=GeneralPolicy(
            minimum_holdout_cases=int(ev_raw.get("general", {}).get("minimum_holdout_cases", 20)),
            minimum_shift_distributions=int(ev_raw.get("general", {}).get("minimum_shift_distributions", 3)),
            maximum_failure_upper_bound=float(ev_raw.get("general", {}).get("maximum_failure_upper_bound", 0.01)),
            require_adversarial_shift=bool(ev_raw.get("general", {}).get("require_adversarial_shift", True)),
        ),
        statistics=StatisticsPolicy(
            confidence=float(stats_raw.get("confidence", 0.95)),
            minimum_samples_family=int(stats_raw.get("minimum_samples", {}).get("family", 20)),
            minimum_samples_general=int(stats_raw.get("minimum_samples", {}).get("general", 50)),
        ),
    )
    limits = ResourceLimits(
        max_verification_seconds=float(limits_raw.get("max_verification_seconds", 300.0)),
        max_verification_cases=int(limits_raw.get("max_verification_cases", 500)),
        max_holdout_cases=int(limits_raw.get("max_holdout_cases", 500)),
        max_shift_cases=int(limits_raw.get("max_shift_cases", 200)),
        max_fixture_files=int(limits_raw.get("max_fixture_files", 5000)),
        max_adapter_output_bytes=int(limits_raw.get("max_adapter_output_bytes", 256 * 1024)),
        max_shell_output_bytes=int(limits_raw.get("max_shell_output_bytes", 64 * 1024)),
        max_argument_bytes=int(limits_raw.get("max_argument_bytes", 64 * 1024)),
    )
    inf_raw = data.get("inference", {})
    inference_policy = InferencePolicy(
        allowed_models=tuple(inf_raw.get("allowed_models", InferencePolicy.allowed_models)),
        max_input_tokens=int(inf_raw.get("max_input_tokens", 4096)),
        max_output_tokens=int(inf_raw.get("max_output_tokens", 1024)),
        max_prompt_chars=int(inf_raw.get("max_prompt_chars", 32768)),
        max_output_chars=int(inf_raw.get("max_output_chars", 65536)),
        input_token_weight=float(inf_raw.get("input_token_weight", 1.0)),
        output_token_weight=float(inf_raw.get("output_token_weight", 1.0)),
        max_cost_units_per_request=float(inf_raw.get("max_cost_units_per_request", 8192.0)),
        window_seconds=float(inf_raw.get("window_seconds", 3600.0)),
        window_budget_units=float(inf_raw.get("window_budget_units", 100000.0)),
        request_timeout_seconds=float(inf_raw.get("request_timeout_seconds", 30.0)),
        allowed_finish_reasons=tuple(inf_raw.get("allowed_finish_reasons", InferencePolicy.allowed_finish_reasons)),
        require_usage=bool(inf_raw.get("require_usage", True)),
        require_nonempty_output=bool(inf_raw.get("require_nonempty_output", True)),
    )
    cfg = CrestConfig(
        workspace_root=root,
        e_max=float(exposure.get("max_window_exposure", 1.0)),
        exposure_window_seconds=float(exposure.get("window_seconds", 3600.0)),
        min_recovery_success_rate=float(admission.get("min_recovery_success_rate", 0.95)),
        max_recovery_p99_ms=float(admission.get("max_recovery_p99_ms", 10000.0)),
        allowed_action_classes=tuple(admission.get("allowed_action_classes", CrestConfig.allowed_action_classes)),
        receipt_ttl_seconds=float(admission.get("max_receipt_age_seconds", 3600.0)),
        require_receipt=bool(admission.get("require_receipt", True)),
        allow_fixture_evidence=bool(admission.get("allow_fixture_evidence", True)),
        min_evidence_class=str(admission.get("min_evidence_class", "VERIFIED_FIXTURE")),
        shell_allowlist=tuple(shell_raw) if shell_raw else tuple(DEFAULT_SHELL_ALLOWLIST),
        state_dir=Path(state_raw) if state_raw else None,
        audit_path=Path(audit_raw) if audit_raw else None,
        dry_run=bool(runtime.get("dry_run", False)),
        policy_version=str(data.get("policy", {}).get("version", "policy-v1")),
        mode=str(data.get("runtime", {}).get("mode", "production")),
        evidence_policy=policy,
        limits=limits,
        inference_policy=inference_policy,
    )
    cfg.validate()
    return cfg


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
  min_evidence_class: VERIFIED_FIXTURE
  max_receipt_age_seconds: 3600
  min_recovery_success_rate: 0.95
  max_recovery_p99_ms: 10000
evidence:
  fixture:
    requires_exact_scope: true
  family:
    minimum_verification_cases: 10
    minimum_holdout_cases: 10
    maximum_failure_upper_bound: 0.05
  general:
    minimum_holdout_cases: 20
    minimum_shift_distributions: 3
    maximum_failure_upper_bound: 0.01
    require_adversarial_shift: true
statistics:
  confidence: 0.95
  minimum_samples:
    family: 20
    general: 50
limits:
  max_verification_seconds: 300
  max_verification_cases: 500
  max_holdout_cases: 500
  max_shift_cases: 200
inference:
  allowed_models:
    - fake-echo
  max_input_tokens: 4096
  max_output_tokens: 1024
  max_prompt_chars: 32768
  max_output_chars: 65536
  input_token_weight: 1.0
  output_token_weight: 1.0
  max_cost_units_per_request: 8192.0
  window_seconds: 3600
  window_budget_units: 100000.0
  request_timeout_seconds: 30.0
  allowed_finish_reasons:
    - stop
  require_usage: true
  require_nonempty_output: true
policy:
  version: policy-v1
revocation:
  enabled: true
  immediate: true
runtime:
  dry_run: false
  # production (default) fails closed; research permits experimental
  # verification policies and verbose experiment tooling.
  mode: production
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
