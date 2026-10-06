"""crest doctor: diagnostics with ERROR / WARNING / INFO levels.

Exit codes: 0 healthy, 1 errors present, 2 usage errors (argparse).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crest.receipts import CapabilityReceipt
from crest.store import SCHEMA_VERSION

ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"


def _finding(level: str, code: str, message: str, detail: Any = None) -> dict[str, Any]:
    out = {"level": level, "code": code, "message": message}
    if detail is not None:
        out["detail"] = detail
    return out


def diagnose(rt) -> tuple[list[dict[str, Any]], int]:
    findings: list[dict[str, Any]] = []

    # config
    try:
        rt.config.validate()
        findings.append(_finding(INFO, "CONFIG_OK", f"policy {rt.config.policy_version} valid (mode={rt.config.mode})"))
    except Exception as exc:
        findings.append(_finding(ERROR, "CONFIG_INVALID", str(exc)))

    # state dir / database
    db = rt.config.resolved_state_dir / "crest.db"
    if not db.exists():
        findings.append(_finding(WARNING, "DB_MISSING", f"no database yet at {db}"))
    else:
        try:
            conn = sqlite3.connect(str(db))
            row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            conn.close()
            if row is None:
                findings.append(_finding(ERROR, "DB_NO_SCHEMA", "database has no schema_version row"))
            elif int(row[0]) != SCHEMA_VERSION:
                findings.append(_finding(ERROR, "DB_SCHEMA_MISMATCH", f"schema_version={row[0]} (runtime expects {SCHEMA_VERSION})"))
            else:
                findings.append(_finding(INFO, "DB_OK", f"schema_version={row[0]}"))
        except Exception as exc:
            findings.append(_finding(ERROR, "DB_CORRUPT", f"cannot read database: {exc}"))

    # receipts
    now = datetime.now(timezone.utc)
    expired = 0
    revoked = 0
    invalid = 0
    for row in rt.store.list_receipts():
        payload = rt.get_receipt(row["receipt_id"]) or {}
        if payload.get("revoked"):
            revoked += 1
            continue
        try:
            receipt = CapabilityReceipt.from_dict(payload)
        except Exception:
            invalid += 1
            continue
        if not receipt.is_hash_valid():
            invalid += 1
        elif receipt.is_expired(now):
            expired += 1
    if invalid:
        findings.append(_finding(ERROR, "RECEIPT_INVALID", f"{invalid} receipts failed integrity validation"))
    else:
        findings.append(_finding(INFO, "RECEIPT_INTEGRITY", "all receipts hash-valid"))
    if expired:
        findings.append(_finding(WARNING, "RECEIPT_EXPIRED", f"{expired} receipts expired"))
    if revoked:
        findings.append(_finding(INFO, "RECEIPT_REVOKED", f"{revoked} receipts revoked"))

    # capabilities
    revoked_caps = [c.capability_id for c in rt.store.list_capabilities() if c.state == "REVOKED"]
    if revoked_caps:
        findings.append(_finding(WARNING, "CAPABILITY_REVOKED", f"{len(revoked_caps)} revoked capabilities", revoked_caps))

    # workspace
    ws = Path(rt.config.workspace_root)
    if not ws.exists():
        findings.append(_finding(ERROR, "WORKSPACE_MISSING", str(ws)))
    elif not ws.is_dir():
        findings.append(_finding(ERROR, "WORKSPACE_NOT_DIR", str(ws)))
    else:
        findings.append(_finding(INFO, "WORKSPACE_OK", str(ws)))

    # exposure
    total = rt.store.total_exposure()
    if total > rt.config.e_max:
        findings.append(_finding(ERROR, "EXPOSURE_OVER_BUDGET", f"ledger {total} exceeds e_max {rt.config.e_max}"))
    else:
        findings.append(_finding(INFO, "EXPOSURE_OK", f"{total}/{rt.config.e_max}"))

    errors = sum(1 for f in findings if f["level"] == ERROR)
    return findings, (1 if errors else 0)


def report_text(findings: list[dict[str, Any]]) -> str:
    return "\n".join(f"{f['level']:8s} {f['code']:24s} {f['message']}" for f in findings)


def doctor(rt) -> int:
    findings, code = diagnose(rt)
    print(json.dumps({"findings": findings, "exit_code": code}, indent=2))
    return code
