# dev/_installers/ibeis_pyi_helper.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

from PyInstaller.utils.hooks import collect_data_files

# Analysis() expects:
#   datas:    List[Tuple[src, dest]]
#   binaries: List[Tuple[src, dest]]
#   hiddenimports: List[str]
#
# We intentionally avoid collect_all() because it imports packages in isolation and
# can be extremely slow / fragile for scipy/matplotlib/sklearn graphs.

HERE = Path(__file__).resolve().parent

DataTuple = Tuple[str, str]      # (src, destdir)
BinaryTuple = Tuple[str, str]    # (src, destdir)


def get_icon_path() -> str | None:
    """
    Use your existing icons in dev/_installers/
    """
    if sys.platform == "win32":
        return str(HERE / "ibsicon.ico")
    if sys.platform == "darwin":
        return str(HERE / "ibsicon.icns")
    # Linux: no embedded EXE icon; installer/desktop file handles icons.
    return None


def _find_pkg_dir(pkgname: str) -> Path | None:
    """
    Find a package directory without importing it.
    Returns the directory containing __init__.py for packages.
    """
    spec = importlib.util.find_spec(pkgname)
    if spec is None:
        return None
    locs = getattr(spec, "submodule_search_locations", None)
    if not locs:
        return None
    return Path(list(locs)[0])


def _find_site_packages_root(pkgdir: Path) -> Path:
    """
    Given .../site-packages/<pkgname>/ return .../site-packages/
    """
    return pkgdir.parent


def _iter_files(d: Path) -> Iterable[Path]:
    # Avoid surprises with broken links, permission oddities.
    if not d.exists():
        return []
    return (p for p in d.rglob("*") if p.is_file())


def _collect_dir_as_datas(src_dir: Path, dest_prefix: str) -> List[DataTuple]:
    """
    Copy a directory tree as DATA tuples (src, destdir).
    destdir is where the file's parent directory goes inside the bundle.
    """
    out: List[DataTuple] = []
    for p in _iter_files(src_dir):
        rel = p.relative_to(src_dir)
        destdir = str(Path(dest_prefix) / rel.parent).replace("\\", "/")
        out.append((str(p), destdir))
    return out


def _collect_dir_as_binaries(src_dir: Path, dest_prefix: str) -> List[BinaryTuple]:
    """
    Copy only dll/pyd files under src_dir as BINARIES tuples.
    """
    out: List[BinaryTuple] = []
    for p in _iter_files(src_dir):
        if p.suffix.lower() in {".dll", ".pyd"}:
            rel = p.relative_to(src_dir)
            destdir = str(Path(dest_prefix) / rel.parent).replace("\\", "/")
            out.append((str(p), destdir))
    return out


def _collect_pkg_binaries(pkgname: str) -> List[BinaryTuple]:
    """
    Collect all .dll/.pyd files that live inside the package directory tree.
    Does not import the package.
    """
    pkgdir = _find_pkg_dir(pkgname)
    if pkgdir is None:
        return []
    # Put them under _internal/<pkgname>/...
    return _collect_dir_as_binaries(pkgdir, pkgname)


def _collect_sibling_dotlibs(pkgname: str) -> List[BinaryTuple]:
    """
    Collect sibling <pkgname>.libs directory if present:
      site-packages/numpy.libs/
      site-packages/scipy.libs/
      site-packages/sklearn.libs/
      site-packages/opencv_python.libs/
    """
    pkgdir = _find_pkg_dir(pkgname)
    if pkgdir is None:
        return []
    libsdir = pkgdir.with_name(pkgname + ".libs")
    if libsdir.is_dir():
        return _collect_dir_as_binaries(libsdir, libsdir.name)
    return []


def _collect_named_sibling_libs(sibling_dirname: str, anchor_pkg: str) -> List[BinaryTuple]:
    """
    Collect a sibling directory by exact name, using anchor_pkg to locate site-packages.
    Example: opencv-python uses 'opencv_python.libs' next to the 'cv2' package.
    """
    pkgdir = _find_pkg_dir(anchor_pkg)
    if pkgdir is None:
        return []
    site = _find_site_packages_root(pkgdir)
    sib = site / sibling_dirname
    if sib.is_dir():
        return _collect_dir_as_binaries(sib, sibling_dirname)
    return []


def _all_py_modules_in_package(pkgname: str) -> List[str]:
    """
    Enumerate all python modules in a package without importing it.
    This fixes dynamic imports like 'ibeis.annots' not being found.
    """
    pkgdir = _find_pkg_dir(pkgname)
    if pkgdir is None:
        return []
    site = _find_site_packages_root(pkgdir)
    mods: List[str] = []
    for py in pkgdir.rglob("*.py"):
        rel = py.relative_to(site).with_suffix("")  # ibeis/annots -> ibeis/annots
        mod = ".".join(rel.parts)
        mods.append(mod)
    # De-dupe but keep stable ordering-ish
    return sorted(set(mods))


def collect_everything():
    datas: List[DataTuple] = []
    binaries: List[BinaryTuple] = []
    hiddenimports: List[str] = []

    # ---- IBEIS data files (web templates/static) ----
    # collect_data_files does not import ibeis.
    datas += collect_data_files(
        "ibeis",
        includes=[
            "web/*",
            "web/**/*",
        ],
        excludes=[
            "**/*.pyc",
            "**/__pycache__/*",
        ],
    )

    # ---- Ensure ALL ibeis.* modules are available (dynamic imports) ----
    hiddenimports += _all_py_modules_in_package("ibeis")

    # ---- Your ctypes-loaded / custom wheels: include their package DLLs/PYDs ----
    # Avoid collect_dynamic_libs('pyhesaff') because it may import / attempt to load the DLL at build time.
    for pkg in ["pyhesaff", "pyflann_ibeis", "vtool_ibeis_ext"]:
        binaries += _collect_pkg_binaries(pkg)

    # ---- Bring in common wheel dependency DLL bundles (.libs) ----
    # These are the usual sources of OpenMP/BLAS/etc that ctypes-loaded DLLs depend on.
    for pkg in ["numpy", "scipy", "pandas", "shapely", "sklearn"]:
        binaries += _collect_sibling_dotlibs(pkg)

    # OpenCV wheel typically uses opencv_python.libs (or opencv_python_headless.libs)
    # adjacent to the cv2 package.
    binaries += _collect_named_sibling_libs("opencv_python.libs", anchor_pkg="cv2")
    binaries += _collect_named_sibling_libs("opencv_python_headless.libs", anchor_pkg="cv2")

    # ---- A few known “sometimes missed” modules referenced in ibeis/__main__.py ----
    hiddenimports += [
        "mpl_toolkits.axes_grid1",
        "scipy.sparse.csgraph._validation",
        "scipy.special._ufuncs_cxx",
    ]

    # De-dupe output tuples while preserving order
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
