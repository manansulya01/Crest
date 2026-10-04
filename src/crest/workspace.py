"""Isolated temporary workspace used as the controlled action environment."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


class WorkspaceError(Exception):
    pass


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def temporary(cls) -> "Workspace":
        return cls(Path(tempfile.mkdtemp(prefix="crest-ws-")))

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def resolve(self, relpath: str) -> Path:
        p = (self.root / relpath).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise WorkspaceError(f"path escapes workspace: {relpath!r}")
        return p

    def exists(self, relpath: str) -> bool:
        return self.resolve(relpath).exists()

    def write(self, relpath: str, data: bytes | str) -> None:
        p = self.resolve(relpath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)

    def read(self, relpath: str) -> bytes:
        return self.resolve(relpath).read_bytes()

    def delete(self, relpath: str) -> None:
        p = self.resolve(relpath)
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()

    def move(self, src: str, dst: str) -> None:
        s, d = self.resolve(src), self.resolve(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))

    def file_set(self) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for p in self.root.rglob("*"):
            if p.is_file():
                out[str(p.relative_to(self.root)).replace("\\", "/")] = p.read_bytes()
        return out

    def snapshot(self) -> dict[str, bytes]:
        return self.file_set()

    def restore_snapshot(self, snap: dict[str, bytes]) -> None:
        for p in list(self.root.rglob("*")):
            if p.is_file():
                p.unlink()
        for rel, data in snap.items():
            self.write(rel, data)

    def state_matches(self, snap: dict[str, bytes]) -> bool:
        return self.file_set() == snap
