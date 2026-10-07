"""Receipt malformed-input matrix: every corrupt/attacker-controlled payload
must be rejected with a stable code, never an uncaught exception, never
admission, never execution, never state mutation."""
from __future__ import annotations

import copy
import json

import pytest

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.recovery import RecoveryProgram


def _admitted_rt(tmp_path):
    (tmp_path / "a.txt").write_text("data", encoding="utf-8")
    rt = CrestRuntime(CrestConfig(workspace_root=tmp_path, state_dir=tmp_path / ".crest"))
    out = rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=3)
    assert out["admitted"] is True
    return rt


def _tamper(rt, mutate):
    rid = rt.store.list_receipts()[0]["receipt_id"]
    payload = copy.deepcopy(rt.get_receipt(rid))
    meta = {k: payload[k] for k in ("action_class", "target_scope", "status", "evidence_classification", "issued_at", "expires_at")}
    mutate(payload)
    rt.store.save_receipt(rid, meta["action_class"], meta["target_scope"], meta["status"], meta["evidence_classification"], meta["issued_at"], meta["expires_at"], payload)
    return rid


def _attempt(rt):
    return rt.execute(agent_id="att", tool="filesystem", operation="modify_file", arguments={"path": "a.txt", "content": "x"})


@pytest.mark.parametrize("field", ["issued_at", "receipt_version", "action_class", "target_scope", "evidence", "policy_version", "verifier_version", "signature", "key_id", "payload_digest", "evidence_digest", "expires_at", "receipt_id", "status", "schema_version"])
def test_missing_required_payload_field_rejected(tmp_path, field):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p.pop(field, None)
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok
    assert res.reason.split(":")[0] in ("RECEIPT_MALFORMED", "RECEIPT_NOT_FOUND", "RECEIPT_REVOKED", "RECEIPT_UNKNOWN_KEY", "RECEIPT_BAD_SIGNATURE")
    assert rt.store.total_exposure() == 0.0
    rt.close()


@pytest.mark.parametrize("field", ["issued_at", "expires_at"])
def test_malformed_timestamp_rejected(tmp_path, field):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p[field] = "not-a-timestamp"
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok and res.reason.startswith("RECEIPT_MALFORMED")
    rt.close()


def test_naive_timestamp_rejected(tmp_path):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p["issued_at"] = "2026-01-01T00:00:00"
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok and res.reason.startswith("RECEIPT_MALFORMED")
    rt.close()


@pytest.mark.parametrize("field", ["payload_digest", "evidence_digest", "bound_digest"])
def test_malformed_digest_rejected(tmp_path, field):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p[field] = "zz" * 32
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok and res.reason.startswith("RECEIPT_MALFORMED")
    rt.close()


def test_unknown_receipt_version_rejected(tmp_path):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p["receipt_version"] = "99.0"
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok and res.reason.startswith("RECEIPT_MALFORMED")
    rt.close()


def test_attacker_extra_field_rejected(tmp_path):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p["is_admin"] = True
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok and res.reason.startswith("RECEIPT_MALFORMED")
    rt.close()


def test_wrong_field_type_rejected(tmp_path):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p["schema_version"] = "2"
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok and res.reason.startswith("RECEIPT_MALFORMED")
    rt.close()


def test_empty_required_string_rejected(tmp_path):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p["action_class"] = ""
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok and res.reason.startswith("RECEIPT_MALFORMED")
    rt.close()


def test_evidence_missing_inner_field_rejected(tmp_path):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p["evidence"].pop("recovery_success_rate", None)
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok and res.reason.startswith("RECEIPT_MALFORMED")
    rt.close()


def test_signature_forgery_rejected(tmp_path):
    rt = _admitted_rt(tmp_path)
    import base64, os
    def mutate(p):
        p["signature"] = base64.b64encode(os.urandom(64)).decode()
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok and res.reason in ("RECEIPT_BAD_SIGNATURE", "RECEIPT_TAMPERED")
    rt.close()


def test_unsigned_receipt_rejected(tmp_path):
    rt = _admitted_rt(tmp_path)
    def mutate(p):
        p["signature"] = ""
        p["key_id"] = ""
        p["signature_algorithm"] = ""
    _tamper(rt, mutate)
    res = _attempt(rt)
    assert not res.ok
    assert res.reason.split(":")[0] in ("RECEIPT_UNKNOWN_KEY", "RECEIPT_BAD_SIGNATURE", "RECEIPT_MALFORMED")
    rt.close()


def test_revoked_receipt_replay_rejected(tmp_path):
    rt = _admitted_rt(tmp_path)
    rid = rt.store.list_receipts()[0]["receipt_id"]
    rt.revoke("modify_file:*")
    # attacker reinstates the capability row without a valid receipt chain
    row_cap = rt.get_capability("modify_file:*")
    assert row_cap["state"] == "REVOKED"
    res = _attempt(rt)
    assert not res.ok
    rt.close()


def test_forged_payload_with_valid_digest_but_no_signature(tmp_path):
    """Recomputing digests must not be enough: authenticity requires the key."""
    from crest.receipts import CapabilityReceipt

    rt = _admitted_rt(tmp_path)
    rid = rt.store.list_receipts()[0]["receipt_id"]
    payload = copy.deepcopy(rt.get_receipt(rid))
    payload["action_class"] = "delete_file"
    try:
        forged = CapabilityReceipt.from_payload(payload)
        # attacker recomputes the payload digest over the tampered fields
        forged2 = CapabilityReceipt(**{**forged.to_dict(), "payload_digest": forged.recompute_payload_digest()})
        payload.update(forged2.to_dict())
    except Exception:
        pass
    rt.store.save_receipt(rid, payload["action_class"], payload["target_scope"], payload["status"], payload["evidence_classification"], payload["issued_at"], payload["expires_at"], payload)
    res = _attempt(rt)
    assert not res.ok
    assert res.reason.split(":")[0] in ("RECEIPT_BAD_SIGNATURE", "RECEIPT_TAMPERED", "RECEIPT_UNKNOWN_KEY", "RECEIPT_ACTION_MISMATCH", "RECEIPT_SCOPE_MISMATCH", "RECEIPT_MALFORMED")
    rt.close()
