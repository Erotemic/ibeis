# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

from dev._installers import ibeis_pyi_helper

HERE = Path(globals().get("SPECPATH", os.getcwd())).resolve()
REPO_ROOT = HERE.parents[1]
INSTALLERS_DIR = HERE

pathex = ibeis_pyi_helper.get_path_extensions(REPO_ROOT, INSTALLERS_DIR)
datas = ibeis_pyi_helper.get_datas()
binaries = ibeis_pyi_helper.get_binaries()
hiddenimports = ibeis_pyi_helper.get_hidden_imports()

block_cipher = None

analysis = Analysis(
    [str(INSTALLERS_DIR / "ibeis_app_entry.py")],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[str(INSTALLERS_DIR / "rthook_add_dll_dirs.py")],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

common_exe_kwargs = dict(
    icon=str(INSTALLERS_DIR / "ibsicon.ico"),
    exclude_binaries=True,
)

exe_gui = EXE(
    pyz,
    analysis.scripts,
    analysis.zipfiles,
    analysis.datas,
    [],
    name="IBEIS",
    console=False,
    **common_exe_kwargs,
)

exe_console = EXE(
    pyz,
    analysis.scripts,
    analysis.zipfiles,
    analysis.datas,
    [],
    name="IBEIS-console",
    console=True,
    **common_exe_kwargs,
)

coll = COLLECT(
    exe_gui,
    exe_console,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=False,
    name="IBEIS-dist",
)
