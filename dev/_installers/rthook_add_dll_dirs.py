# dev/_installers/rthook_add_dll_dirs.py
"""Runtime hook to make ctypes-loaded DLLs work in PyInstaller builds (Windows).

Notes
-----
* Python 3.8+ on Windows uses 'safe DLL search'. You need to add directories explicitly.
* os.add_dll_directory() returns a handle that MUST be kept alive.
* For debugging on customer machines, we provide an opt-in test load that bypasses
  PyInstaller's ctypes wrapper by calling LoadLibraryExW directly.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

_DLL_DIR_HANDLES: list[object] = []


def _prepend_path(p: Path) -> None:
    os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")


def _add_dll_dir(p: Path) -> None:
    p = Path(p)
    if not p.is_dir():
        return
    _prepend_path(p)
    if hasattr(os, "add_dll_directory"):
        try:
            _DLL_DIR_HANDLES.append(os.add_dll_directory(str(p)))
        except Exception:
            pass


def _resolve_appdir() -> Path:
    # onefile: sys._MEIPASS points to extracted bundle directory
    # onedir: sys.executable's parent is the dist directory
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()


def _win_last_error_message(err: int) -> str:
    # FormatMessageW wrapper
    FORMAT_MESSAGE_FROM_SYSTEM = 0x00001000
    buf = ctypes.create_unicode_buffer(2048)
    n = ctypes.windll.kernel32.FormatMessageW(
        FORMAT_MESSAGE_FROM_SYSTEM,
        None,
        err,
        0,
        buf,
        len(buf),
        None,
    )
    if n:
        return buf.value.strip()
    return f"Windows error {err}"


appdir = _resolve_appdir()
internal = (appdir / "_internal") if (appdir / "_internal").is_dir() else appdir

# Add these in an order that matches typical dependency resolution
_add_dll_dir(appdir)
_add_dll_dir(internal)
_add_dll_dir(internal / "pyhesaff")      # hesaff.dll + opencv_*.dll live here
_add_dll_dir(internal / "cv2")
_add_dll_dir(internal / "pyflann_ibeis")
_add_dll_dir(internal / "vtool_ibeis_ext")

for p in internal.glob("*.libs"):
    _add_dll_dir(p)

if os.environ.get("IBEIS_DLL_DEBUG") == "1":
    print("[rthook] appdir   =", appdir)
    print("[rthook] internal =", internal)
    print("[rthook] added DLL dirs (count) =", len(_DLL_DIR_HANDLES))
    print("[rthook] PATH(head) =", os.environ.get("PATH", "").split(os.pathsep)[:12])

    # Bypass PyInstaller's ctypes wrapper to get a real Win32 error code on failures
    hesaff = internal / "pyhesaff" / "hesaff.dll"
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError.argtypes = [ctypes.c_ulong]
        kernel32.GetLastError.restype = ctypes.c_ulong
        kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_ulong]
        kernel32.LoadLibraryExW.restype = ctypes.c_void_p
        kernel32.FreeLibrary.argtypes = [ctypes.c_void_p]
        kernel32.FreeLibrary.restype = ctypes.c_int

        kernel32.SetLastError(0)

        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR = 0x00000100
        LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x00001000
        h = kernel32.LoadLibraryExW(str(hesaff), None, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS)

        if not h:
            err = int(kernel32.GetLastError())
            common = {126: "ERROR_MOD_NOT_FOUND (missing dependency)", 193: "ERROR_BAD_EXE_FORMAT (x86/x64 mismatch)", 1114: "ERROR_DLL_INIT_FAILED (dependency init failed)"}
            print("[rthook] test LoadLibraryExW FAILED:", hesaff)
            print("[rthook]   GetLastError =", err, "-", _win_last_error_message(err))
            if err in common:
                print("[rthook]   hint:", common[err])
        else:
            print("[rthook] test LoadLibraryExW OK:", hesaff)
            kernel32.FreeLibrary(h)
    except Exception as ex:
        print("[rthook] test LoadLibraryExW ERROR:", repr(ex))
