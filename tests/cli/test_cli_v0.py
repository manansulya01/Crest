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
