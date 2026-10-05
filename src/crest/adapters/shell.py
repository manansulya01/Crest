"""Restricted shell adapter: native implementations of a small allowlist,
no arbitrary command execution, no shell interpretation."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..paths import canonical_within, relative_posix
from .filesystem import AdapterContext, AdapterSecurityError

METACHARS = re.compile(r"[;|&><`$\\(){}\[\]\n\r]")


class ShellSecurityError(Exception):
    pass


class ShellAdapter:
    def __init__(self, context: AdapterContext, allowlist: tuple[str, ...] = ()):
        if context is None or not getattr(context, "admitted", False):
            raise AdapterSecurityError("shell operations require an admitted runtime context")
        self.ctx = context
        self.root = Path(self.ctx.workspace_root).resolve()
        self.allowlist = allowlist or ("pwd", "ls", "dir", "git status", "git diff", "python --version", "echo")

    def _is_allowed(self, argv: list[str]) -> bool:
        joined = " ".join(argv)
        if joined in self.allowlist:
            return True
        if argv[0] in ("ls", "dir") and all(not t.startswith("-") for t in argv[1:]):
            try:
                for t in argv[1:]:
                    canonical_within(self.root, t)
                return True
            except Exception:
                return False
        if argv[0] == "echo":
            return all(not t.startswith("-") for t in argv[1:])
        return False

    def execute(self, argv: list[str] | str, cwd: str | None = None) -> dict:
        if isinstance(argv, str):
            if METACHARS.search(argv):
                raise ShellSecurityError("shell metacharacters are not permitted")
            argv = argv.split()
        for token in argv:
            if METACHARS.search(token):
                raise ShellSecurityError(f"disallowed token: {token!r}")
        if not self._is_allowed(argv):
            raise ShellSecurityError(f"command not in allowlist: {argv!r}")
        workdir = canonical_within(self.root, cwd) if cwd else self.root
        return self._run(argv, workdir)

    def _run(self, argv: list[str], workdir: Path) -> dict:
        prog, *rest = argv
        if prog in ("pwd",):
            return {"stdout": str(workdir), "stderr": "", "code": 0}
        if prog in ("ls", "dir"):
            target = canonical_within(workdir, rest[0]) if rest else workdir
            return {"stdout": "\n".join(sorted(p.name for p in target.iterdir())), "stderr": "", "code": 0}
        if prog == "echo":
            return {"stdout": " ".join(rest), "stderr": "", "code": 0}
        if prog == "python" and rest == ["--version"]:
            proc = subprocess.run(["python", "--version"], capture_output=True, text=True, timeout=30)
            return {"stdout": (proc.stdout or proc.stderr).strip(), "stderr": "", "code": proc.returncode}
        if prog == "git" and rest and rest[0] in ("status", "diff"):
            proc = subprocess.run(["git", "-C", str(workdir)] + rest, capture_output=True, text=True, timeout=60)
            return {"stdout": proc.stdout, "stderr": proc.stderr, "code": proc.returncode}
        raise ShellSecurityError(f"command not supported: {argv!r}")
