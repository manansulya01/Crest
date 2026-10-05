"""Filesystem adapter. All operations are executed only through a
runtime-issued AdapterContext, so direct adapter invocation fails closed."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..paths import canonical_within, relative_posix


class AdapterSecurityError(Exception):
    pass


@dataclass
class AdapterContext:
    runtime: object
    request_id: str
    agent_id: str
    admitted: bool
    workspace_root: Path


OPERATIONS = {"create_file", "modify_file", "move_file", "delete_file", "delete_directory"}


class FilesystemAdapter:
    def __init__(self, context: AdapterContext):
        if context is None or not getattr(context, "admitted", False):
            raise AdapterSecurityError("filesystem operations require an admitted runtime context")
        self.ctx = context

    def target_rel(self, path_arg: str) -> str:
        target = canonical_within(self.ctx.workspace_root, path_arg)
        return relative_posix(self.ctx.workspace_root, target)

    def create_file(self, path: str, content: str = "") -> dict:
        p = canonical_within(self.ctx.workspace_root, path)
        if p.exists():
            raise FileExistsError(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"path": self.target_rel(path), "bytes": len(content.encode("utf-8"))}

    def modify_file(self, path: str, content: str | None = None, append: str | None = None) -> dict:
        p = canonical_within(self.ctx.workspace_root, path)
        if not p.is_file():
            raise FileNotFoundError(path)
        if append is not None:
            with p.open("a", encoding="utf-8", newline="") as fh:
                fh.write(append)
        elif content is not None:
            p.write_text(content, encoding="utf-8")
        else:
            raise ValueError("modify_file requires content or append")
        return {"path": self.target_rel(path)}

    def move_file(self, path: str, destination: str) -> dict:
        s = canonical_within(self.ctx.workspace_root, path)
        d = canonical_within(self.ctx.workspace_root, destination)
        if not s.exists():
            raise FileNotFoundError(path)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
        return {"from": self.target_rel(path), "to": relative_posix(self.ctx.workspace_root, d)}

    def delete_file(self, path: str) -> dict:
        p = canonical_within(self.ctx.workspace_root, path)
        if not p.is_file():
            raise FileNotFoundError(path)
        p.unlink()
        return {"path": self.target_rel(path)}

    def delete_directory(self, path: str) -> dict:
        p = canonical_within(self.ctx.workspace_root, path)
        if not p.is_dir():
            raise NotADirectoryError(path)
        shutil.rmtree(p)
        return {"path": self.target_rel(path)}

    def execute(self, operation: str, arguments: dict) -> dict:
        if operation not in OPERATIONS:
            raise ValueError(f"unsupported filesystem operation: {operation}")
        fn = getattr(self, operation)
        args = {k: v for k, v in arguments.items() if k not in ("exposure",)}
        return fn(**args)
