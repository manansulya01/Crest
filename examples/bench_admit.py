"""Admission latency + execution overhead benchmark."""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.recovery import RecoveryProgram


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="crest-bench-"))
    try:
        cfg = CrestConfig(workspace_root=tmp, state_dir=tmp / ".crest", e_max=100_000.0)
        rt = CrestRuntime(cfg)
        rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=4)

        n = 1000
        t0 = time.perf_counter()
        for _ in range(n):
            rt.check(agent_id="bench", tool="filesystem", operation="modify_file", arguments={"path": "a.txt"})
        t_check = (time.perf_counter() - t0) / n * 1000

        (tmp / "a.txt").write_text("x", encoding="utf-8")
        m = 50
        t0 = time.perf_counter()
        for i in range(m):
            r = rt.execute(agent_id="bench", tool="filesystem", operation="modify_file", arguments={"path": "a.txt", "content": f"{i}"})
            assert r.ok
        t_exec = (time.perf_counter() - t0) / m * 1000

        print(f"check latency mean: {t_check:.3f} ms")
        print(f"modify_file through crest: {t_exec:.3f} ms mean (incl. ledger+probe)")
        rt.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
