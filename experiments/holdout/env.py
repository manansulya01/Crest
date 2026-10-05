"""Holdout experiment: is a recovery receipt evidence of general
recoverability, or only of one observed reversible test instance?

A = verification environment, B = holdout/execution environment.
"""
from __future__ import annotations

from crest.workspace import Workspace

TARGET = "a.txt"


def build_env_a(ws: Workspace) -> dict[str, bytes]:
    """Flat workspace, seed-prefixed contents, few simple files."""
    ws.write("a.txt", b"seed-alpha")
    ws.write("notes.txt", b"seed-notes")
    ws.write("meta.txt", b"seed-meta")
    return ws.snapshot()


def build_env_b(ws: Workspace) -> dict[str, bytes]:
    """Different names, contents, directory structure, more files."""
    ws.write(TARGET, b"shifted reality, not a seed blob")
    ws.write("docs/notes.txt", b"nested notes with different content")
    ws.write("archive/2024/dump.bin", b"\x00\x11\x22")
    ws.write("extra.tmp", b"unrelated scratch")
    return ws.snapshot()


TRANSFORMATIONS = [
    "different file contents",
    "different file names",
    "additional distractor files",
    "nested directory structure",
    "different file ordering",
]
