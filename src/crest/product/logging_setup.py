"""Structured, rotating application logs with secret redaction."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from ..redaction import redact_text
from .platform import logs_dir

_HANDLER_MARKER = "_crest_handler"
_LOGGER_NAME = "crest"


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))


def configure_logging(
    data_dir: str | Path | None = None,
    *,
    level: int = logging.INFO,
    console: bool | None = None,
) -> dict[str, Any]:
    """Configure rotating logs once and return the active paths.

    Repeated calls (for example from tests creating multiple apps) reuse the
    existing handler instead of multiplying output.
    """
    directory = logs_dir(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / "crest.log"
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    setattr(handler, _HANDLER_MARKER, True)
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)

    if console is None:
        console = not getattr(__import__("sys"), "frozen", False)
    if console:
        stream = logging.StreamHandler()
        setattr(stream, _HANDLER_MARKER, True)
        stream.setFormatter(
            RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(stream)

    # Capture uvicorn errors in the same redacted rotating file.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        target = logging.getLogger(name)
        target.handlers = []
        target.propagate = True
    return {"log_file": str(log_file), "log_dir": str(directory)}


def get_logger(name: str = "crest") -> logging.Logger:
    return logging.getLogger(name)


def log_files(data_dir: str | Path | None = None) -> list[dict[str, Any]]:
    directory = logs_dir(data_dir)
    if not directory.exists():
        return []
    out = []
    for path in sorted(directory.glob("*.log*"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            stat = path.stat()
        except OSError:
            continue
        out.append({"name": path.name, "path": str(path), "size_bytes": stat.st_size})
    return out


def tail_log(data_dir: str | Path | None = None, *, lines: int = 200) -> str:
    directory = logs_dir(data_dir)
    path = directory / "crest.log"
    if not path.exists():
        return ""
    lines = max(1, min(int(lines), 2000))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        content = handle.readlines()[-lines:]
    return redact_text("".join(content))


def prune_logs(data_dir: str | Path | None = None, *, keep: int = 5) -> int:
    """Keep only the newest rotated log files. Returns files removed."""
    directory = logs_dir(data_dir)
    rotated = sorted(directory.glob("crest.log.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for path in rotated[keep:]:
        try:
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed
