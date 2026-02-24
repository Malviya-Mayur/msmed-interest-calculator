# msme_calculator.spec
# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the MSMED Act Interest Calculator.
# Build:
#   Linux :  pyinstaller msme_calculator.spec
#   Windows: pyinstaller msme_calculator.spec   (run from Windows machine)
#
# Output: dist/msme_calculator  (Linux binary)  or  dist/msme_calculator.exe  (Windows)

import sys
import os

block_cipher = None

# ── Data files to bundle ──────────────────────────────────────────────────────
# Format: (source_path_or_glob, dest_folder_inside_bundle)
added_datas = [
    ("ui/templates",  "ui/templates"),   # Jinja2 HTML templates
    ("ui/static",     "ui/static"),      # CSS / JS / images
]

# ── Hidden imports that PyInstaller may miss ──────────────────────────────────
hidden_imports = [
    # FastAPI / Starlette internals
    "uvicorn",
    "uvicorn.lifespan.on",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "starlette",
    "starlette.middleware",
    "starlette.routing",
    "starlette.staticfiles",
    "starlette.templating",
    "fastapi",
    "fastapi.templating",
    "jinja2",
    "jinja2.ext",
    # Data / IO
    "pandas",
    "numpy",
    "openpyxl",
    "openpyxl.cell._writer",
    "openpyxl._constants",
    "python_multipart",
    "multipart",
    "aiofiles",
    # Our own packages
    "ingestion",
    "ingestion.loader",
    "ingestion.validator",
    "engine",
    "engine.mapper",
    "engine.interest",
    "engine.models",
    "output",
    "output.reporter",
    "output.exporter",
    "api",
    "api.routes",
    "config",
]

a = Analysis(
    ["launcher.py"],          # entry point
    pathex=["."],             # add current dir to sys.path during analysis
    binaries=[],
    datas=added_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "PIL", "cv2"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="msme_calculator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,               # compress if UPX is available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,            # show terminal console (useful for error messages)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # add an .ico file here if desired
)
