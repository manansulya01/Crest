"""CREST 1.1 packaged backend sidecar.

This is the executable entry point used by the native desktop shell. It binds
only to loopback, picks an available port, writes an atomic runtime descriptor
that the shell polls for, and serves the built web app from inside the bundle.

It is *not* a browser launcher: the desktop shell owns the window and embeds
this server in a WebView.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import time
from pathlib import Path

from crest.product.platform import VERSION


def _free_loopback_port(host: str) -> int:
    """Ask the OS for an unused loopback port (brief race, local use only)."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def _write_runtime(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    try:
        import uvicorn
    except ImportError:  # pragma: no cover - packaging guard
        print("CREST backend dependencies are missing.", file=sys.stderr)
        return 2

    from crest.product.api import create_app

    host = os.environ.get("CREST_HOST", "127.0.0.1")
    # Only loopback is permitted for the packaged sidecar.
    if host not in ("127.0.0.1", "localhost", "::1"):
        host = "127.0.0.1"
    try:
        port = int(os.environ.get("CREST_PORT", "0"))
    except ValueError:
        port = 0
    if port <= 0:
        port = _free_loopback_port(host)

    shutdown_token = os.environ.get("CREST_SHUTDOWN_TOKEN") or secrets.token_urlsafe(32)
    os.environ["CREST_SHUTDOWN_TOKEN"] = shutdown_token
    os.environ.setdefault("CREST_REQUIRE_CSRF", "1")

    runtime_raw = os.environ.get("CREST_RUNTIME_FILE", "")
    runtime_path = Path(runtime_raw).expanduser().resolve() if runtime_raw else None

    app = create_app()
    schema = app.state.db.schema_version()

    if runtime_path is not None:
        _write_runtime(
            runtime_path,
            {
                "port": port,
                "host": host,
                "url": f"http://{host}:{port}",
                "pid": os.getpid(),
                "version": VERSION,
                "schema_version": schema,
                "shutdown_token": shutdown_token,
                "started_at": time.time(),
            },
        )
    print(f"CREST backend {VERSION} listening on http://{host}:{port} (schema v{schema})", flush=True)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
        server_header=False,
        timeout_graceful_shutdown=5,
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    finally:
        if runtime_path is not None:
            try:
                runtime_path.unlink(missing_ok=True)
            except OSError:
                pass
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    raise SystemExit(main())
