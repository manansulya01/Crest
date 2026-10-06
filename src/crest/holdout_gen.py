"""Structurally independent holdout fixture generator (Level-3 holdout).

The training generator (crest.fixtures) builds a fixed shape and fills it.
This generator instead samples a path graph from a deterministic RNG and
populates it, so a recovery program cannot exploit the training generator's
shape assumptions. The resulting trees still belong to the same declared
family.

The learner never receives this module; it is verifier-side only.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .env_family import EnvironmentFamily
from .fixtures import Fixture
from .workspace import Workspace


@dataclass(frozen=True)
class HoldoutSpec:
    family_id: str
    seed: int
    depth: int
    breadth: int
    sibling_noise: int
    target: str


def sample_spec(family: EnvironmentFamily, seed: int) -> HoldoutSpec:
    import zlib

    fam_key = zlib.crc32(family.family_id.encode())
    rng = random.Random((seed * 2654435761) ^ fam_key)
    if family.family_id == "filesystem.single_file":
        return HoldoutSpec(family.family_id, seed, depth=0, breadth=1, sibling_noise=rng.randint(1, 5), target="a.txt")
    depth = rng.randint(2, 3)
    breadth = rng.randint(2, 3)
    target = "/".join(f"n{i}" for i in range(depth)) + "/t.txt"
    return HoldoutSpec(family.family_id, seed, depth=depth, breadth=breadth, sibling_noise=rng.randint(2, 6), target=target)


def _content(seed: int, i: int) -> bytes:
    rng = random.Random(seed * 7919 + i)
    return bytes(rng.randrange(97, 123) for _ in range(rng.randint(16, 96)))


def _nodes(spec: HoldoutSpec) -> list[str]:
    """File paths (never directories) implied by the sampled path graph."""
    if spec.depth == 0:
        files = [spec.target]
        files += [f"s{i}.dat" for i in range(spec.sibling_noise)]
        return files
    chain = "/".join(f"n{i}" for i in range(spec.depth))
    files = [f"{chain}/t{b}.txt" for b in range(spec.breadth)]
    files += [f"{chain}/s{i}.dat" for i in range(spec.sibling_noise)]
    return files


def build(ws: Workspace, family: EnvironmentFamily, seed: int) -> Fixture:
    """Path-graph-first construction (independent of the training generator)."""
    spec = sample_spec(family, seed)
    nodes = sorted(set(_nodes(spec)))
    for i, rel in enumerate(nodes):
        ws.write(rel, _content(seed, i))
    import hashlib

    h = hashlib.sha256()
    for rel in sorted(ws.file_set()):
        h.update(rel.encode())
        h.update(ws.read(rel))
    return Fixture(family_id=family.family_id, seed=seed, target=nodes[0], digest=h.hexdigest(), file_count=len(ws.file_set()))