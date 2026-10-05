"""Crest Runtime v0: the security-critical control plane.

LEARN != VERIFY != ADMIT. This class is the only path to execution.
"""
from __future__ import annotations

import fnmatch
import json
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .actions import ALL_ACTION_CLASSES
from .adapters.filesystem import AdapterContext, FilesystemAdapter
from .adapters.git import GitAdapter
from .adapters.shell import ShellAdapter
from .capabilities import Capability, CapabilityState
from .config import CrestConfig, load as load_config
from .constitution import Constitution
from .gateway import ToolRequest, ToolResult
from .paths import WorkspaceViolation, canonical_within, relative_posix, scope_matches
from .receipts import CapabilityReceipt, RecoveryEvidence
from .recovery import RecoveryContext, RecoveryProgram, get_handler
from .store import CapabilityRow, SecurityStateCorrupt, Store
from .verifier import TestConfig, Verifier
from .workspace import Workspace

EVIDENCE_VERIFIED_FIXTURE = "VERIFIED_FIXTURE"
EVIDENCE_VERIFIED_GENERAL = "VERIFIED_GENERAL"

DEFAULT_EXPOSURE = {
    ("filesystem", "create_file"): 0.1,
    ("filesystem", "modify_file"): 0.2,
    ("filesystem", "move_file"): 0.2,
    ("filesystem", "delete_file"): 0.4,
    ("filesystem", "delete_directory"): 0.6,
    ("git", "create_branch"): 0.1,
    ("git", "modify_file"): 0.2,
    ("git", "commit"): 0.3,
    ("shell", "command"): 0.05,
}

GIT_OPERATIONS = {"create_branch", "modify_file", "commit"}
FILESYSTEM_OPERATIONS = {"create_file", "modify_file", "move_file", "delete_file", "delete_directory"}


