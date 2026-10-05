from __future__ import annotations

import pytest

from crest.adapters.filesystem import FilesystemAdapter
from crest.adapters.git import GitAdapter
from crest.adapters.shell import ShellAdapter, ShellSecurityError
from crest.adapters.filesystem import AdapterSecurityError


def ctx(workspace):
    from crest.adapters.filesystem import AdapterContext

    return AdapterContext(runtime=None, request_id="r", agent_id="a", admitted=True, workspace_root=workspace)


def test_filesystem_basic(workspace):
    fs = FilesystemAdapter(ctx(workspace))
    fs.create_file("new.txt", "hi")
    assert (workspace / "new.txt").read_text() == "hi"
    fs.modify_file("new.txt", append="!")
    assert (workspace / "new.txt").read_text() == "hi!"
    fs.move_file("new.txt", "sub/moved.txt")
    assert (workspace / "sub" / "moved.txt").exists()
    fs.delete_file("sub/moved.txt")
    assert not (workspace / "sub" / "moved.txt").exists()


def test_filesystem_traversal(workspace):
    fs = FilesystemAdapter(ctx(workspace))
    with pytest.raises(Exception):
        fs.modify_file("../out.txt", content="x")


def test_filesystem_delete_directory(workspace):
    fs = FilesystemAdapter(ctx(workspace))
    fs.create_file("d/a.txt", "1")
    fs.delete_directory("d")
    assert not (workspace / "d").exists()


def test_git_adapter(workspace):
    import subprocess

    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    ga = GitAdapter(ctx(workspace))
    ga.modify_file("f.txt", "v1")
    ga.commit("init commit", paths=["f.txt"])
    out = ga.create_branch("feat/x")
    assert out["stdout"] == ""  # branch created silently


def test_git_adapter_invalid_branch(workspace):
    import subprocess

    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    ga = GitAdapter(ctx(workspace))
    with pytest.raises(ValueError):
        ga.create_branch("bad..name")


def test_shell_allowlist(workspace):
    sh = ShellAdapter(ctx(workspace))
    r = sh.execute(["pwd"])
    assert r["stdout"]
    with pytest.raises(ShellSecurityError):
        sh.execute(["rm", "-rf", "/"])
    with pytest.raises(ShellSecurityError):
        sh.execute("ls; rm -rf /")
    with pytest.raises(ShellSecurityError):
        sh.execute(["curl", "evil"])
    r = sh.execute(["ls"])
    assert "data" in r["stdout"]


def test_shell_metachars(workspace):
    sh = ShellAdapter(ctx(workspace))
    for bad in ["echo $(whoami)", "echo `id`", "echo hi > /tmp/x", "echo a | cat"]:
        with pytest.raises(ShellSecurityError):
            sh.execute(bad)


def test_direct_adapter_access_fails(workspace):
    from crest.adapters.filesystem import AdapterSecurityError

    try:
        FilesystemAdapter(None)
        assert False
    except AdapterSecurityError:
        pass
