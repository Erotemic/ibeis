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


import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
from PyInstaller.building.datastruct import Tree


def _pkg_dir(pkgname: str) -> Path | None:
    spec = importlib.util.find_spec(pkgname)
    locs = getattr(spec, "submodule_search_locations", None) if spec else None
    if not locs:
        return None
    return Path(list(locs)[0])


def _collect_sibling_libs_as_binaries(pkgname: str):
    """
    Collect sibling dir like site-packages/<pkg>.libs into _internal/<pkg>.libs.
    Mark DLL/PYD as BINARY so they land in the right place.
    """
    pkgdir = _pkg_dir(pkgname)
    if pkgdir is None:
        return []
    sib = pkgdir.with_name(pkgname + ".libs")
    if not sib.exists():
        return []
    items = Tree(str(sib), prefix=sib.name).tolist()
    out = []
    for dst, src, typ in items:
        ext = str(src).lower()
        if ext.endswith((".dll", ".pyd")):
            out.append((dst, src, "BINARY"))
        else:
            out.append((dst, src, "DATA"))
    return out


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


def _all_modules_in_package(pkgname: str) -> list[str]:
    pkgdir = _pkg_dir(pkgname)
    if pkgdir is None:
        return []
    root = pkgdir.parent  # site-packages/
    mods = []
    for py in pkgdir.rglob("*.py"):
        rel = py.relative_to(root).with_suffix("")  # e.g. ibeis/annots -> ibeis.annots
        mod = ".".join(rel.parts)
        # skip __init__? keep it; harmless
        mods.append(mod)
    return mods


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
        binaries += _collect_sibling_libs_as_binaries(pkg)

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

    hiddenimports += _all_modules_in_package("ibeis")

    # Keep your web/templates data
    datas += collect_data_files("ibeis", includes=["web/*", "web/**/*"])

    return datas, binaries, hiddenimports