class _Denied(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Decision:
    allowed: bool
    reason: str
    target: str | None = None
    capability_id: str | None = None
    receipt_id: str | None = None
    exposure_before: float = 0.0
    exposure_after: float = 0.0

    def to_audit(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "target": self.target,
            "capability_id": self.capability_id,
            "receipt_id": self.receipt_id,
            "exposure_before": self.exposure_before,
            "exposure_after": self.exposure_after,
        }


def _operation_action(tool: str, operation: str) -> str:
    if tool == "filesystem":
        return operation
    if tool == "git":
        return {"create_branch": "git_create_branch", "modify_file": "git_modify_file", "commit": "git_commit"}[operation]
    if tool == "shell":
        return "shell_command"
    raise _Denied(f"UNKNOWN_TOOL:{tool}")


class CrestRuntime:
    def __init__(self, config: CrestConfig):
        self.config = config
        self.lock = threading.RLock()
        Path(self.config.workspace_root).mkdir(parents=True, exist_ok=True)
        self.config.resolved_state_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.store = Store(self.config.resolved_state_dir / "crest.db")
        except SecurityStateCorrupt:
            raise
        self.verifier = Verifier()

    @classmethod
    def from_config(cls, path: str | Path) -> "CrestRuntime":
        return cls(load_config(path))

    def close(self) -> None:
        self.store.close()

    # ---------- management ----------

    def verify_and_admit(
        self,
        *,
        action_class: str,
        scope: str,
        recovery: RecoveryProgram,
        target: str,
        trials: int = 8,
        seed: int = 7,
        evidence_classification: str = EVIDENCE_VERIFIED_FIXTURE,
    ) -> dict[str, Any]:
        """Run independent verification, store receipt, admit capability."""
        with self.lock:
            decision = self._evaluate_research(
                action_class=action_class,
                target_scope=scope,
                target=target,
                recovery=recovery,
                trials=trials,
                seed=seed,
            )
            receipt = decision["receipt"]
            if not decision["allowed"]:
                return {"receipt_id": receipt.bound_digest[:16], "status": receipt.status, "admitted": False, "reason": decision["reason"]}
            return self._admit_from_receipt(receipt, action_class, scope, evidence_classification, recovery)

    def _evaluate_research(self, *, action_class, target_scope, target, recovery, trials, seed) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        constitution_snapshot = {
            "e_max": self.config.e_max,
            "min": self.config.min_recovery_success_rate,
            "max_p99": self.config.max_recovery_p99_ms,
        }
        receipt = self.verifier.verify(
            action_class=action_class, target_scope=target_scope, target=target, params={},
            recovery=recovery, test_config=TestConfig(trials=trials, repeat_trials=max(1, trials // 4), seed=seed),
            now=now, ttl_seconds=self.config.receipt_ttl_seconds,
        )
        ok = receipt.status == "VERIFIED" and receipt.evidence.recovery_success_rate >= self.config.min_recovery_success_rate and receipt.evidence.recovery_latency_p99_ms <= self.config.max_recovery_p99_ms
        return {
            "allowed": ok and action_class in self.config.allowed_action_classes,
            "reason": "ok" if ok else f"verification status={receipt.status}",
            "receipt": receipt,
            "constitution": constitution_snapshot,
        }

    def _admit_from_receipt(self, receipt: CapabilityReceipt, action_class: str, scope: str, classification: str, recovery: RecoveryProgram) -> dict[str, Any]:
        cap_id = f"{action_class}:{scope}"
        now = datetime.now(timezone.utc).isoformat()
        payload = receipt.to_dict()
        payload["recovery_program"] = {"kind": recovery.kind, "params": dict(recovery.params or {})}
        payload["evidence_classification"] = classification
        self.store.save_receipt(receipt.bound_digest[:32], action_class, scope, receipt.status, classification, receipt.verified_at, receipt.expires_at, payload)
        row = CapabilityRow(cap_id, action_class, scope, CapabilityState.ADMITTED.value, receipt.bound_digest[:32], now, now)
        # walk legal transitions from FORBIDDEN: ADMITTED is terminal legal target via explicit set
        self.store.upsert_capability(row)
        self._audit(None, None, cap_id, None, None, "CAPABILITY_ADMITTED", classification, {"receipt_id": receipt.bound_digest[:32]})
        return {"receipt_id": receipt.bound_digest[:32], "status": receipt.status, "admitted": True, "capability_id": cap_id}

    def revoke(self, capability_id: str, reason: str = "manual") -> dict[str, Any]:
        with self.lock:
            row = self.store.get_capability(capability_id)
            if row is None:
                raise KeyError(capability_id)
            if row.state not in (CapabilityState.ADMITTED.value, CapabilityState.ACTIVE.value):
                return {"revoked": False, "state": row.state}
            now = datetime.now(timezone.utc).isoformat()
            row.state = CapabilityState.REVOKED.value
            row.revoked_at = now
            row.revocation_reason = reason
            row.updated_at = now
            self.store.upsert_capability(row)
            self._audit(None, None, capability_id, None, None, "CAPABILITY_REVOKED", reason, {})
            return {"revoked": True, "state": row.state}

    def get_capability(self, capability_id: str) -> dict[str, Any] | None:
        row = self.store.get_capability(capability_id)
        return row.__dict__ if row else None

    def list_capabilities(self) -> list[dict[str, Any]]:
        return [r.__dict__ for r in self.store.list_capabilities()]

    def list_receipts(self) -> list[dict[str, Any]]:
        return self.store.list_receipts()

    def get_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        return self.store.get_receipt_payload(receipt_id)

    def audit(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.recent_audit(limit)

    def status(self) -> dict[str, Any]:
        caps = self.store.list_capabilities()
        by_state: dict[str, int] = {}
        for c in caps:
            by_state[c.state] = by_state.get(c.state, 0) + 1
        return {
            "workspace": str(self.config.workspace_root),
            "e_max": self.config.e_max,
            "exposure_total": self.store.total_exposure(),
            "capabilities": len(caps),
            "capability_states": by_state,
            "receipts": len(self.store.list_receipts()),
            "receipt_ttl_seconds": self.config.receipt_ttl_seconds,
            "dry_run": self.config.dry_run,
        }

    # ---------- decision core ----------

    def _lookup_capability(self, action_class: str, rel_target: str) -> CapabilityRow | None:
        candidates = [r for r in self.store.list_capabilities() if r.action_class == action_class]
        # exact match wins; otherwise widest first scope
        matching = [r for r in candidates if scope_matches(r.scope, rel_target)]
        if not matching:
            return None
        matching.sort(key=lambda r: len(r.scope))
        return matching[0]

    def _validate_cached_receipt(self, row: CapabilityRow, action_class: str, rel_target: str, now: datetime) -> tuple[CapabilityReceipt | None, str]:
        if not row.receipt_id:
            return None, "MISSING_RECEIPT"
        payload = self.store.get_receipt_payload(row.receipt_id)
        if payload is None:
            return None, "RECEIPT_NOT_FOUND"
        try:
            receipt = CapabilityReceipt.from_dict(payload)
        except Exception:
            return None, "RECEIPT_MALFORMED"
        if not receipt.is_hash_valid():
            return None, "RECEIPT_TAMPERED"
        if receipt.is_expired(now):
            return None, "RECEIPT_EXPIRED"
        if receipt.action_class != action_class:
            return None, "RECEIPT_ACTION_MISMATCH"
        if not scope_matches(receipt.target_scope, rel_target):
            return None, "RECEIPT_SCOPE_MISMATCH"
        classification = payload.get("evidence_classification", EVIDENCE_VERIFIED_FIXTURE)
        if classification == EVIDENCE_VERIFIED_FIXTURE and not self.config.allow_fixture_evidence:
            return None, "FIXTURE_EVIDENCE_NOT_ALLOWED"
        if receipt.status != "VERIFIED":
            return None, f"RECEIPT_STATUS:{receipt.status}"
        return receipt, "ok"

    def check(self, *, agent_id: str, tool, operation, arguments: dict[str, Any], request_id: str | None = None) -> Decision:
        with self.lock:
            decision = self._evaluate(agent_id, tool, operation, arguments)
            self._audit(request_id, agent_id, decision.capability_id, tool, operation,
                        "ADMISSION_ALLOWED" if decision.allowed else "ADMISSION_DENIED", decision.reason, decision.to_audit())
            return decision

    def _evaluate(self, agent_id: str, tool: str, operation: str, arguments: dict[str, Any]) -> Decision:
        try:
            action_class = _operation_action(tool, operation)
        except _Denied as e:
            return Decision(False, e.reason)
        if tool == "git" and operation not in GIT_OPERATIONS:
            return Decision(False, f"UNKNOWN_OPERATION:{operation}")
        if tool == "filesystem" and operation not in FILESYSTEM_OPERATIONS:
            return Decision(False, f"UNKNOWN_OPERATION:{operation}")
        if tool == "shell" and operation != "command":
            return Decision(False, f"UNKNOWN_OPERATION:{operation}")
        if tool not in ("filesystem", "git", "shell"):
            return Decision(False, f"UNKNOWN_TOOL:{tool}")
        if action_class not in self.config.allowed_action_classes and tool != "shell":
            return Decision(False, f"FORBIDDEN_ACTION:{action_class}")

        rel_target, abs_target, note = self._normalize_target(tool, arguments)
        if note is not None:
            return Decision(False, note, target=arguments.get("path"))

        exposure_est = float(arguments.get("exposure", DEFAULT_EXPOSURE.get((tool, operation), 0.2)))
        exposure_before = self.store.total_exposure()
        if exposure_before + exposure_est > self.config.e_max:
            return Decision(False, "EXPOSURE_BUDGET_EXCEEDED", target=rel_target, exposure_before=exposure_before, exposure_after=exposure_before)

        row = self._lookup_capability(action_class, rel_target) if tool != "shell" else None
        if tool == "shell":
            # shell uses a dedicated scope "shell:*"
            row = self._lookup_capability("shell_command", "*")
        if row is None:
            return Decision(False, "CAPABILITY_NOT_FOUND", target=rel_target)
        if row.state == CapabilityState.REVOKED.value:
            return Decision(False, "CAPABILITY_REVOKED", target=rel_target, capability_id=row.capability_id)
        if row.state == CapabilityState.EXPIRED.value:
            return Decision(False, "CAPABILITY_EXPIRED", target=rel_target, capability_id=row.capability_id)
        if row.state not in (CapabilityState.ADMITTED.value, CapabilityState.ACTIVE.value):
            return Decision(False, f"CAPABILITY_NOT_EXECUTABLE:{row.state}", target=rel_target, capability_id=row.capability_id)

        now = datetime.now(timezone.utc)
        receipt, reason = self._validate_cached_receipt(row, action_class, rel_target, now)
        if receipt is None:
            if reason == "RECEIPT_EXPIRED":
                row.state = CapabilityState.EXPIRED.value
                row.updated_at = now.isoformat()
                self.store.upsert_capability(row)
            return Decision(False, reason, target=rel_target, capability_id=row.capability_id)
        if not self.config.require_receipt and receipt is None:
            pass  # receipt is required in V0; kept structural guard
        # scope re-check is done; exposure already checked
        return Decision(True, "ADMITTED", target=rel_target, capability_id=row.capability_id, receipt_id=row.receipt_id, exposure_before=exposure_before, exposure_after=exposure_before + exposure_est)

    def _normalize_target(self, tool: str, arguments: dict[str, Any]) -> tuple[str, Path | None, str | None]:
        if tool == "shell":
            return "*", None, None
        path_arg = arguments.get("path") or arguments.get("destination") or arguments.get("cwd") or (arguments.get("paths") or [None])[0]
        if path_arg is None:
            # branch name / commit message args map to workspace root target
            return ".", Path(self.config.workspace_root).resolve(), None
        try:
            abs_target = canonical_within(self.config.workspace_root, str(path_arg))
        except WorkspaceViolation as e:
            return "", None, f"WORKSPACE_VIOLATION:{e}"
        return relative_posix(self.config.workspace_root, abs_target), abs_target, None

    # ---------- execution ----------

    def execute(self, *, agent_id: str, tool: str, operation: str, arguments: dict[str, Any], request_id: str | None = None) -> ToolResult:
        request_id = request_id or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        with self.lock:
            decision = self._evaluate(agent_id, tool, operation, arguments)
            self._audit(request_id, agent_id, decision.capability_id, tool, operation,
                        "ADMISSION_ALLOWED" if decision.allowed else "ADMISSION_DENIED", decision.reason, decision.to_audit())
            if not decision.allowed:
                return ToolResult(ok=False, request_id=request_id, agent_id=agent_id, tool=tool, operation=operation, reason=decision.reason, target=decision.target, exposure_before=decision.exposure_before, exposure_after=decision.exposure_after, duration_ms=(time.perf_counter() - start) * 1000)

            row = self.store.get_capability(decision.capability_id)
            rel_target = decision.target
            exp = float(arguments.get("exposure", DEFAULT_EXPOSURE.get((tool, operation), 0.2)))
            exposure_before = self.store.total_exposure()
            self._audit(request_id, agent_id, decision.capability_id, tool, operation, "EXECUTION_STARTED", None, {"target": rel_target})

            workspace = Workspace(Path(self.config.workspace_root))
            pre = workspace.snapshot()
            try:
                if self.config.dry_run:
                    output = {"dry_run": True}
                else:
                    ctx = AdapterContext(runtime=self, request_id=request_id, agent_id=agent_id, admitted=True, workspace_root=Path(self.config.workspace_root))
                    output = self._dispatch(tool, operation, arguments, ctx)
            except Exception as exc:
                self.store.add_exposure(exp, datetime.now(timezone.utc).isoformat(), _operation_action(tool, operation), rel_target, f"failed execution: {exc}")
                self._audit(request_id, agent_id, decision.capability_id, tool, operation, "EXECUTION_FAILED", str(exc), {})
                return ToolResult(ok=False, request_id=request_id, agent_id=agent_id, tool=tool, operation=operation, reason=f"EXECUTION_FAILED:{exc}", target=rel_target, exposure_before=exposure_before, exposure_after=self.store.total_exposure(), duration_ms=(time.perf_counter() - start) * 1000)

            now_iso = datetime.now(timezone.utc).isoformat()
            self.store.add_exposure(exp, now_iso, _operation_action(tool, operation), rel_target, "execution")
            row.state = CapabilityState.ACTIVE.value
            row.updated_at = now_iso
            self.store.upsert_capability(row)
            self._audit(request_id, agent_id, decision.capability_id, tool, operation, "EXECUTION_SUCCEEDED", None, {"output": output if isinstance(output, (dict, list, str)) else str(output)})

            # observed; filesystem ops get a re-probe on the scratch copy
            probe_note = None
            if tool == "filesystem" and not self.config.dry_run:
                probe_ok, probe_note = self._reprobe(decision, workspace, pre, _operation_action(tool, operation), arguments)
                if not probe_ok:
                    # asymmetric revocation on evidence failure in the probe
                    from .receipts import CapabilityReceipt as _CR  # noqa: F401

                    self._revoke_row(decision.capability_id, probe_note or "REPROBE_FAILED", now_iso)
                    self._audit(request_id, agent_id, decision.capability_id, tool, operation, "REPROBE_FAILED", probe_note, {})
                    return ToolResult(ok=False, request_id=request_id, agent_id=agent_id, tool=tool, operation=operation, reason=f"REPROBE_FAILED:{probe_note}", target=rel_target, exposure_before=exposure_before, exposure_after=self.store.total_exposure(), duration_ms=(time.perf_counter() - start) * 1000)

            return ToolResult(ok=True, request_id=request_id, agent_id=agent_id, tool=tool, operation=operation, reason="EXECUTED", target=rel_target, exposure_before=exposure_before, exposure_after=self.store.total_exposure(), output=output, duration_ms=(time.perf_counter() - start) * 1000)

    def _dispatch(self, tool: str, operation: str, arguments: dict[str, Any], ctx: AdapterContext) -> Any:
        if tool == "filesystem":
            return FilesystemAdapter(ctx).execute(operation, {k: v for k, v in arguments.items() if k != "exposure"})
        if tool == "git":
            return GitAdapter(ctx).execute(operation, {k: v for k, v in arguments.items() if k != "exposure"})
        if tool == "shell":
            cmd = arguments.get("command") or arguments.get("cmd") or arguments.get("argv")
            return ShellAdapter(ctx, tuple(self.config.shell_allowlist)).execute(cmd)
        raise _Denied(f"UNKNOWN_TOOL:{tool}")

    def _reprobe(self, decision: Decision, workspace: Workspace, pre: dict[str, bytes], action_class: str, arguments: dict[str, Any]) -> tuple[bool, str | None]:
        payload = self.store.get_receipt_payload(decision.receipt_id) if decision.receipt_id else None
        program_info = (payload or {}).get("recovery_program")
        if not program_info:
            return True, "no recovery program recorded; probe skipped"
        handler = get_handler(program_info.get("kind"))
        if handler is None:
            return False, f"unknown recovery handler: {program_info.get('kind')}"
        scratch = Workspace.temporary()
        try:
            for rel, data in pre.items():
                scratch.write(rel, data)
            from .actions import ACTIONS

            ACTIONS[action_class](scratch, decision.target, {k: v for k, v in arguments.items() if k != "exposure"})
            handler(scratch, RecoveryContext(action_class, decision.target, {k: v for k, v in arguments.items() if k != "exposure"}, pre))
            if not scratch.state_matches(pre):
                return False, "recovery did not restore pre-action state"
            return True, None
        except Exception as exc:
            return False, str(exc)
        finally:
            scratch.cleanup()

    def _revoke_row(self, capability_id: str, reason: str, now_iso: str) -> None:
        row = self.store.get_capability(capability_id)
        if row:
            row.state = CapabilityState.REVOKED.value
            row.revoked_at = now_iso
            row.revocation_reason = reason
            row.updated_at = now_iso
            self.store.upsert_capability(row)
        self._audit(None, None, capability_id, None, None, "CAPABILITY_REVOKED", reason, {})

    def _audit(self, request_id: str | None, agent_id: str | None, capability_id: str | None, tool: str | None, operation: str | None, event: str, reason: str | None, details: dict[str, Any]) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self.store.add_audit(ts, request_id or "-", agent_id, capability_id, tool, operation, event, reason, details)
        try:
            self.config.resolved_audit_path.parent.mkdir(parents=True, exist_ok=True)
            line = {"timestamp": ts, "request_id": request_id or "-", "agent_id": agent_id, "capability_id": capability_id, "tool": tool, "operation": operation, "decision": event, "reason": reason, **details}
            with self.config.resolved_audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, default=str) + "\n")
        except OSError:
            raise SecurityStateCorrupt("audit sink unavailable")
