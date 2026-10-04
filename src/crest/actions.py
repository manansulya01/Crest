"""Deterministic action implementations over a Workspace.

Every action has a clearly defined target and observable state change.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .workspace import Workspace

ActionFn = Callable[[Workspace, str, dict[str, Any]], None]


def create_file(ws: Workspace, target: str, params: dict[str, Any]) -> None:
    if ws.exists(target):
        raise FileExistsError(target)
    ws.write(target, str(params.get("content", "")))


def modify_file(ws: Workspace, target: str, params: dict[str, Any]) -> None:
    if not ws.exists(target):
        raise FileNotFoundError(target)
    before = ws.read(target).decode("utf-8", errors="replace")
    if "append" in params:
        ws.write(target, before + str(params["append"]))
    else:
        ws.write(target, str(params.get("content", "")))


def delete_file(ws: Workspace, target: str, params: dict[str, Any]) -> None:
    if not ws.exists(target):
        raise FileNotFoundError(target)
    ws.delete(target)


def move_file(ws: Workspace, target: str, params: dict[str, Any]) -> None:
    ws.move(target, str(params["destination"]))


def create_record(ws: Workspace, target: str, params: dict[str, Any]) -> None:
    if ws.exists(target):
        raise FileExistsError(target)
    ws.write(target, json.dumps(params.get("record", {})))


def modify_record(ws: Workspace, target: str, params: dict[str, Any]) -> None:
    if not ws.exists(target):
        raise FileNotFoundError(target)
    rec = json.loads(ws.read(target).decode("utf-8"))
    rec.update(params.get("updates", {}))
    ws.write(target, json.dumps(rec))


def delete_record(ws: Workspace, target: str, params: dict[str, Any]) -> None:
    delete_file(ws, target, params)


ACTIONS: dict[str, ActionFn] = {
    "create_file": create_file,
    "modify_file": modify_file,
    "move_file": move_file,
    "delete_file": delete_file,
    "create_record": create_record,
    "modify_record": modify_record,
    "delete_record": delete_record,
}

ALL_ACTION_CLASSES = frozenset(ACTIONS)
