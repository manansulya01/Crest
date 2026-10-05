"""Deterministic fixture generators keyed by (family, seed)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .env_family import EnvironmentFamily
from .workspace import Workspace


@dataclass(frozen=True)
class Fixture:
    family_id: str
    seed: int
    target: str
    digest: str
    file_count: int


def _content(family: str, seed: int, i: int, size: int) -> bytes:
    return (f"crest-{family}-seed{seed}-file{i}|".encode() + b"x" * size)[:size]


def _digest(ws: Workspace) -> str:
    h = hashlib.sha256()
    for rel in sorted(ws.file_set()):
        h.update(rel.encode())
        h.update(ws.read(rel))
    return h.hexdigest()


def generate(ws: Workspace, *, family: EnvironmentFamily, seed: int, include_target: bool = True) -> Fixture:
    n_files = 2 + (seed % 4)
    target = "a.txt"
    if family.family_id == "filesystem.single_file":
        ws.write(target, _content(family.family_id, seed, 0, 64 + seed % 128))
        for i in range(n_files):
            ws.write(f"d{i}.txt", _content(family.family_id, seed, i + 1, 32))
    elif family.family_id == "filesystem.directory_tree":
        ws.write(f"docs/{target}", _content(family.family_id, seed, 0, 128))
        ws.write(f"src/main.py", _content(family.family_id, seed, 1, 64))
        ws.write(f"data/deep/inner/x{seed}.bin", _content(family.family_id, seed, 2, 256))
        for i in range(n_files):
            ws.write(f"distractor-{i}.tmp", _content(family.family_id, seed, 3 + i, 16))
        target = f"docs/{target}"
    elif family.family_id == "git.repository":
        ws.write(target, _content(family.family_id, seed, 0, 128))
        ws.write("README.md", b"# demo\n")
    else:  # pragma: no cover
        raise ValueError(family.family_id)
    return Fixture(family_id=family.family_id, seed=seed, target=target, digest=_digest(ws), file_count=len(ws.file_set()))
