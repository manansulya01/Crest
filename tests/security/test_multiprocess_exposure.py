"""Multi-process exposure safety: concurrent processes sharing one state
directory must never collectively commit more than e_max."""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

WORKER = textwrap.dedent(
    """
    import sys, json
    from pathlib import Path
    from crest.store import Store

    db = Path(sys.argv[1])
    attempts = int(sys.argv[2])
    ok = 0
    store = Store(db)
    for _ in range(attempts):
        try:
            if store.try_reserve_exposure(0.25, 1.0, "2026-10-07T00:00:00+00:00", "modify_file", "a.txt", "worker"):
                ok += 1
        except Exception as exc:
            print(json.dumps({"error": str(exc)}))
            break
    print(json.dumps({"reserved": ok}))
    """
)


def _run_workers(db: Path, n: int, attempts: int):
    procs = [subprocess.Popen([sys.executable, "-c", WORKER, str(db), str(attempts)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(n)]
    total_ok = 0
    for p in procs:
        out, err = p.communicate()
        assert p.returncode == 0, err
        total_ok += json.loads(out.strip().splitlines()[-1])["reserved"]
    return total_ok


def test_two_processes_never_exceed_budget(tmp_path):
    db = tmp_path / "crest.db"
    total_ok = _run_workers(db, 2, 5)
    from crest.store import Store

    store = Store(db)
    assert store.total_exposure() <= 1.0 + 1e-9
    assert total_ok * 0.25 <= 1.0 + 1e-9


def test_eight_processes_boundary(tmp_path):
    db = tmp_path / "crest.db"
    total_ok = _run_workers(db, 8, 4)
    from crest.store import Store

    store = Store(db)
    assert store.total_exposure() <= 1.0 + 1e-9
    # 0.25 * 4 = 1.0 fits exactly; a 5th must never succeed
    assert total_ok <= 4


def test_crash_mid_reservation_leaves_no_corruption(tmp_path):
    db = tmp_path / "crest.db"
    crasher = tmp_path / "crasher.py"
    crasher.write_text(
        "import os, sqlite3\n"
        f"c = sqlite3.connect(r'{db}')\n"
        "c.execute('BEGIN IMMEDIATE')\n"
        "c.execute(\"INSERT INTO exposure (amount,timestamp,action_class,target,reason) VALUES (0.5,'t','a','t','crash')\")\n"
        "os._exit(1)\n",
        encoding="utf-8",
    )
    # the crash script runs BEFORE the store creates the schema, so first
    # initialize the schema, then crash mid-transaction
    from crest.store import Store

    Store(db).close()
    proc = subprocess.run([sys.executable, str(crasher)])
    assert proc.returncode != 0
    store = Store(db)
    assert store.total_exposure() == 0.0  # rolled back
    assert store.try_reserve_exposure(0.4, 1.0, "t", "a", "t", "ok")
    assert abs(store.total_exposure() - 0.4) < 1e-9
