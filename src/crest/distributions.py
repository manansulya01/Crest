"""Evaluation distributions for cross-distribution generalization research.

The V0.3 fixture generator is one implementation; V0.4 measures whether
recovery evidence survives *distributions the training generator never
produced*. Each distribution is applied on top of a base fixture.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .workspace import Workspace


class Distribution(str, Enum):
    IN_DISTRIBUTION = "IN_DISTRIBUTION"
    PARAMETER_SHIFT = "PARAMETER_SHIFT"
    STRUCTURAL_SHIFT = "STRUCTURAL_SHIFT"
    COMPOSITION_SHIFT = "COMPOSITION_SHIFT"
    ADVERSARIAL_SHIFT = "ADVERSARIAL_SHIFT"
    OUT_OF_FAMILY = "OUT_OF_FAMILY"


def _long_name(i: int) -> str:
    return ("very_long_filename_" + "x" * 40 + f"_{i}.txt")


def _unicode_name(i: int) -> str:
    return f"файл_测试_αρχείο_{i}.txt"


@dataclass(frozen=True)
class ShiftResult:
    distribution: Distribution
    target: str
    applied: tuple[str, ...]


def apply_distribution(ws: Workspace, base_target: str, distribution: Distribution, seed: int = 0) -> ShiftResult:
    """Mutate a generated fixture into the requested evaluation distribution."""
    applied: list[str] = []
    target = base_target

    if distribution is Distribution.IN_DISTRIBUTION:
        return ShiftResult(distribution, target, ())

    if distribution is Distribution.PARAMETER_SHIFT:
        # different file sizes + more siblings of the same shape
        for i in range(seed % 3 + 2):
            ws.write(f"extra-{i}.txt", b"y" * (64 * (i + 1)))
        applied.append("larger_siblings")

    elif distribution is Distribution.STRUCTURAL_SHIFT:
        deep = "/".join(f"lvl{i}" for i in range(4))
        ws.write(f"{deep}/deep.txt", b"deep content " * 20)
        for i in range(12):
            ws.write(f"many/file-{i}.bin", bytes([seed % 256]) * 8)
        applied.extend(["deep_nesting", "many_siblings"])

    elif distribution is Distribution.COMPOSITION_SHIFT:
        # two adjacent files with cross references (composition hazard surface)
        ws.write("compose_a.txt", b"A-1")
        ws.write("compose_b.txt", b"B-1 -> A")
        applied.append("cross_referenced_siblings")

    elif distribution is Distribution.ADVERSARIAL_SHIFT:
        # fixture-detecting recovery programs see verifier-style artifacts
        ws.write("distractor-0.txt", b"verifier-artifact")
        ws.write("distractor-1.txt", b"verifier-artifact")
        ws.write("__verifier_probe__", b"x")
        applied.extend(["verifier_artifacts"])

    elif distribution is Distribution.OUT_OF_FAMILY:
        ws.write(f"{_long_name(seed % 5)}.txt", b"long name")
        ws.write(f"{_unicode_name(seed % 5)}.md", b"unicode name")
        applied.extend(["long_names", "unicode_names", "other_extensions"])

    return ShiftResult(distribution, target, tuple(applied))