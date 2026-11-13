"""CREST 1.0 Desktop Launcher (browser-based).

Starts the local CREST API server and opens the web app in the default
browser. This is intentionally not a native desktop package: it runs the
same FastAPI backend and serves the same built web app as the manual
quickstart, and it requires the product extras to be installed.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def main() -> int:
    # Allow running this file directly from a source checkout without
    # installing the package first.
    src = Path(__file__).resolve().parent / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

    try:
        import uvicorn
    except ImportError:
        print(
            "CREST's product dependencies are not installed.\n"
            "Install them with:  pip install -e \".[product]\"",
            file=sys.stderr,
        )
        return 1

    host = os.environ.get("CREST_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("CREST_PORT", "8000"))
    except ValueError:
        print("CREST_PORT must be an integer.", file=sys.stderr)
        return 1
    app_url = f"http://{host}:{port}/app"

    dist = Path(__file__).resolve().parent / "web" / "dist" / "index.html"
    if not dist.exists():
        print(
            "The web app has not been built yet. From the repository root run:\n"
            "  cd web\n"
            "  npm install\n"
            "  npm run build\n\n"
            "The API will still start; it will show setup instructions at the root URL.",
            file=sys.stderr,
        )

    print(f"Starting CREST 1.0 backend on http://{host}:{port}")
    print(f"Opening the web app at {app_url}")
    print("Press Ctrl+C to stop. This launcher uses your default browser.")

    def open_browser() -> None:
        time.sleep(1.5)
        webbrowser.open(app_url)

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("crest.api:app", host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
