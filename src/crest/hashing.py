"""Deterministic JSON-canonical hashing utilities."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_default).encode("utf-8")


def digest_of(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def _default(o: Any) -> Any:
    if isinstance(o, (bytes, bytearray)):
        return o.hex()
    if hasattr(o, "value"):
        return o.value
    raise TypeError(f"not serializable: {type(o)!r}")
