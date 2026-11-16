"""Windows-first platform paths and application metadata for CREST 1.1.

The application never writes user data next to the executable.  On Windows the
stable location is ``%LOCALAPPDATA%\\CREST``.  Environment overrides exist for
tests, portable development, and advanced deployments:

* ``CREST_DATA_DIR``   -- override the data root (database, credentials)
* ``CREST_LOG_DIR``    -- override the log directory
* ``CREST_BACKUP_DIR`` -- override the backup directory
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "CREST"
APP_ID = "com.crest.app"
VERSION = "1.1.0"
SCHEMA_VERSION = 2


def is_windows() -> bool:
    return os.name == "nt"


def app_data_dir() -> Path:
    raw = os.environ.get("CREST_DATA_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    if is_windows():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return (Path(base) / APP_NAME).resolve()
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return (Path(base) / "crest").resolve()
    return (Path.home() / ".local" / "share" / "crest").resolve()


def logs_dir(data_dir: str | Path | None = None) -> Path:
    raw = os.environ.get("CREST_LOG_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path(data_dir) if data_dir else app_data_dir()) / "logs"


def backups_dir(data_dir: str | Path | None = None) -> Path:
    raw = os.environ.get("CREST_BACKUP_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path(data_dir) if data_dir else app_data_dir()) / "backups"


def database_path(data_dir: str | Path | None = None) -> Path:
    return (Path(data_dir) if data_dir else app_data_dir()) / "crest.db"


def runtime_file(data_dir: str | Path | None = None) -> Path:
    return (Path(data_dir) if data_dir else app_data_dir()) / "runtime.json"


def ensure_app_dirs(data_dir: str | Path | None = None) -> dict[str, Path]:
    root = Path(data_dir) if data_dir else app_data_dir()
    paths = {
        "data": root,
        "logs": logs_dir(root),
        "backups": backups_dir(root),
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))
