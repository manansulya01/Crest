from hashlib import sha256
import json

import pytest

import crest.cli as cli


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr().out
    return code, out


def test_cli_init_status_exec(capsys, workspace):
    cfg = workspace / "crest.yaml"
    code, out = run(capsys, ["--config", str(cfg), "init", "--root", str(workspace)])
    assert code == 0 and cfg.exists()

    code, out = run(capsys, ["--config", str(cfg), "status"])
    assert code == 0 and '"e_max"' in out

    code, out = run(capsys, ["--config", str(cfg), "verify", "--action", "modify_file", "--recovery", "restore_from_snapshot", "--target", "data/a.txt", "--trials", "3"])
    assert code == 0 and '"admitted": true' in out

    code, out = run(capsys, ["--config", str(cfg), "exec", "filesystem", "modify_file", "--arg", "path=data/a.txt", "--arg", "content=ok"])
    assert code == 0 and (workspace / "data" / "a.txt").read_text() == "ok"

    code, out = run(capsys, ["--config", str(cfg), "capabilities", "list"])
    assert code == 0 and "modify_file" in out

    code, out = run(capsys, ["--config", str(cfg), "exec", "filesystem", "delete_file", "--arg", "path=data/a.txt"])
    assert code == 3

    code, out = run(capsys, ["--config", str(cfg), "audit", "--limit", "5"])
    assert "ADMISSION_DENIED" in out


def test_cli_policy_check_path_violation(capsys, workspace):
    cfg = workspace / "crest.yaml"
    run(capsys, ["--config", str(cfg), "init", "--root", str(workspace)])
    code, out = run(capsys, ["--config", str(cfg), "policy", "check", "--tool", "filesystem", "--operation", "modify_file", "--arg", "path=../etc/passwd"])
    assert code == 3 and "WORKSPACE_VIOLATION" in out


def test_cli_help_and_version(capsys):
    code, out = run(capsys, [])
    assert code == 0 and "usage" in out

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == f"crest {cli.__version__}"


def test_cli_doctor_deep_exit_codes(capsys, workspace):
    from crest.agent_runtime import CrestRuntime
    from crest.config import CrestConfig
    from crest.recovery import RecoveryProgram

    cfg = workspace / "crest.yaml"
    run(capsys, ["--config", str(cfg), "init", "--root", str(workspace)])

    code, out = run(capsys, ["--config", str(cfg), "doctor", "--deep"])
    assert code == 0 and "DEEP_OK" in out

    rt = CrestRuntime(CrestConfig(workspace_root=workspace, state_dir=workspace / ".crest"))
    rt.verify_and_admit(
        action_class="modify_file",
        scope="*",
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        target="data/a.txt",
        trials=3,
    )
    row = rt.store.get_capability("modify_file:*")
    row.receipt_id = "receipt-that-does-not-exist"
    rt.store.upsert_capability(row)
    rt.close()

    code, out = run(capsys, ["--config", str(cfg), "doctor", "--deep"])
    assert code == 1 and "CAPABILITY_ORPHAN_RECEIPT" in out
