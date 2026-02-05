# dev/_installers/rthook_add_dll_dirs.py
"""
Runtime hook to make ctypes-loaded DLLs work in PyInstaller builds (Windows).

Why this exists:
- On modern Python/Windows, DLL search is “safe” by default.
- os.add_dll_directory() only helps if the loader uses the right LoadLibraryEx flags.
- Many projects using ctypes do not pass winmode=..., so dependencies in adjacent folders
  are not found even though you've added dirs.
- We therefore:
  1) add known DLL directories (and keep handles alive)
  2) prepend PATH (still helps some cases)
  3) monkeypatch ctypes.CDLL/WinDLL to provide a good default winmode for absolute paths
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

_DLL_DIR_HANDLES: list[object] = []

# Windows loader flags
LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR = 0x00000100
LOAD_LIBRARY_SEARCH_USER_DIRS = 0x00000400
LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x00001000

DEFAULT_WINMODE = (
    LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR
    | LOAD_LIBRARY_SEARCH_USER_DIRS
    | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS
)


def _add_dll_dir(p: Path) -> None:
    p = Path(p)
    if not p.is_dir():
        return

    # Prepend PATH (some loaders still consult this)
    os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")

    # AddDllDirectory (must keep handle alive!)
    if hasattr(os, "add_dll_directory"):
        try:
            _DLL_DIR_HANDLES.append(os.add_dll_directory(str(p)))
        except Exception:
            pass


def _resolve_dirs():
    # PyInstaller sometimes sets sys._MEIPASS even for onedir.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass).resolve()
        # If base is "...\\_internal", treat its parent as the app dir.
        if base.name.lower() == "_internal":
            appdir = base.parent
            internal = base
        else:
            appdir = base
            internal = base / "_internal"
    else:
        appdir = Path(sys.executable).resolve().parent
        internal = appdir / "_internal"

    return appdir, internal


def _patch_ctypes_winmode():
    # Patch ctypes.CDLL/WinDLL so that absolute-path loads use a sane winmode.
    orig_cdll = ctypes.CDLL
    orig_windll = ctypes.WinDLL

    def cdll_patched(name, *args, **kwargs):
        if sys.platform == "win32" and kwargs.get("winmode", None) is None:
            try:
                s = os.fspath(name)
                if os.path.isabs(s):
                    kwargs["winmode"] = DEFAULT_WINMODE
            except Exception:
                pass
        return orig_cdll(name, *args, **kwargs)

    def windll_patched(name, *args, **kwargs):
        if sys.platform == "win32" and kwargs.get("winmode", None) is None:
            try:
                s = os.fspath(name)
                if os.path.isabs(s):
                    kwargs["winmode"] = DEFAULT_WINMODE
            except Exception:
                pass
        return orig_windll(name, *args, **kwargs)

    ctypes.CDLL = cdll_patched  # type: ignore[assignment]
    ctypes.WinDLL = windll_patched  # type: ignore[assignment]


# ---- Main hook behavior ----
_appdir, _internal = _resolve_dirs()

_add_dll_dir(_appdir)
_add_dll_dir(_internal)

# Critical: hesaff.dll and its opencv_*.dll live here
_add_dll_dir(_internal / "pyhesaff")

# Common locations in your bundle
_add_dll_dir(_internal / "cv2")
_add_dll_dir(_internal / "pyflann_ibeis")
_add_dll_dir(_internal / "vtool_ibeis_ext")

# Wheel .libs bundles (numpy.libs, scipy.libs, shapely.libs, etc.)
if _internal.is_dir():
    for p in _internal.glob("*.libs"):
        _add_dll_dir(p)

# Patch ctypes so user-added DLL dirs + dll-load-dir are actually used
_patch_ctypes_winmode()

# Optional debug / proof test
if os.environ.get("IBEIS_DLL_DEBUG") == "1":
    print("[rthook] appdir   =", _appdir)
    print("[rthook] internal =", _internal)
    print("[rthook] added DLL dirs (count) =", len(_DLL_DIR_HANDLES))
    print("[rthook] PATH(head) =", os.environ.get("PATH", "").split(os.pathsep)[:12])

    test = _internal / "pyhesaff" / "hesaff.dll"
    if test.exists():
        try:
            ctypes.WinDLL(str(test), winmode=DEFAULT_WINMODE)
            print("[rthook] test load OK:", test)
        except OSError as ex:
            print("[rthook] test load FAILED:", repr(ex), "winerror=", getattr(ex, "winerror", None))

