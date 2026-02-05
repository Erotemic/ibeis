import os
import sys
from pathlib import Path


def add_dir(p: Path):
    try:
        if p.is_dir():
            os.add_dll_directory(str(p))
    except Exception:
        pass

# For onefile: sys._MEIPASS; for onedir: folder containing the exe
base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
internal = base / "_internal"

# Always add these
add_dir(base)
add_dir(internal)

# Add common wheel “.libs” locations (and the packages themselves)
for name in [
    "pyhesaff", "pyhesaff.libs",
    "pyflann_ibeis", "pyflann_ibeis.libs",
    "vtool_ibeis_ext", "vtool_ibeis_ext.libs",
    "numpy.libs", "scipy.libs", "cv2",
]:
    add_dir(internal / name)
