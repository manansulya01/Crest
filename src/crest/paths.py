"""Canonical, traversal-safe path handling that works on Windows."""
from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath


class WorkspaceViolation(Exception):
    pass


def _norm(p: Path | str) -> str:
    return str(p).replace("\\", "/")


def canonical_within(root: Path, candidate: Path | str) -> Path:
    root_r = Path(root).resolve()
    try:
        resolved = (root_r / candidate).resolve() if not os.path.isabs(str(candidate)) else Path(candidate).resolve()
    except OSError as e:
        raise WorkspaceViolation(str(e)) from e
    try:
        resolved.relative_to(root_r)
    except ValueError:
        raise WorkspaceViolation(f"path escapes workspace: {candidate!r} -> {resolved} (root {root_r})")
    return resolved


def relative_posix(root: Path, target: Path) -> str:
    return _norm(target.resolve().relative_to(Path(root).resolve()))


def scope_matches(scope: str, relpath: str) -> bool:
    """Glob scope over POSIX-normalized relative paths.

    Supports `*` (within a segment), `**` (across segments), `?`.
    """
    scope_n = scope.replace("\\", "/")
    path_n = relpath.replace("\\", "/")
    if scope_n in ("*", "**"):
        return True
    if scope_n.endswith("/**"):
        prefix = scope_n[:-3]
        if path_n == prefix or path_n.startswith(prefix + "/"):
            return True
    pattern = "^" + re.escape(scope_n).replace(r"\*\*", "@@").replace(r"\*", "[^/]*").replace(r"\?", "[^/]").replace("@@", ".*") + "$"
    return re.match(pattern, path_n) is not None
