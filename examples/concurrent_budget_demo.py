"""Concurrent budget: N agents race; only <= E_max / per-action may execute."""
from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.recovery import RecoveryProgram


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="crest-concurrent-"))
    try:
        (tmp / "doc.txt").write_text("x", encoding="utf-8")
        rt = CrestRuntime(CrestConfig(workspace_root=tmp, state_dir=tmp / ".crest", e_max=0.6))
        rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="doc.txt", trials=3)
        results: list[tuple[str, str]] = []
        barrier = threading.Barrier(6)

        def worker(agent: str) -> None:
            barrier.wait()
            r = rt.execute(agent_id=agent, tool="filesystem", operation="modify_file", arguments={"path": "doc.txt", "content": agent, "exposure": 0.3})
            results.append((agent, r.reason))

        threads = [threading.Thread(target=worker, args=(f"agent-{i}",)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ok = sum(1 for _, reason in results if reason == "EXECUTED")
        denied = sum(1 for _, reason in results if reason == "EXPOSURE_BUDGET_EXCEEDED")
        print(f"executed={ok} (budget allows at most {int(0.6/0.3)}) denied={denied} total_exposure={rt.store.total_exposure():.2f}")
        print("budget never exceeded:", rt.store.total_exposure() <= 0.6 + 1e-9)
        rt.close()
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
