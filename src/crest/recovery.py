"""Recovery programs are UNTRUSTED proposals produced by a learner.

They are data identified by a digest and executed by the verifier,
never trusted by the constitutional layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .hashing import digest_of
from .workspace import Workspace


@dataclass(frozen=True)
class RecoveryContext:
    action_class: str
    target: str
    params: Mapping[str, Any]
    pre_action_snapshot: Mapping[str, bytes]


RecoveryHandler = Callable[[Workspace, RecoveryContext], None]

_REGISTRY: dict[str, RecoveryHandler] = {}


def register(kind: str) -> Callable[[RecoveryHandler], RecoveryHandler]:
    def _wrap(fn: RecoveryHandler) -> RecoveryHandler:
        _REGISTRY[kind] = fn
        return fn

    return _wrap


def get_handler(kind: str) -> RecoveryHandler | None:
    return _REGISTRY.get(kind)


def known_kinds() -> frozenset[str]:
    return frozenset(_REGISTRY)


@register("restore_from_snapshot")
def _restore_all(ws: Workspace, ctx: RecoveryContext) -> None:
    ws.restore_snapshot(dict(ctx.pre_action_snapshot))


@register("restore_file_from_snapshot")
def _restore_file(ws: Workspace, ctx: RecoveryContext) -> None:
    snap = ctx.pre_action_snapshot
    if ctx.target in snap:
        ws.write(ctx.target, snap[ctx.target])
    elif ws.exists(ctx.target):
        ws.delete(ctx.target)


@register("noop")
def _noop(ws: Workspace, ctx: RecoveryContext) -> None:
    return None


@register("delete_target")
def _delete_target(ws: Workspace, ctx: RecoveryContext) -> None:
    if ws.exists(ctx.target):
        ws.delete(ctx.target)


@dataclass(frozen=True)
class RecoveryProgram:
    kind: str
    params: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", dict(self.params or {}))

    @property
    def digest(self) -> str:
        return digest_of({"kind": self.kind, "params": dict(self.params)})
