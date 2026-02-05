# dev/_installers/ibeis_app_entry.py
"""PyInstaller entrypoint for IBEIS.

Why this wrapper exists:
* Calls multiprocessing.freeze_support() (required on Windows when frozen).
* Keeps the actual app entry logic in ibeis.__main__.run_ibeis.
"""

from __future__ import annotations

import multiprocessing
import os
import sys


def main() -> None:
    multiprocessing.freeze_support()

    # Optional quick startup diagnostics (disabled by default)
    if os.environ.get("IBEIS_BOOT_DEBUG") == "1":
        print("[IBEIS_BOOT_DEBUG] sys.executable =", sys.executable)
        print("[IBEIS_BOOT_DEBUG] cwd           =", os.getcwd())
        print("[IBEIS_BOOT_DEBUG] argv          =", sys.argv)
        print("[IBEIS_BOOT_DEBUG] _MEIPASS      =", getattr(sys, "_MEIPASS", None))
        print("[IBEIS_BOOT_DEBUG] PATH(head)    =", os.environ.get("PATH", "").split(os.pathsep)[:10])

    # Help PyInstaller “see” dynamic imports / compiled submodules (safe if it fails)
    try:
        from ibeis.__main__ import dependencies_for_myprogram  # type: ignore
        dependencies_for_myprogram()
    except Exception:
        pass

    from ibeis.__main__ import run_ibeis
    run_ibeis()


if __name__ == "__main__":
    main()

