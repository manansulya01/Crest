"""Controlled Git adapter. No arbitrary git invocation — three bounded
operations, each argument-validated and scoped to the workspace."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..paths import canonical_within, relative_posix
from .filesystem import AdapterContext, AdapterSecurityError

BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,120}$")


class GitAdapter:
    def __init__(self, context: AdapterContext):
        if context is None or not getattr(context, "admitted", False):
            raise AdapterSecurityError("git operations require an admitted runtime context")
        self.ctx = context
        self.root = canonical_within(self.ctx.workspace_root, ".")

    def _git(self, *args: str) -> dict:
        cmd = ["git", "-C", str(self.root)] + list(args)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
        return {"stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}

    def create_branch(self, name: str) -> dict:
        if not BRANCH_RE.match(name) or ".." in name:
            raise ValueError(f"invalid branch name: {name!r}")
        self._git("rev-parse", "--is-inside-work-tree")
        return self._git("branch", name)

    def modify_file(self, path: str, content: str) -> dict:
        target = canonical_within(self.root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": relative_posix(self.root, target)}

    def commit(self, message: str, paths: list[str] | None = None) -> dict:
        if not message or len(message) > 500:
            raise ValueError("invalid commit message")
        rel_paths = []
        for p in paths or []:
            rel = relative_posix(self.root, canonical_within(self.root, p))
            rel_paths.append(rel)
        for rel in rel_paths:
            self._git("add", "--", rel)
        self._git(
            "-c", "user.name=crest", "-c", "user.email=crest@local",
            "commit", "-m", message, "--", *(rel_paths or []),
        )
        head = self._git("rev-parse", "HEAD")
        return {"commit": head["stdout"], "staged": rel_paths}

    def execute(self, operation: str, arguments: dict) -> dict:
        if operation == "create_branch":
            return self.create_branch(str(arguments["name"]))
        if operation == "modify_file":
            return self.modify_file(str(arguments["path"]), str(arguments.get("content", "")))
        if operation == "commit":
            return self.commit(str(arguments.get("message", "crest commit")), arguments.get("paths"))
        raise ValueError(f"unsupported git operation: {operation}")
