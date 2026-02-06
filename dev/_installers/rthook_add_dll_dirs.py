"""Runtime hook for Windows DLL resolution in frozen IBEIS builds."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

_DLL_DIR_HANDLES = []


def _debug(msg: str) -> None:
    if os.environ.get("IBEIS_DLL_DEBUG", "0") == "1":
        print(f"[rthook] {msg}")


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _candidate_roots() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        appdir = Path(sys.executable).resolve().parent
    else:
        appdir = Path.cwd().resolve()

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        internal = Path(meipass).resolve()
    else:
        internal = appdir / "_internal"
    return appdir, internal


def _collect_dll_dirs(appdir: Path, internal: Path) -> list[Path]:
    dirs: list[Path] = [
        appdir,
        internal,
        internal / "pyhesaff",
        internal / "cv2",
        internal / "pyflann_ibeis",
        internal / "vtool_ibeis_ext",
    ]
    if internal.exists():
        dirs.extend(sorted(p for p in internal.glob("*.libs") if p.is_dir()))
    return [d for d in dirs if d.exists()]


def _update_dll_search_path(dll_dirs: list[Path]) -> None:
    if not _is_windows():
        return

    for dpath in dll_dirs:
        try:
            handle = os.add_dll_directory(str(dpath))
            _DLL_DIR_HANDLES.append(handle)
        except (FileNotFoundError, OSError):
            pass

    current_path = os.environ.get("PATH", "")
    prefix = os.pathsep.join(str(d) for d in dll_dirs)
    os.environ["PATH"] = f"{prefix}{os.pathsep}{current_path}" if current_path else prefix


def _format_winerror(err_code: int) -> str:
    if not err_code:
        return "success"
    return ctypes.FormatError(err_code).strip()


def _diagnostic_hesaff_load(internal: Path) -> None:
    if not _is_windows() or os.environ.get("IBEIS_DLL_DEBUG", "0") != "1":
        return

    hesaff = internal / "pyhesaff" / "hesaff.dll"
    if not hesaff.exists():
        _debug(f"hesaff not found at {hesaff}")
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    load_library_exw = kernel32.LoadLibraryExW
    load_library_exw.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    load_library_exw.restype = ctypes.c_void_p
    free_library = kernel32.FreeLibrary
    free_library.argtypes = [ctypes.c_void_p]
    free_library.restype = ctypes.c_int

    LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008
    handle = load_library_exw(str(hesaff), None, LOAD_WITH_ALTERED_SEARCH_PATH)
    if handle:
        _debug(f"LoadLibraryExW succeeded for {hesaff}")
        free_library(handle)
        return

    err_code = ctypes.get_last_error()
    _debug(
        "LoadLibraryExW failed for {} err={} msg={!r}".format(
            hesaff, err_code, _format_winerror(err_code)
        )
    )


def _main() -> None:
    if not _is_windows():
        return
    appdir, internal = _candidate_roots()
    dll_dirs = _collect_dll_dirs(appdir, internal)
    _update_dll_search_path(dll_dirs)
    _debug(f"appdir={appdir}")
    _debug(f"internal={internal}")
    _debug(f"added DLL dirs count={len(_DLL_DIR_HANDLES)}")
    _debug(f"PATH head={os.environ.get('PATH', '')[:500]}")
    _diagnostic_hesaff_load(internal)


_main()
