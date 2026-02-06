"""PyInstaller-friendly entrypoint for IBEIS."""
from __future__ import annotations

import multiprocessing
import runpy


def main() -> None:
    multiprocessing.freeze_support()
    runpy.run_module("ibeis", run_name="__main__")


if __name__ == "__main__":
    main()
