"""Conservative, append-only exposure accounting.

Successful recovery never refunds exposure. Exposure is released only by
window expiry, not by the agent's behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class ExposureEntry:
    amount: float
    timestamp: datetime
    action_class: str
    target: str
    reason: str


@dataclass
class ExposureLedger:
    _entries: list[ExposureEntry] = field(default_factory=list)

    def record(self, amount: float, when: datetime, action_class: str, target: str, reason: str) -> ExposureEntry:
        if amount < 0:
            raise ValueError("negative exposure not allowed")
        entry = ExposureEntry(amount=amount, timestamp=when, action_class=action_class, target=target, reason=reason)
        self._entries.append(entry)
        return entry

    def total(self) -> float:
        return sum(e.amount for e in self._entries)

    def total_in_window(self, now: datetime, window_seconds: float) -> float:
        cutoff = now - timedelta(seconds=window_seconds)
        return sum(e.amount for e in self._entries if e.timestamp >= cutoff)

    def entries(self) -> tuple[ExposureEntry, ...]:
        return tuple(self._entries)
