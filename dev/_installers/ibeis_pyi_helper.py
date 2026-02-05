# dev/_installers/ibeis_pyi_helper.py
from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

try:
    # PyInstaller 6.x
    from PyInstaller.building.datastruct import Tree
except Exception:  # pragma: no cover
    Tree = None  # type: ignore


HERE = Path(__file__).resolve().parent


def get_icon_path() -> str | None:
    if sys.platform == "win32":
        return str(HERE / "ibsicon.ico")
    if sys.platform == "darwin":
        return str(HERE / "ibsicon.icns")
    return None


def _pkg_dir(pkgname: str) -> Path | None:
    """
    Find package directory WITHOUT importing it.
    """
    spec = importlib.util.find_spec(pkgname)
    if spec is None:
        return None
    locs = getattr(spec, "submodule_search_locations", None)
    if not locs:
        return None
    return Path(list(locs)[0])


def _collect_sibling_libs(pkgname: str):
    """
    Collect delvewheel-style sibling dir: <pkgname>.libs
    Example: site-packages/pyhesaff.libs/*.dll
    """
    if Tree is None:
        return []

    pkgdir = _pkg_dir(pkgname)
    if pkgdir is None:
        return []

    sib = pkgdir.with_name(pkgname + ".libs")
    if sib.exists():
        # Prefix ensures it lands in _internal/<name>.libs
        return Tree(str(sib), prefix=sib.name).tolist()
    return []


def collect_everything():
    datas = []
    binaries = []
    hiddenimports = []

    # --- IBEIS data you likely need at runtime ---
    # (collect_data_files does NOT import ibeis)
    datas += collect_data_files("ibeis", includes=["web/*", "web/**/*"], excludes=["**/*.pyc"])

    # --- DLL-heavy wheels that use ctypes to load their own *.dll ---
    for pkg in ["pyhesaff", "pyflann_ibeis", "vtool_ibeis_ext"]:
        binaries += collect_dynamic_libs(pkg)
        binaries += _collect_sibling_libs(pkg)

    # --- Often helpful for scientific wheels (usually redundant with built-in hooks, but safe) ---
    for pkg in ["numpy", "scipy", "cv2"]:
        binaries += collect_dynamic_libs(pkg)

    # Your __main__.py already hints these are sometimes missed
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
