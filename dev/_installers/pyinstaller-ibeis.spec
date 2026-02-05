# dev/_installers/pyinstaller-ibeis.spec
# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

block_cipher = None

# PyInstaller provides SPECPATH; __file__ is not always defined.
HERE = Path(globals().get("SPECPATH", os.getcwd())).resolve()  # dev/_installers
ROOT = HERE.parent.parent  # repo root (.../ibeis)

sys.path.insert(0, str(HERE))
import ibeis_pyi_helper as helper  # noqa: E402

datas, binaries, hiddenimports = helper.collect_everything()
icon_path = helper.get_icon_path()

entry_script = str(HERE / "ibeis_app_entry.py")

a = Analysis(
    [entry_script],
    pathex=[str(ROOT), str(HERE)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[str(HERE / "rthook_add_dll_dirs.py")],
    excludes=["torch", "tensorflow"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe_gui = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IBEIS",
    console=False,
    icon=icon_path,
)

exe_console = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IBEIS-console",
    console=True,
    icon=icon_path,
)

coll = COLLECT(
    exe_gui,
    exe_console,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="IBEIS-dist",
)
