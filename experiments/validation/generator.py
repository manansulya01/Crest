"""Third, evaluation-only fixture generator.

The training generator (``crest.fixtures``) builds fixed shapes; the V0.4
holdout generator (``crest.holdout_gen``) samples a path graph. This module is
a third construction used only by the independent validation harness. The
policy and verifier modules must not import it.

It deliberately uses a different RNG mapping and different file naming from
both existing generators, so a recovery program that keys on the training
fixture shape has no legitimate reason to pass here.
"""
from __future__ import annotations

import hashlib
import random
import zlib
from dataclasses import dataclass
from typing import Final

from crest.env_family import EnvironmentFamily
from crest.workspace import Workspace

_SUPPORTED: Final = frozenset(
    {"filesystem.single_file", "filesystem.directory_tree"}
)


@dataclass(frozen=True)
class ValidationFixture:
    family_id: str
    seed: int
    target: str
    digest: str
    file_count: int


def _family_key(family_id: str) -> int:
    return zlib.crc32(("validation:" + family_id).encode("utf-8"))


def _content(seed: int, index: int) -> bytes:
    rng = random.Random(seed * 104729 + index * 7919 + 17)
    return bytes(rng.randrange(65, 91) for _ in range(rng.randint(24, 120)))


def _digest(ws: Workspace) -> str:
    digest = hashlib.sha256()
    for rel in sorted(ws.file_set()):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(ws.read(rel))
        digest.update(b"\0")
    return digest.hexdigest()


def build(ws: Workspace, family: EnvironmentFamily, seed: int) -> ValidationFixture:
    """Build a deterministic evaluation fixture for one family and seed."""
    if family.family_id not in _SUPPORTED:
        raise ValueError(
            f"validation generator does not support family {family.family_id!r}"
        )

    rng = random.Random((seed * 2654435761) ^ _family_key(family.family_id))
    files: list[str] = []

    if family.family_id == "filesystem.single_file":
        target = "a.txt"
        files.append(target)
        for index in range(rng.randint(2, 6)):
            files.append(f"sibling_{index}.dat")
    else:
        depth = rng.randint(2, 4)
        directories = [f"dir_{rng.randrange(10)}_{level}" for level in range(depth)]
        leaf = "/".join(directories)
        target = f"{leaf}/target.txt"
        files.append(target)
        for index in range(rng.randint(1, 4)):
            files.append(f"{leaf}/leaf_{index}.dat")
        for index in range(rng.randint(2, 5)):
            side = rng.randrange(10)
            files.append(f"side_{side}_{index}/item_{index}.bin")

    for index, rel in enumerate(sorted(set(files))):
        ws.write(rel, _content(seed, index))

    return ValidationFixture(
        family_id=family.family_id,
        seed=seed,
        target=target,
        digest=_digest(ws),
        file_count=len(ws.file_set()),
    )
