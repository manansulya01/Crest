"""Malicious agent attempt: bypass, forge, tamper, escape — all must fail closed."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import crest.cli as cli
from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.recovery import RecoveryProgram


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="crest-malicious-"))
    try:
        (tmp / "a.txt").write_text("data", encoding="utf-8")
        rt = CrestRuntime(CrestConfig(workspace_root=tmp, state_dir=tmp / ".crest"))
        rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=3)

        attacks = [
            # direct adapter call (no admission context)
            ("adapter bypass", lambda: _adapter_bypass()),
            # unknown tool
            ("unknown tool", lambda: rt.execute(agent_id="m", tool="kernel", operation="root", arguments={})),
            # traversal
            ("path traversal", lambda: rt.execute(agent_id="m", tool="filesystem", operation="delete_file", arguments={"path": "..\\..\\windows\\system32\\config\\SAM"})),
            # tampered receipt
            ("forged receipt", lambda: _tamper(rt)),
            # forked cwd outside workspace via shell
            ("shell path outside workspace", lambda: rt.execute(agent_id="m", tool="shell", operation="command", arguments={"command": "ls ..\\.."})),
            # raw shell with injection
            ("shell injection", lambda: rt.execute(agent_id="m", tool="shell", operation="command", arguments={"command": "ls && shutdown /s"})),
        ]
        for name, attempt in attacks:
            try:
                res = attempt()
                print(f"attack={name:28s} -> blocked: {not getattr(res, 'ok', False)} reason={getattr(res, 'reason', res)}")
            except Exception as exc:
                print(f"attack={name:28s} -> blocked: True reason={exc}")
        rt.close()
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _adapter_bypass():
    from crest.adapters.filesystem import FilesystemAdapter

    try:
        FilesystemAdapter(None)  # type: ignore
    except Exception as exc:
        return exc
    return _AdapterBypassNoError()


class _AdapterBypassNoError:
    ok = True
    reason = "BYPASS SUCCEEDED"


def _tamper(rt):
    receipt_ids = [r["receipt_id"] for r in rt.store.list_receipts()]
    if receipt_ids:
        payload = rt.store.get_receipt_payload(receipt_ids[0])
        payload["action_class"] = "delete_file"
        rt.store.save_receipt(receipt_ids[0], "modify_file", "*", "VERIFIED", "VERIFIED_FIXTURE", payload["verified_at"], payload["expires_at"], payload)
        res = rt.execute(agent_id="m", tool="filesystem", operation="modify_file", arguments={"path": "a.txt", "content": "x"})
        return res
    return _AdapterBypassNoError()


if __name__ == "__main__":
    import crest.cli  # noqa: F401

    raise SystemExit(main())
