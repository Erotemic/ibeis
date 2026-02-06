"""Helper utilities for modern PyInstaller IBEIS builds."""
from __future__ import annotations

import os
import site
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


def _safe_collect_data(package: str) -> list[tuple[str, str]]:
    try:
        return collect_data_files(package)
    except Exception:
        return []


def _safe_collect_submodules(package: str) -> list[str]:
    try:
        return collect_submodules(package)
    except Exception:
        return []


def _safe_collect_dynamic(package: str) -> list[tuple[str, str]]:
    try:
        return collect_dynamic_libs(package)
    except Exception:
        return []


def _find_site_packages() -> list[Path]:
    roots = set()
    try:
        for s in site.getsitepackages():
            roots.add(Path(s))
    except Exception:
        pass
    roots.add(Path(site.getusersitepackages()))
    return [p for p in roots if p.exists()]


def _collect_libs_dir(package_name: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for site_root in _find_site_packages():
        for libsdir in sorted(site_root.glob(f"{package_name}*.libs")):
            if libsdir.is_dir():
                for dll in libsdir.glob("*.dll"):
                    out.append((str(dll), str(Path("_internal") / libsdir.name)))
    return out


def _collect_cv2_extra_libs() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for site_root in _find_site_packages():
        for libdir_name in ("opencv_python.libs", "opencv_python_headless.libs"):
            libdir = site_root / libdir_name
            if libdir.is_dir():
                for dll in libdir.glob("*.dll"):
                    out.append((str(dll), str(Path("_internal") / libdir_name)))
    return out


def _collect_system_msvc_runtime() -> list[tuple[str, str]]:
    if not sys.platform.startswith("win"):
        return []

    runtime_names = [
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "concrt140.dll",
        "vcomp140.dll",
    ]
    sysroot = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    system32 = sysroot / "System32"
    binaries: list[tuple[str, str]] = []
    for name in runtime_names:
        src = system32 / name
        if src.exists():
            binaries.append((str(src), "_internal"))
    return binaries


def get_path_extensions(repo_root: Path, installers_dir: Path) -> list[str]:
    return [str(repo_root), str(installers_dir)]


def get_hidden_imports() -> list[str]:
    hiddenimports = set()
    hiddenimports.update(_safe_collect_submodules("ibeis"))
    hiddenimports.update(_safe_collect_submodules("win32ctypes"))
    hiddenimports.update(
        {
            "win32ctypes.core",
            "win32ctypes.pywin32",
            "win32ctypes.pywin32.pywintypes",
            "win32ctypes.pywin32.win32api",
        }
    )
    return sorted(hiddenimports)


def get_datas() -> list[tuple[str, str]]:
    datas: list[tuple[str, str]] = []
    datas.extend(_safe_collect_data("ibeis"))
    datas.extend(_safe_collect_data("win32ctypes"))
    return datas


def get_binaries() -> list[tuple[str, str]]:
    binaries: list[tuple[str, str]] = []
    for pkg in (
        "pyhesaff",
        "pyflann_ibeis",
        "vtool_ibeis_ext",
        "numpy",
        "scipy",
        "pandas",
        "shapely",
        "sklearn",
        "win32ctypes",
        "cv2",
    ):
        binaries.extend(_safe_collect_dynamic(pkg))

    for libs_pkg in ("numpy", "scipy", "pandas", "shapely", "scikit_learn"):
        binaries.extend(_collect_libs_dir(libs_pkg))

    binaries.extend(_collect_cv2_extra_libs())
    binaries.extend(_collect_system_msvc_runtime())

    deduped = {}
    for src, dst in binaries:
        deduped[(src, dst)] = None
    return list(deduped.keys())
