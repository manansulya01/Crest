"""CREST 1.0 Desktop Launcher.

Starts the backend API server and opens the web dashboard in the default browser.
No external dependencies beyond the CREST package.
"""
from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def main():
    import uvicorn

    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}"

    print(f"Starting CREST 1.0 backend on {url} ...")
    print("Press Ctrl+C to stop.")

    # Open browser after a short delay
    import threading
    def open_browser():
        time.sleep(2)
        webbrowser.open(url)
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run("crest.api:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()