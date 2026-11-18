# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone Updater (onefile console exe).

Build from the project root:

    python -m PyInstaller --noconfirm packaging/updater.spec

Produces ``dist/Updater/Updater.exe``. The build script copies this next to the
main application executable so ``launch_updater`` can find it at runtime.
"""

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

block_cipher = None

a = Analysis(
    [os.path.join(SPECPATH, "updater_entry.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[
        "core.update.updater",
        "core.update.installer",
        "core.update.manifest",
        "core.update.verifier",
        "core.update.downloader",
        "core.logging_config",
        "core.paths",
        "core.version",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt6", "tkinter", "pytest"],
    win_no_prefer_redirects=True,
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
    name="Updater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)