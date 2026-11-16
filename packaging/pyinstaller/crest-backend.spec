# PyInstaller spec for the CREST 1.1 packaged backend sidecar.
# Build from the repository root with:
#   python -m PyInstaller --noconfirm --distpath packaging\build\backend packaging\pyinstaller\crest-backend.spec
from pathlib import Path

import os

SPEC_DIR = Path(SPECPATH).resolve()  # noqa: F821  (provided by PyInstaller)
ROOT = SPEC_DIR.parent.parent
SRC = ROOT / "src"
WEB_DIST = ROOT / "web" / "dist"

if not (WEB_DIST / "index.html").exists():
    raise SystemExit(
        "web/dist/index.html not found. Run 'npm run build' inside web/ before building the sidecar."
    )

hidden = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "anyio",
    "starlette",
    "fastapi",
    "pydantic",
    "ctypes",
    "sqlite3",
]

a = Analysis(  # noqa: F821
    [str(SRC / "crest" / "product" / "sidecar.py")],
    pathex=[str(SRC), str(ROOT)],
    binaries=[],
    datas=[(str(WEB_DIST), "web/dist")],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "tkinter", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="crest-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no terminal window during normal use
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
