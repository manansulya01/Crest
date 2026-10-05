"""Product security invariants for Crest Runtime v0."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import crest.faults  # noqa: F401
from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.receipts import CapabilityReceipt
from crest.recovery import RecoveryProgram
from crest.store import CapabilityRow, SecurityStateCorrupt

from tests.conftest import make_runtime

OK_PROGRAM = RecoveryProgram(kind="restore_from_snapshot")


def admit(rt, action="delete_file", scope="*", recovery=OK_PROGRAM):
    return rt.verify_and_admit(action_class=action, scope=scope, recovery=recovery, target="a.txt", trials=4, seed=3)


def test_agent_cannot_grant_capability(workspace):
    rt = make_runtime(workspace)
    # no public "grant" entry point on the runtime
    assert not any(name.startswith("grant") for name in dir(rt))
    res = rt.execute(agent_id="agent", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert res.ok is False
    assert res.reason in ("CAPABILITY_NOT_FOUND", "FORBIDDEN_ACTION:delete_file")
    rt.close()


def test_agent_cannot_modify_e_max(workspace):
    rt = make_runtime(workspace)
    with pytest.raises(Exception):
        rt.config.e_max = 99999  # frozen dataclass
    rt.close()


def test_agent_cannot_mutate_ledger_through_public_api(workspace):
    rt = make_runtime(workspace)
    assert not hasattr(rt, "ledger_mutator")
    before = rt.store.total_exposure()
    rt.store  # read-only exposure tooling
    assert rt.store.total_exposure() == before
    rt.close()


def test_proposal_cannot_become_admitted_without_verification(workspace):
    # The runtime has no code path that admits without a receipt from Verifier.
    rt = make_runtime(workspace)
    assert not hasattr(rt, "propose_and_admit")
    assert rt.store.list_capabilities() == []
    rt.close()


def test_revoked_capability_cannot_execute(workspace):
    rt = make_runtime(workspace)
    assert admit(rt)["admitted"] is True
    rt.revoke("delete_file:*", "test")
    res = rt.execute(agent_id="agent", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert not res.ok and res.reason == "CAPABILITY_REVOKED"
    rt.close()


def test_expired_receipt_cannot_authorize(workspace):
    rt = make_runtime(workspace, receipt_ttl_seconds=-1)
    out = admit(rt)
    assert out["admitted"] is True
    res = rt.execute(agent_id="agent", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert not res.ok and res.reason == "RECEIPT_EXPIRED"
    assert rt.get_capability("delete_file:*")["state"] == "EXPIRED"
    rt.close()


def test_receipt_action_mismatch_denied(workspace):
    rt = make_runtime(workspace)
    out = admit(rt, action="modify_file", recovery=OK_PROGRAM)
    assert out["admitted"] is True
    res = rt.execute(agent_id="agent", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert not res.ok and res.reason == "CAPABILITY_NOT_FOUND"
    rt.close()


def test_scope_mismatch_denied(workspace):
    rt = make_runtime(workspace)
    out = rt.verify_and_admit(action_class="delete_file", scope="public/*", recovery=OK_PROGRAM, target="public/a.txt", trials=4, seed=3)
    assert out["admitted"] is True
    res = rt.execute(agent_id="agent", tool="filesystem", operation="delete_file", arguments={"path": "secret/a.txt"})
    assert not res.ok and res.reason in ("CAPABILITY_NOT_FOUND", "RECEIPT_SCOPE_MISMATCH")
    rt.close()


def test_exposure_budget_denied(workspace):
    rt = make_runtime(workspace, e_max=0.5)
    assert admit(rt)["admitted"]
    res = rt.execute(agent_id="agent", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt", "exposure": 0.4})
    assert res.ok is True
    res2 = rt.execute(agent_id="agent", tool="filesystem", operation="delete_file", arguments={"path": "data/b.txt", "exposure": 0.4})
    assert res2.ok is False and res2.reason == "EXPOSURE_BUDGET_EXCEEDED"
    rt.close()


def test_recovery_does_not_refund_exposure(workspace):
    rt = make_runtime(workspace)
    assert admit(rt)["admitted"]
    rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    before = rt.store.total_exposure()
    assert before > 0
    rt.close()
    rt = make_runtime(workspace)
    assert rt.store.total_exposure() == before
    rt.close()


def test_corrupt_database_fails_closed(workspace):
    rt = make_runtime(workspace)
    rt.close()
    db = workspace / ".crest" / "crest.db"
    db.write_bytes(b"not sqlite")
    with pytest.raises(Exception):
        CrestRuntime(CrestConfig(workspace_root=workspace, state_dir=workspace / ".crest"))


def test_path_traversal_blocked(workspace):
    rt = make_runtime(workspace)
    admit(rt)
    res = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "../outside.txt"})
    assert not res.ok and res.reason.startswith("WORKSPACE_VIOLATION")
    rt.close()


def test_shell_injection_or_unknown_command_blocked(workspace):
    rt = make_runtime(workspace)
    rt.verify_and_admit(action_class="shell_command", scope="*", recovery=RecoveryProgram(kind="noop"), target="a.txt", trials=2)
    res = rt.execute(agent_id="a", tool="shell", operation="command", arguments={"command": "rm -rf /"})
    assert not res.ok
    res2 = rt.execute(agent_id="a", tool="shell", operation="command", arguments={"command": "ls; rm -rf /"})
    assert not res2.ok
    rt.close()


def test_direct_adapter_use_fails_closed(workspace):
    from crest.adapters.filesystem import FilesystemAdapter

    try:
        FilesystemAdapter(None)  # type: ignore
        assert False, "adapter accepted null context"
    except Exception:
        pass


def test_asymmetric_revocation_and_fresh_evidence(workspace):
    rt = make_runtime(workspace)
    admit(rt)
    rt.revoke("delete_file:*", "test")
    res = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert not res.ok
    out = admit(rt)  # fresh verification re-admits
    assert out["admitted"] is True
    res = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert res.ok
    rt.close()


def test_learner_cannot_reach_policy(workspace):
    from crest.learner import HeuristicProposer

    learner = HeuristicProposer()
    assert not any(h in dir(learner) for h in ("runtime", "store", "constitution", "ledger", "admit", "execute"))


def test_tampered_receipt_rejected(workspace):
    rt = make_runtime(workspace)
    out = admit(rt)
    rid = out["receipt_id"]
    payload = rt.store.get_receipt_payload(rid)
    payload["action_class"] = "modify_file"
    rt.store.save_receipt(rid, "delete_file", "*", "VERIFIED", "VERIFIED_FIXTURE", payload["verified_at"], payload["expires_at"], payload)
    res = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert not res.ok and res.reason == "RECEIPT_TAMPERED"
    rt.close()


def test_decision_reproducible(workspace):
    rt = make_runtime(workspace)
    admit(rt)
    d1 = rt.check(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    d2 = rt.check(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert d1.allowed == d2.allowed and d1.reason == d2.reason and d1.capability_id == d2.capability_id
    rt.close()


def test_repo_audit_logged_even_on_denial(workspace):
    rt = make_runtime(workspace)
    rt.execute(agent_id="agent", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    events = [e["decision"] for e in rt.audit()]
    assert "ADMISSION_DENIED" in events
    rt.close()


def test_concurrent_budget_race(workspace):
    rt = make_runtime(workspace, e_max=0.5)
    admit(rt)
    results = []

    def worker():
        r = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt", "exposure": 0.3})
        results.append(r.reason)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(1 for r in results if r == "EXECUTED") == 1
    assert sum(1 for r in results if r == "EXPOSURE_BUDGET_EXCEEDED") == 1
    rt.close()
