# dev/_installers/ibeis_pyi_helper.py
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # repo root (…/ibeis)


def get_icon_path() -> str | None:
    """
    Use your existing icons:
      dev/_installers/ibsicon.ico
      dev/_installers/ibsicon.png
      dev/_installers/ibsicon.icns
    """
    if sys.platform == "win32":
        return str(HERE / "ibsicon.ico")
    if sys.platform == "darwin":
        return str(HERE / "ibsicon.icns")
    # Linux: EXE icon embedding doesn't really apply; keep None for safety.
    return None


def collect_everything():
    datas = []
    binaries = []
    hiddenimports = []

    # Big hitters (PyInstaller hooks exist, but collect_all is the “make it work” hammer)
    for pkg in ["PyQt5", "numpy", "scipy", "matplotlib", "cv2"]:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h

    # IBEIS + your stack
    for pkg in [
        "ibeis",
        "utool",
        "ubelt",
        "guitool_ibeis",
        "plottool_ibeis",
        "vtool_ibeis",
        "dtool_ibeis",
        "pyhesaff",
        "pyflann_ibeis",
        "vtool_ibeis_ext",
    ]:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h

    # Ensure IBEIS web assets are present (templates/static)
    datas += collect_data_files("ibeis", includes=["web/*", "web/**/*"])

    # Ensure compiled extension DLLs for your custom wheels get picked up
    for pkg in ["pyhesaff", "pyflann_ibeis", "vtool_ibeis_ext"]:
        binaries += collect_dynamic_libs(pkg)

    # A few historical “sometimes-missed” things (your __main__.py references these)
    hiddenimports += [
        "mpl_toolkits.axes_grid1",
        "scipy.sparse.csgraph._validation",
        "scipy.special._ufuncs_cxx",
    ]

    # De-dupe
    datas = list(dict.fromkeys(datas))
    binaries = list(dict.fromkeys(binaries))
    hiddenimports = sorted(set(hiddenimports))

    return datas, binaries, hiddenimports
