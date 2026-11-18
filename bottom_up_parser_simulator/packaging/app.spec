# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the main application (onedir build).

Build from the project root:

    python -m PyInstaller --noconfirm packaging/app.spec

Produces ``dist/ParseCraft/`` containing the executable,
bundled Python/runtime, ``version.json``, and all application resources.
"""

import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

block_cipher = None

hidden_imports = (
    collect_submodules("core")
    + collect_submodules("gui")
    + collect_submodules("models")
)

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "version.json"), "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    win_no_prefer_redirects=True,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ParseCraft",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ParseCraft",
)