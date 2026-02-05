# dev/_installers/rthook_add_dll_dirs.py
import os
import sys
from pathlib import Path

_DLL_DIR_HANDLES = []  # keep add_dll_directory handles alive


def add_dir(p: Path):
    p = Path(p)
    if not p.is_dir():
        return

    # Prepend to PATH (robust for ctypes-loaded DLL deps)
    os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")

    # Also add to DLL search path (and KEEP HANDLE)
    if hasattr(os, "add_dll_directory"):
        try:
            _DLL_DIR_HANDLES.append(os.add_dll_directory(str(p)))
        except Exception:
            pass


base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
internal = base / "_internal"

add_dir(base)
add_dir(internal)

# Add all wheel "libs" dirs that may contain dependency DLLs
if internal.is_dir():
    for p in internal.glob("*.libs"):
        add_dir(p)

# Add known package dirs too
for name in [
    "pyhesaff", "pyhesaff.libs",
    "pyflann_ibeis", "pyflann_ibeis.libs",
    "vtool_ibeis_ext", "vtool_ibeis_ext.libs",
    "numpy.libs", "scipy.libs",
    "cv2",
]:
    add_dir(internal / name)
