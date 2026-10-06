"""Crest V0.4 end-to-end demonstration.

1. agent requests delete_file -> Crest sees VERIFIED evidence, checks scope,
   evidence, exposure, drift -> ADMITS -> executes -> observes -> reprobes
2. distribution shift introduced -> reprobe/drift invalidates evidence ->
   REVOKE -> the same request is DENIED
3. fresh generalized verification (independent holdouts) -> re-admission.
   With the default strict policy and small demo sample sizes the resulting
   evidence class is VERIFIED_FIXTURE/VERIFIED_FAMILY; reaching
   VERIFIED_GENERAL requires the configured sample sizes. See
   docs/research-v0.4.md and experiments/tables/ablations.md for measured
   generalized evidence.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import crest.faults  # noqa: F401
from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig, default_yaml
from crest.recovery import RecoveryProgram


def show(step: str) -> None:
    print(f"\n--- {step} ---")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="crest-v04-demo-"))
    try:
        (tmp / "report.txt").write_text("quarterly numbers\n", encoding="utf-8")
        (tmp / "crest.yaml").write_text(default_yaml(tmp), encoding="utf-8")
        rt = CrestRuntime.from_config(tmp / "crest.yaml")

        show("1. agent requests delete_file")
        res = rt.execute(agent_id="demo-agent", tool="filesystem", operation="delete_file", arguments={"path": "report.txt"})
        print(f"DENIED before verification: ok={res.ok} reason={res.reason}")

        show("2. generalized verification (independent holdout generator)")
        out = rt.verify_generalized(
            action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"),
            family_ids=("filesystem.single_file",), verification_cases=6, holdout_cases=6, shift_cases=3,
        )
        print(f"verify -> {out}")

        show("3. agent retries: admitted")
        res = rt.execute(agent_id="demo-agent", tool="filesystem", operation="delete_file", arguments={"path": "report.txt"})
        print(f"ADMIT+EXECUTE: ok={res.ok} reason={res.reason} exposure_after={res.exposure_after}")

        show("4. distribution shift: target replaced by a nested tree")
        (tmp / "nested").mkdir()
        (tmp / "nested" / "report.txt").write_text("shifted\n", encoding="utf-8")
        res = rt.execute(agent_id="demo-agent", tool="filesystem", operation="delete_file", arguments={"path": "nested/report.txt"})
        print(f"DRIFT: ok={res.ok} reason={res.reason}")
        print(f"capability state: {rt.get_capability('delete_file:*')['state']}")

        show("5. previously admitted action is now denied")
        (tmp / "report.txt").write_text("restored\n", encoding="utf-8")
        res = rt.execute(agent_id="demo-agent", tool="filesystem", operation="delete_file", arguments={"path": "report.txt"})
        print(f"DENIED after revocation: ok={res.ok} reason={res.reason}")

        show("6. fresh generalized verification -> re-admission")
        out2 = rt.verify_generalized(
            action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"),
            family_ids=("filesystem.single_file",), verification_cases=6, holdout_cases=6, shift_cases=3,
        )
        print(f"re-verify -> {out2}")
        print(f"   evidence class={out2['classification']} (default policy, small sample sizes: "
              "VERIFIED_GENERAL needs the configured minimum samples)")
        res = rt.execute(agent_id="demo-agent", tool="filesystem", operation="delete_file", arguments={"path": "report.txt"})
        print(f"READMITTED+EXECUTE: ok={res.ok} reason={res.reason}")

        show("7. status / exposure / audit")
        print(f"status: {rt.status()}")
        for e in rt.audit(12):
            print(f"  {e['decision']:<22} {e['operation'] or '-':14} {e['reason'] or ''}")
        rt.close()
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())