"""Secret redaction for audit/CLI surfaces.

Best-effort pattern redaction. This is NOT a complete secret scanner.
"""
from __future__ import annotations

import re
from typing import Any

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b(sk-[A-Za-z0-9]{16,})\b"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)(gh[pousr]_[A-Za-z0-9]{20,})"), "[REDACTED_TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)\b(\s*[:=]\s*)(\S+)"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)\bAuthorization:\s*Bearer\s+\S+"), "Authorization: Bearer [REDACTED]"),
)

_SENSITIVE_KEYS = {"password", "passwd", "secret", "api_key", "apikey", "token", "access_token", "refresh_token", "private_key", "authorization"}


def redact_text(text: str) -> str:
    out = text
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out


def redact(value: Any, _depth: int = 0) -> Any:
    if _depth > 12:
        return "[REDACTED_DEPTH]"
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in _SENSITIVE_KEYS else redact(v, _depth + 1)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, _depth + 1) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value