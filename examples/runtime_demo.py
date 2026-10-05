"""Crest Runtime v0 end-to-end demo."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import crest.faults  # noqa: F401  registers overfit attack handlers for the demo
from crest.agent_runtime import CrestRuntime
from crest.config import default_yaml
from crest.recovery import RecoveryProgram


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="crest-demo-"))
    try:
        (tmp / "project.txt").write_text("v1 draft\n", encoding="utf-8")
        (tmp / "crest.yaml").write_text(default_yaml(tmp), encoding="utf-8")
        rt = CrestRuntime.from_config(tmp / "crest.yaml")

        print("== 1. honest capability: modify_file ==")
        out = rt.verify_and_admit(
            action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"),
            target="project.txt", trials=6,
        )
        print(f"   verify_and_admit: {out}")

        print("== 2. agent modifies a file via crest ==")
        res = rt.execute(agent_id="agent-1", tool="filesystem", operation="modify_file", arguments={"path": "project.txt", "content": "v2 draft\n"})
        print(f"   ok={res.ok} reason={res.reason} exposure_after={res.exposure_after}")
        print(f"   content: {(tmp / 'project.txt').read_text().strip()}")

        print("== 3. agent tries an unadmitted operation: delete_file ==")
        res = rt.execute(agent_id="agent-1", tool="filesystem", operation="delete_file", arguments={"path": "project.txt"})
        print(f"   ok={res.ok} reason={res.reason}")

        print("== 4. poisoned admission: admit delete_file with an overfit recovery ==")
        out = rt.verify_and_admit(
            action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="overfit_distractor_gate"),
            target="project.txt", trials=6,
        )
        print(f"   verify_and_admit: admitted={out.get('admitted')} status={out.get('status')}")

        print("== 5. agent deletes; reprobe catches the gap ==")
        (tmp / "project.txt").write_text("valuable\n", encoding="utf-8")
        res = rt.execute(agent_id="agent-1", tool="filesystem", operation="delete_file", arguments={"path": "project.txt"})
        print(f"   ok={res.ok} reason={res.reason}")
        caps = [c for c in rt.list_capabilities() if c["action_class"] == "delete_file"]
        print(f"   delete_file state: {caps[0]['state'] if caps else '?'} reason={caps and caps[0]['revocation_reason']}")

        print("== 6. previously admitted modify_file still works; delete_file is dead ==")
        res = rt.execute(agent_id="agent-1", tool="filesystem", operation="delete_file", arguments={"path": "project.txt"})
        print(f"   delete_file retry: ok={res.ok} reason={res.reason}")

        print("== 7. status ==")
        print(f"   {rt.status()}")

        print("== 8. audit trail ==")
        for e in rt.audit(12):
            print(f"   {e['decision']:<22} {e['tool'] or '-':10} {e['operation'] or '-':14} {e['reason'] or ''}")
        rt.close()
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
