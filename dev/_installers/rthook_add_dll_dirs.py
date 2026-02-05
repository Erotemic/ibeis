# dev/_installers/rthook_add_dll_dirs.py
"""Runtime hook to make ctypes-loaded DLLs work in PyInstaller builds (Windows).

Key points:
* Python 3.8+ uses safe DLL search on Windows; you must add directories explicitly.
* os.add_dll_directory() returns a handle that MUST be kept alive, or the directory is removed.
* We also prepend PATH for libraries that still rely on PATH-based resolution.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_DLL_DIR_HANDLES: list[object] = []


def _add_dll_dir(p: Path) -> None:
    p = Path(p)
    if not p.is_dir():
        return

    # Prepend PATH (helps some loaders; also useful for debugging)
    os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")

    # AddDllDirectory (preferred under Python's safe DLL loading)
    if hasattr(os, "add_dll_directory"):
        try:
            _DLL_DIR_HANDLES.append(os.add_dll_directory(str(p)))
        except Exception:
            # Don't hard-fail the app if Windows rejects the directory for any reason
            pass


def _resolve_base_dir() -> Path:
    # onefile: sys._MEIPASS points to extracted bundle directory
    # onedir: sys.executable's parent is the dist directory
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return base


base = _resolve_base_dir()

# PyInstaller onedir layout typically has a sibling "_internal" directory.
# On onefile, it may also exist under _MEIPASS.
if (base / "_internal").is_dir():
    internal = base / "_internal"
elif base.name.lower() == "_internal":
    internal = base
else:
    internal = base / "_internal"

# Always add these
_add_dll_dir(base)
_add_dll_dir(internal)

# Critical: pyhesaff ships hesaff.dll + opencv_*.dll in this directory; deps must be discoverable.
_add_dll_dir(internal / "pyhesaff")

# Other common binary dependency locations in your build
_add_dll_dir(internal / "cv2")
_add_dll_dir(internal / "pyflann_ibeis")
_add_dll_dir(internal / "vtool_ibeis_ext")

# Common wheel binary bundles (numpy.libs, scipy.libs, etc.)
if internal.is_dir():
    for p in internal.glob("*.libs"):
        _add_dll_dir(p)

# Optional debug
if os.environ.get("IBEIS_DLL_DEBUG") == "1":
    print("[rthook] base     =", base)
    print("[rthook] internal =", internal)
    print("[rthook] added DLL dirs (count) =", len(_DLL_DIR_HANDLES))
    print("[rthook] PATH(head) =", os.environ.get("PATH", "").split(os.pathsep)[:12])
