"""Runtime: checks admission immediately before every execution.

The caller does not perform these checks; the runtime does.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .actions import ACTIONS
from .admission import AdmissionDecision, admit
from .capabilities import Capability, CapabilityState
from .constitution import Constitution
from .ledger import ExposureLedger
from .receipts import CapabilityReceipt
from .recovery import RecoveryContext, RecoveryProgram, get_handler
from .verifier import TestConfig, Verifier
from .workspace import Workspace


class SecurityError(Exception):
    pass


class RecoveryProbeFailure(Exception):
    pass


@dataclass
class ExecutionResult:
    ok: bool
    action_class: str
    target: str
    detail: str = ""


class Runtime:
    def __init__(
        self,
        *,
        constitution: Constitution,
        ledger: ExposureLedger,
        verifier: Verifier | None = None,
        now_fn=None,
    ):
        self.constitution = constitution
        self.ledger = ledger
        self.verifier = verifier or Verifier()
        self._now_fn = now_fn or (lambda: datetime.now().astimezone())
        self.capabilities: dict[str, Capability] = {}
        self.receipts: dict[str, CapabilityReceipt] = {}
        self._recovery_programs: dict[str, RecoveryProgram] = {}

    # ----- constitutional lifecycle (not learner-accessible) -----

    def capability(self, action_class: str) -> Capability:
        return self.capabilities.setdefault(action_class, Capability(action_class))

    def evaluate_and_admit(
        self,
        *,
        action_class: str,
        target_scope: str,
        target: str,
        params: dict[str, Any],
        recovery: RecoveryProgram,
        test_config: TestConfig,
        now: datetime | None = None,
    ) -> AdmissionDecision:
        now = now or self._now_fn()
        cap = self.capability(action_class)
        if cap.state == CapabilityState.FORBIDDEN:
            cap.transition(CapabilityState.PROPOSED)
        if cap.state == CapabilityState.REVOKED:
            cap.transition(CapabilityState.VERIFYING)
        elif cap.state == CapabilityState.PROPOSED:
            cap.transition(CapabilityState.VERIFYING)
        elif cap.state not in (CapabilityState.VERIFYING,):
            raise SecurityError(f"cannot verify from state {cap.state}")

        receipt = self.verifier.verify(
            action_class=action_class,
            target_scope=target_scope,
            target=target,
            params=params,
            recovery=recovery,
            test_config=test_config,
            now=now,
            ttl_seconds=self.constitution.receipt_ttl_seconds,
        )
        if receipt.status != "VERIFIED":
            cap.transition(CapabilityState.FORBIDDEN)
            return AdmissionDecision(allow=False, reasons=(f"verification status {receipt.status}",))

        cap.transition(CapabilityState.VERIFIED)
        decision = admit(
            receipt=receipt,
            current_exposure=self.ledger.total_in_window(now, self.constitution.exposure_window_seconds),
            constitution=self.constitution,
            now=now,
        )
        if decision.allow:
            self.receipts[action_class] = receipt
            cap.receipt_digest = receipt.bound_digest
            self._recovery_programs[action_class] = recovery
            cap.transition(CapabilityState.ADMITTED)
        else:
            cap.transition(CapabilityState.FORBIDDEN)
        return decision

    def revoke(self, action_class: str, reason: str) -> None:
        cap = self.capability(action_class)
        if cap.state in (CapabilityState.ACTIVE, CapabilityState.ADMITTED):
            cap.transition(CapabilityState.REVOKED)

    def expire(self, action_class: str) -> None:
        cap = self.capability(action_class)
        if cap.state in (CapabilityState.ACTIVE, CapabilityState.ADMITTED):
            cap.transition(CapabilityState.EXPIRED)

    # ----- execution -----

    def execute(
        self,
        workspace: Workspace,
        *,
        action_class: str,
        target: str,
        params: dict[str, Any] | None = None,
        estimated_exposure: float = 0.0,
        now: datetime | None = None,
    ) -> ExecutionResult:
        now = now or self._now_fn()
        params = dict(params or {})
        cap = self.capability(action_class)
        if not cap.executable:
            raise SecurityError(f"action {action_class!r} not admitted (state={cap.state})")

        receipt = self.receipts.get(action_class)
        if receipt is None:
            raise SecurityError("no receipt on file")
        if not receipt.is_hash_valid():
            raise SecurityError("receipt hash binding invalid")
        if receipt.is_expired(now):
            self.expire(action_class)
            raise SecurityError("receipt expired")
        if receipt.action_class != action_class:
            raise SecurityError("receipt action class mismatch")
        if not fnmatch.fnmatchcase(target, receipt.target_scope):
            raise SecurityError(f"target {target!r} outside receipt scope {receipt.target_scope!r}")
        if not self.constitution.is_action_allowed(action_class):
            raise SecurityError("action class constitutionally forbidden")

        current = self.ledger.total_in_window(now, self.constitution.exposure_window_seconds)
        if current + estimated_exposure > self.constitution.e_max:
            raise SecurityError("exposure budget would be exceeded")

        if cap.state == CapabilityState.ADMITTED:
            cap.transition(CapabilityState.ACTIVE)

        pre = workspace.snapshot()
        try:
            ACTIONS[action_class](workspace, target, params)
        except Exception as exc:
            self.ledger.record(estimated_exposure, now, action_class, target, reason=f"failed execution: {exc}")
            self.revoke(action_class, f"execution failed: {exc}")
            raise

        self.ledger.record(estimated_exposure, now, action_class, target, reason="execution")

        probe = Workspace.temporary()
        try:
            for rel, data in pre.items():
                probe.write(rel, data)
            ACTIONS[action_class](probe, target, params)
            rec = self._recovery_programs.get(action_class)
            if rec is None or get_handler(rec.kind) is None:
                raise RecoveryProbeFailure("no recovery handler")
            get_handler(rec.kind)(probe, RecoveryContext(action_class, target, params, pre))
            if not probe.state_matches(pre):
                self.revoke(action_class, "recovery probe failed")
                raise RecoveryProbeFailure("recovery did not restore pre-action state")
        finally:
            probe.cleanup()

        return ExecutionResult(ok=True, action_class=action_class, target=target)

    def register_recovery_program(self, action_class: str, program: RecoveryProgram) -> None:
        self._recovery_programs[action_class] = program
