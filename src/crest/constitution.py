"""The constitutional plane: small, deterministic, immutable policy."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Constitution:
    e_max: float
    min_recovery_success_rate: float
    max_recovery_p99_ms: float
    allowed_action_classes: frozenset[str]
    receipt_ttl_seconds: float
    exposure_window_seconds: float

    def is_action_allowed(self, action_class: str) -> bool:
        return action_class in self.allowed_action_classes
