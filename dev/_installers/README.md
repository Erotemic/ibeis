# Building & Testing the IBEIS Windows Installer

This directory contains everything needed to turn a source checkout into a
Windows installer (`IBEIS-Setup-<version>.exe`) and to verify the result on a
clean Windows VM. The same script drives two generated xcookie artifact jobs:
`build_windows_installer_integration` in the test workflow builds selected
pure-Python dependencies from the exact `tpl/` submodule revisions, while
`build_windows_installer` in the release workflow uses only published PyPI
dependencies. Both jobs are declared under `[tool.xcookie.ci_artifacts.*]` in
`pyproject.toml`; edit those declarations rather than generated workflow files.

Key files:

| File | Role |
|---|---|
| `build_installer.ps1` | One-stop build driver (venv, deps, PyInstaller, checks, Inno) |
| `pyinstaller-ibeis.spec` | PyInstaller spec (onedir; GUI + console exes) |
| `ibeis_pyi_helper.py` | Collects binaries, data files, hidden imports, and **`.py` sources** (required — IBEIS introspects function source at runtime) |
| `ibeis_app_entry.py` | Frozen-app entry point; also hosts the self-test |
| `rthook_add_dll_dirs.py` | Runtime hook so ctypes-loaded DLLs resolve on Windows |
| `win_installer_script.iss` | Inno Setup script (installs to `C:\Program Files\IBEIS`) |

## 1. VM prerequisites

* Windows 10/11 x64 with admin rights (needed to install Inno Setup via
  winget and to run the produced installer).
* **Python on PATH** — either the `py` launcher or `python`. If the VM has
  nothing: `winget install Python.Python.3.13` (or the python.org installer;
  check "Add to PATH"). The build script bootstraps everything else itself
  (uv, the venv, project deps, PyInstaller, Inno Setup).
