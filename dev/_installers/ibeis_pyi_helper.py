# dev/_installers/ibeis_pyi_helper.py
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

from PyInstaller.utils.hooks import collect_data_files

HERE = Path(__file__).resolve().parent

DataTuple = Tuple[str, str]      # (src, destdir)
BinaryTuple = Tuple[str, str]    # (src, destdir)


def get_icon_path() -> str | None:
    if sys.platform == "win32":
        return str(HERE / "ibsicon.ico")
    if sys.platform == "darwin":
        return str(HERE / "ibsicon.icns")
    return None


def _find_pkg_dir(pkgname: str) -> Path | None:
    """Find a package directory without importing it."""
    spec = importlib.util.find_spec(pkgname)
    if spec is None:
        return None
    locs = getattr(spec, "submodule_search_locations", None)
    if not locs:
        return None
    return Path(list(locs)[0])


def _find_site_packages_root(pkgdir: Path) -> Path:
    return pkgdir.parent


def _iter_files(d: Path) -> Iterable[Path]:
    if not d.exists():
        return []
    return (p for p in d.rglob("*") if p.is_file())


def _collect_dir_as_datas(src_dir: Path, dest_prefix: str, exts: set[str] | None = None) -> List[DataTuple]:
    out: List[DataTuple] = []
    for p in _iter_files(src_dir):
        if exts is not None and p.suffix.lower() not in exts:
            continue
        rel = p.relative_to(src_dir)
        destdir = str(Path(dest_prefix) / rel.parent).replace("\\", "/")
        out.append((str(p), destdir))
    return out


def _collect_dir_as_binaries(src_dir: Path, dest_prefix: str) -> List[BinaryTuple]:
    out: List[BinaryTuple] = []
    for p in _iter_files(src_dir):
        if p.suffix.lower() in {".dll", ".pyd"}:
            rel = p.relative_to(src_dir)
            destdir = str(Path(dest_prefix) / rel.parent).replace("\\", "/")
            out.append((str(p), destdir))
    return out


def _collect_pkg_binaries(pkgname: str) -> List[BinaryTuple]:
    pkgdir = _find_pkg_dir(pkgname)
    if pkgdir is None:
        return []
    return _collect_dir_as_binaries(pkgdir, pkgname)


def _collect_sibling_dotlibs(pkgname: str) -> List[BinaryTuple]:
    pkgdir = _find_pkg_dir(pkgname)
    if pkgdir is None:
        return []
    libsdir = pkgdir.with_name(pkgname + ".libs")
    if libsdir.is_dir():
        return _collect_dir_as_binaries(libsdir, libsdir.name)
    return []


def _collect_named_sibling_libs(sibling_dirname: str, anchor_pkg: str) -> List[BinaryTuple]:
    pkgdir = _find_pkg_dir(anchor_pkg)
    if pkgdir is None:
        return []
    site = _find_site_packages_root(pkgdir)
    sib = site / sibling_dirname
    if sib.is_dir():
        return _collect_dir_as_binaries(sib, sibling_dirname)
    return []


def _all_py_modules_in_package(pkgname: str) -> List[str]:
    pkgdir = _find_pkg_dir(pkgname)
    if pkgdir is None:
        return []
    site = _find_site_packages_root(pkgdir)
    mods: List[str] = []
    for py in pkgdir.rglob("*.py"):
        rel = py.relative_to(site).with_suffix("")
        mods.append(".".join(rel.parts))
    return sorted(set(mods))


def _collect_msvc_runtime_binaries() -> List[BinaryTuple]:
    """Include VC++ runtime DLLs app-locally for customer machines without the redist.

    Destination is '_internal' so they sit next to python313.dll, vcruntime*, etc.
    """
    if sys.platform != "win32":
        return []
    windir = Path(os.environ.get("WINDIR", r"C:\\Windows"))
    sys32 = windir / "System32"
    if not sys32.is_dir():
        return []

    patterns = [
        "msvcp140*.dll",
        "vcruntime140*.dll",
        "concrt140.dll",
        "vcomp140.dll",
    ]

    out: List[BinaryTuple] = []
    for pat in patterns:
        for p in sys32.glob(pat):
            out.append((str(p), "_internal"))
    return out


def collect_everything():
    datas: List[DataTuple] = []
    binaries: List[BinaryTuple] = []
    hiddenimports: List[str] = []

    # IBEIS assets
    datas += collect_data_files(
        "ibeis",
        includes=["web/*", "web/**/*"],
        excludes=["**/*.pyc", "**/__pycache__/*"],
    )

    # Dynamic imports in ibeis
    hiddenimports += _all_py_modules_in_package("ibeis")

    # Custom binary packages
    for pkg in ["pyhesaff", "pyflann_ibeis", "vtool_ibeis_ext"]:
        binaries += _collect_pkg_binaries(pkg)
        hiddenimports += _all_py_modules_in_package(pkg)

    # Wheel binary bundles
    for pkg in ["numpy", "scipy", "pandas", "shapely", "sklearn"]:
        binaries += _collect_sibling_dotlibs(pkg)

    # OpenCV wheel extra DLL folders
    binaries += _collect_named_sibling_libs("opencv_python.libs", anchor_pkg="cv2")
    binaries += _collect_named_sibling_libs("opencv_python_headless.libs", anchor_pkg="cv2")

    # VC++ runtime (portable folder installs)
    binaries += _collect_msvc_runtime_binaries()

    # win32ctypes (pywin32-ctypes)
    win32_dir = _find_pkg_dir("win32ctypes")
    if win32_dir is not None:
        datas += _collect_dir_as_datas(win32_dir, "win32ctypes", exts={".py", ".pyi"})
        hiddenimports += _all_py_modules_in_package("win32ctypes")
    else:
        hiddenimports += [
            "win32ctypes.core",
            "win32ctypes.pywin32",
            "win32ctypes.pywin32.win32api",
            "win32ctypes.pywin32.pywintypes",
            "win32ctypes.pywin32.win32con",
        ]

    # Known sometimes-missed modules
    hiddenimports += [
        "mpl_toolkits.axes_grid1",
        "scipy.sparse.csgraph._validation",
        "scipy.special._ufuncs_cxx",
    ]

    # Deduplicate pairs (keep order)
    def _dedupe_pairs(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        seen = set()
        out = []
        for src, dst in pairs:
            key = (src, dst)
            if key not in seen:
                seen.add(key)
                out.append((src, dst))
        return out

    datas = _dedupe_pairs(datas)
    binaries = _dedupe_pairs(binaries)
    hiddenimports = sorted(set(hiddenimports))

    return datas, binaries, hiddenimports
