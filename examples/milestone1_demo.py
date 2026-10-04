"""Milestone-1 demo: delete_file end-to-end, then deliberate recovery breakage."""
from __future__ import annotations

from datetime import datetime, timezone

from crest.constitution import Constitution
from crest.ledger import ExposureLedger
from crest.learner import HeuristicProposer
from crest.recovery import RecoveryProgram
from crest.runtime import RecoveryProbeFailure, Runtime, SecurityError
from crest.verifier import TestConfig
from crest.workspace import Workspace

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def main() -> None:
    rt = Runtime(
        constitution=Constitution(
            e_max=1.0,
            min_recovery_success_rate=0.95,
            max_recovery_p99_ms=10000.0,
            allowed_action_classes=frozenset({"delete_file"}),
            receipt_ttl_seconds=3600.0,
            exposure_window_seconds=3600.0,
        ),
        ledger=ExposureLedger(),
    )
    ws = Workspace.temporary()
    try:
        ws.write("a.txt", b"important data")

        print("1. learner proposes recovery:")
        recovery = HeuristicProposer().propose("delete_file", "a.txt")
        print(f"   -> {recovery.kind} (digest {recovery.digest[:12]}...)")

        print("2. independent verifier tests it:")
        decision = rt.evaluate_and_admit(
            action_class="delete_file", target_scope="*", target="a.txt", params={},
            recovery=recovery, test_config=TestConfig(trials=8, repeat_trials=2, seed=7), now=NOW,
        )
        receipt = rt.receipts.get("delete_file")
        if receipt:
            print(f"   -> status={receipt.status} success_rate={receipt.evidence.recovery_success_rate:.3f} p99={receipt.evidence.recovery_latency_p99_ms:.2f}ms")
        print(f"   -> admission: allow={decision.allow} reasons={decision.reasons}")
        print(f"   -> capability state: {rt.capability('delete_file').state}")

        print("3. agent executes delete_file autonomously:")
        res = rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.2, now=NOW)
        print(f"   -> {res}; a.txt exists: {ws.exists('a.txt')}")
        print(f"   -> ledger exposure: {rt.ledger.total():.2f}")

        print("4. simulate environment drift: recovery program stops restoring:")
        rt.register_recovery_program("delete_file", RecoveryProgram(kind="noop"))
        ws.write("b.txt", b"other")
        try:
            rt.execute(ws, action_class="delete_file", target="b.txt", estimated_exposure=0.2, now=NOW)
        except RecoveryProbeFailure as e:
            print(f"   -> probe failed: {e}; capability revoked -> {rt.capability('delete_file').state}")

        print("5. action now denied; fresh verification required:")
        try:
            rt.execute(ws, action_class="delete_file", target="b.txt", estimated_exposure=0.2, now=NOW)
        except SecurityError as e:
            print(f"   -> denied: {e}")
    finally:
        ws.cleanup()


if __name__ == "__main__":
    main()