* PowerShell 5.1 or 7 both work. `winget` is preinstalled on Win10 21H2+/Win11;
  without it, preinstall [Inno Setup 6](https://jrsoftware.org/isdl.php)
  manually — the script finds it in Program Files, Program Files (x86),
  `%LOCALAPPDATA%\Programs`, or PATH.
* ~10 GB free disk (venv + build + dist).
* Git is optional for ordinary/release installer builds: a source zip/tarball
  works and dependencies come from PyPI. `-LocalPurePythonTpl` is an explicit
  integration mode that requires Git when its selected `tpl/` submodules are
  not already populated. It currently allows only `utool` and
  `guitool_ibeis`; native-extension packages remain PyPI-backed.

## 2. Get the source

Either clone (no `--recursive` needed):

```powershell
git clone https://github.com/Erotemic/ibeis.git
cd ibeis
```

or copy/extract a source archive onto the VM and `cd` into it.

## 3. Build

From the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\dev\_installers\build_installer.ps1 -Clean -Checks -SmokeTest -Inno
```

That runs the full pipeline: fresh venv → deps → PyInstaller → post-build
checks (including the frozen self-test, see below) → smoke test → Inno
installer. Expect several minutes on the first run (dependency downloads);
rebuilds are faster.

Useful variants (see `-ShowUsage` or `Get-Help` on the script for all of them):

```powershell
# PyInstaller + Inno only, no checks (the default when no targets are given)
.\dev\_installers\build_installer.ps1

# Integration build against selected pure-Python tpl/ revisions
.\dev\_installers\build_installer.ps1 -Clean -LocalPurePythonTpl -Checks -SmokeTest -Inno

# Just rebuild the app directory, keeping the venv
.\dev\_installers\build_installer.ps1 -PyInstaller

# Environment sanity check without building anything
.\dev\_installers\build_installer.ps1 -DiagnosticsOnly
```

The integration mode first installs IBEIS normally from its declared dependency
set, then builds wheels for the allowlisted submodules and force-installs those
wheel files with `--no-deps`. Every local wheel must end in `-none-any.whl`.
The build writes `dist\diagnostics\local_tpl_packages.txt` with the exact
submodule revisions and wheel filenames. This mode is for CI/PR integration
feedback; release installers deliberately omit it so the release still proves
that the published package graph is complete.

Outputs land in `dist\`:

| Path | What it is |
|---|---|
| `dist\IBEIS-dist\` | The onedir app: `IBEIS.exe` (GUI, no console), `IBEIS-console.exe` (same app with a console window), `_internal\` (everything else) |
| `dist\installer\IBEIS-Setup-<version>.exe` | The Inno installer (version is read from `ibeis/__init__.py`) |
| `dist\diagnostics\` | `build_transcript.txt`, `frozen_selftest.txt`, smoke-test stdout/stderr |

## 4. Verify the build before installing

The `-Checks` target already ran these, but they can be re-run by hand on
`dist\IBEIS-dist\` (or on an installed copy in `C:\Program Files\IBEIS`):

```powershell
# Frozen self-test: exercises runtime source introspection (the historical
# "Advanced ID interface" crash path). Prints PASSED/FAILED, exit code 0/1.
$env:IBEIS_FROZEN_SELFTEST = "1"
.\dist\IBEIS-dist\IBEIS-console.exe
Remove-Item Env:IBEIS_FROZEN_SELFTEST
```

Two more opt-in diagnostic hooks exist for debugging on customer machines:

* `IBEIS_BOOT_DEBUG=1` — prints `sys.executable`, cwd, argv, and the
  PyInstaller extraction dir at startup.
* `IBEIS_DLL_DEBUG=1` — prints every DLL directory the runtime hook
  registered, then test-loads `hesaff.dll` via `LoadLibraryExW` and decodes
  the Win32 error on failure (126 = missing dependency, 193 = x86/x64
  mismatch, 1114 = dependency init failed).

## 5. Install and test like a user

1. Run `dist\installer\IBEIS-Setup-<version>.exe` (elevation prompt is
   expected; it installs to `C:\Program Files\IBEIS`). Installing over an
   existing copy is fine — the installer upgrades in place.
2. Launch **IBEIS (Console)** from the Start Menu for testing — it is the
   same app as the plain IBEIS shortcut but shows the log console, which is
   what you want when something goes wrong.
3. Check the startup banner: it prints `ibeis.__version__` — confirm it
   matches the build you just made (stale-build confusion has burned us
   before).
4. Manual smoke checklist (in order of historical breakage):
   * Create a new database somewhere under your user profile
     (e.g. `Documents\IBEIS\testdb`). Do **not** put it in Program Files.
   * Import a handful of images (File → Import).
   * Detect/add annotations on a couple of images and assign a species.
   * Open the annotation editor on an image (double-click) and draw/edit a box.
   * Run **ID → Advanced ID interface** — this dialog exercises the runtime
     introspection machinery and is the thing that crashed on 2.4.x builds.
   * Run a query and open the match review interface.
5. If anything fails, collect and send back:
   * the full console output (select-all in the console window),
   * `dist\diagnostics\` from the build (if you built locally),
   * the version banner and the Windows version.

## 6. Troubleshooting

* **`OSError: could not get source code`** — the build is missing bundled
  `.py` sources; you are almost certainly running a stale (pre-2.5.0)
  installer. Rebuild from current source; the frozen self-test now fails the
  build if this regresses.
* **`Could not find ISCC.exe`** — Inno Setup is not installed and winget was
  unavailable. Install Inno Setup 6 manually, then re-run with `-Inno`.
* **DLL load failures at startup** — re-run with `IBEIS_DLL_DEBUG=1` (see
  above) and check whether the VC++ runtime is present; the installer ships
  `msvcp140`/`vcruntime140` app-locally, but a truly ancient VM may need the
  [VC++ redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).
  Optionally drop `vcredist_x64.exe` next to `win_installer_script.iss`
  before building and the installer will bundle + offer it automatically.
* **Databases/caches appearing in odd places** — if no workdir is configured
  the app now defaults to a per-user data directory (never the install dir).
  Set it explicitly via the GUI or `IBEIS-console.exe --set-workdir <path>`.

## 7. macOS

`mac_dmg_builder.sh` and `Info.plist` are HotSpotter-era leftovers and are
not maintained. There is currently no macOS CI job; the PyInstaller helper is
cross-platform enough that a `.app`/DMG pipeline mirroring the Windows job is
the intended route if demand appears — see `dev/code_smells.md` §6.
