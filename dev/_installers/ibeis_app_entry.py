# dev/_installers/ibeis_app_entry.py
"""PyInstaller entrypoint for IBEIS."""

from __future__ import annotations

import multiprocessing
import os
import sys


def _ensure_standard_streams() -> None:
    """Provide null standard streams for the windowed Windows executable.

    PyInstaller's Windows ``console=False`` bootloader follows ``pythonw.exe``
    and leaves ``sys.stdin``, ``sys.stdout``, and ``sys.stderr`` as ``None``.
    IBEIS and some of its dependencies contain legacy console writes, so give
    those writes harmless file objects when no console exists.  The console
    executable already has real streams and is left unchanged.
    """
    if sys.stdin is None:
        sys.stdin = open(os.devnull, "r")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def _frozen_selftest() -> int:
    """Verify runtime source-introspection works in the frozen app.

    IBEIS/utool parse function source at runtime, so the bundle must ship
    .py files (see SOURCE_INTROSPECTED_PKGS in ibeis_pyi_helper.py). This
    reproduces the 'Advanced ID interface' crash path without a GUI.

    Run via: IBEIS_FROZEN_SELFTEST=1 IBEIS-console.exe  (exit 0 = pass)
    """
    import traceback

    try:
        import utool as ut
        from ibeis.other import ibsfuncs

        src = ut.get_func_sourcecode(ibsfuncs.get_annot_stats_dict)
        assert "get_annot_stats_dict" in src
        keys = ut.parse_func_kwarg_keys(ibsfuncs.get_annot_stats_dict)
        assert keys, "expected nonempty kwarg keys"
    except Exception:
        traceback.print_exc()
        print("[selftest] FAILED: source introspection unavailable in frozen app")
        return 1
    print(f"[selftest] PASSED: source introspection OK ({len(keys)} kwarg keys)")
    return 0


def main() -> None:
    _ensure_standard_streams()
    multiprocessing.freeze_support()

    if os.environ.get("IBEIS_FROZEN_SELFTEST") == "1":
        sys.exit(_frozen_selftest())

    if os.environ.get("IBEIS_BOOT_DEBUG") == "1":
        print("[IBEIS_BOOT_DEBUG] sys.executable =", sys.executable)
        print("[IBEIS_BOOT_DEBUG] cwd           =", os.getcwd())
        print("[IBEIS_BOOT_DEBUG] argv          =", sys.argv)
        print("[IBEIS_BOOT_DEBUG] _MEIPASS      =", getattr(sys, "_MEIPASS", None))

    # Best-effort: helps PyInstaller discover dynamically imported pieces
    try:
        from ibeis.__main__ import dependencies_for_myprogram  # type: ignore
        dependencies_for_myprogram()
    except Exception:
        pass

    from ibeis.__main__ import run_ibeis
    run_ibeis()


if __name__ == "__main__":
    main()
