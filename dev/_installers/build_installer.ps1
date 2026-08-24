# dev/_installers/build_installer.ps1
<#
.SYNOPSIS
Build IBEIS with PyInstaller (onedir) and optionally produce an Inno Setup installer.

.DESCRIPTION
Targets:
  - PyInstaller : build dist/IBEIS-dist via spec file
  - Checks      : validate outputs + (optional) smoke test
  - Inno        : build the installer via ISCC.exe

Default behavior (no args):
  - Runs PyInstaller + Inno (no checks)

This script ALWAYS uses uv to create the venv and to install packages.
If uv is missing, it will install it via: python -m pip install -U uv
It prefers the Windows py launcher (py -3.13) when available.

Important:
  - uv's pip interface targets the `.venv` in the current working directory, so this script
    assumes the venv directory name is exactly `.venv` at the repo root.

Packaging note:
  - If the venv is new (or has never had project deps installed), we run:
      <venv-python> -m pip install -e .[headless]
    so the editable project + runtime deps needed for packaging are present.

.PARAMETER Clean
Deletes ./build and ./dist before doing anything else (then recreates dist/diagnostics).

.PARAMETER PyInstaller
Run the PyInstaller build target.

.PARAMETER Checks
Run post-build checks target (requires dist output already exists).

.PARAMETER Inno
Run the Inno Setup target (requires dist output already exists).

.PARAMETER SmokeTest
When used with -Checks, runs IBEIS-console.exe and captures stdout/stderr into dist/diagnostics.
If you pass -SmokeTest without -Checks, -Checks is implied.

.PARAMETER DiagnosticsOnly
Runs environment + python sanity checks only (does not require existing dist output).

.PARAMETER LocalPurePythonTpl
Build and install an explicit allowlist of pure-Python packages from tpl/
before freezing IBEIS. This is intended for integration CI so coordinated
IBEIS / submodule changes can be exercised before those dependencies are
published. Release installers should omit this switch and use PyPI packages.

.PARAMETER ShowUsage
Prints copy/paste usage commands and exits.

.PARAMETER PythonVersion
Python version string used when creating venv via uv (default: 3.13).

.EXAMPLE
# Print usage/copy/paste commands
powershell -ExecutionPolicy Bypass -File .\dev\_installers\build_installer.ps1 -ShowUsage

.EXAMPLE
# Default: PyInstaller + Inno
.\dev\_installers\build_installer.ps1

.EXAMPLE
# Full clean build with checks + smoke test too
.\dev\_installers\build_installer.ps1 -Clean -Checks -SmokeTest -Inno

.EXAMPLE
# Quick environment diagnostics (no build required)
.\dev\_installers\build_installer.ps1 -DiagnosticsOnly
#>

[CmdletBinding()]
param(
    [switch]$Clean,

    # Targets (positive selection)
    [switch]$PyInstaller,
    [switch]$Checks,
    [switch]$Inno,

    # Options
    [switch]$SmokeTest,
    [switch]$DiagnosticsOnly,
    [switch]$LocalPurePythonTpl,
    [switch]$ShowUsage,

    [string]$PythonVersion = "3.13",

    # Keep as a param only so it is visible/obvious, but uv pip effectively requires `.venv`.
    [string]$VenvDir = ".venv"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $true
}

$UsageText = @'
================================================================================
USAGE (copy/paste)
================================================================================

# 0) From repo root, print help + examples
Get-Help .\dev\_installers\build_installer.ps1 -Full
powershell -ExecutionPolicy Bypass -File .\dev\_installers\build_installer.ps1 -ShowUsage

# 1) Default: PyInstaller + Inno (no checks)
.\dev\_installers\build_installer.ps1

# 2) Clean build: PyInstaller + Inno
.\dev\_installers\build_installer.ps1 -Clean

# 3) Build + checks (+ smoke test) + Inno
.\dev\_installers\build_installer.ps1 -Clean -Checks -SmokeTest -Inno

# 3b) Integration build using selected pure-Python tpl/ submodules
.\dev\_installers\build_installer.ps1 -Clean -LocalPurePythonTpl -Checks -SmokeTest -Inno

# 4) Only run PyInstaller
.\dev\_installers\build_installer.ps1 -PyInstaller

# 5) Only run Checks (requires dist already exists)
.\dev\_installers\build_installer.ps1 -Checks -SmokeTest

# 6) Only build Inno installer (requires dist already exists)
.\dev\_installers\build_installer.ps1 -Inno

# 7) Diagnostics only (no build required)
.\dev\_installers\build_installer.ps1 -DiagnosticsOnly

================================================================================
NOTES
================================================================================
- If you specify no targets (-PyInstaller/-Checks/-Inno), the default is PyInstaller + Inno.
- Checks/Inno require an existing dist output (dist\IBEIS-dist). Run -PyInstaller first.
- This script always uses uv. If uv is missing it will install it via python -m pip install -U uv.
- If project deps are not installed into the venv yet, it will run: <venv-python> -m pip install -e .[headless]
- -LocalPurePythonTpl overrides only the explicit pure-Python allowlist from tpl/ after normal dependency installation.
- Diagnostics and logs go in: dist\diagnostics\
================================================================================
'@

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host ("=" * 80)
    Write-Host $Title
    Write-Host ("=" * 80)
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Resolve-RepoRoot {
    $installersDir = (Resolve-Path $PSScriptRoot).Path
    $cand = Join-Path $installersDir "..\.."
    if (Test-Path (Join-Path $cand "dev\_installers")) {
        return (Resolve-Path $cand).Path
    }
    if (Test-Path (Join-Path (Get-Location) "dev\_installers")) {
        return (Resolve-Path (Get-Location)).Path
    }
    throw "Could not resolve repo root. Expected dev/_installers relative to script or cwd."
}

function Assert-VenvDir([string]$VenvDirName) {
    if ($VenvDirName -ne ".venv") {
        throw "This script currently requires VenvDir='.venv' (uv pip targets .venv in the working directory). Got: '$VenvDirName'"
    }
}

function Get-BootstrapPython([string]$PyVer) {
    # Prefer py -3.13, but verify it actually runs; otherwise fall back to python on PATH.
    if (Test-Command "py") {
        try {
            & py ("-" + $PyVer) -c "import sys; print(sys.version)" | Out-Null
            return @{ Exe = "py"; Args = @("-$PyVer") }
        } catch {
            Write-Warning "py -$PyVer not usable: $($_.Exception.Message)"
        }
    }
    if (Test-Command "python") {
        return @{ Exe = "python"; Args = @() }
    }
    throw "No bootstrap python found on PATH (need 'py' or 'python') to install/run uv."
}

function Ensure-Uv([hashtable]$Boot) {
    # If uv is already importable as a module in the bootstrap python, do nothing.
    try {
        & $Boot.Exe @($Boot.Args) -m uv --version | Out-Null
        return
    } catch {
        # continue to install
    }

    Write-Section "Ensure uv (auto-install via pip)"
    try {
        & $Boot.Exe @($Boot.Args) -m pip --version | Out-Null
    } catch {
        Write-Warning "pip not available; trying ensurepip"
        & $Boot.Exe @($Boot.Args) -m ensurepip | Out-Host
    }

    try {
        & $Boot.Exe @($Boot.Args) -m pip install -U uv | Out-Host
    } catch {
        Write-Warning "pip install uv failed; retrying with --user"
        & $Boot.Exe @($Boot.Args) -m pip install -U --user uv | Out-Host
    }

    Write-Section "Verify uv"
    try {
        & $Boot.Exe @($Boot.Args) -m uv --version | Out-Host
    } catch {
        throw "uv module invocation still failing after bootstrap attempt: $($_.Exception.Message)"
    }
}

function New-Venv([string]$RepoRoot, [string]$VenvDirName, [string]$PyVer, [hashtable]$Boot) {
    $venvPath = Join-Path $RepoRoot $VenvDirName
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $false
    }

    Write-Section "Create venv ($VenvDirName) with uv"
    Push-Location $RepoRoot
    try {
        & $Boot.Exe @($Boot.Args) -m uv venv $VenvDirName --python $PyVer --seed | Out-Host
    } finally {
        Pop-Location
    }

    if (-not (Test-Path $venvPython)) {
        throw "uv reported success but venv python not found at $venvPython"
    }

    return $true
}

function Ensure-Venv([string]$RepoRoot, [string]$VenvDirName, [string]$PyVer) {
    Assert-VenvDir -VenvDirName $VenvDirName

    $boot = Get-BootstrapPython -PyVer $PyVer
    Ensure-Uv -Boot $boot

    $created = New-Venv -RepoRoot $RepoRoot -VenvDirName $VenvDirName -PyVer $PyVer -Boot $boot

    $venvPath = Join-Path $RepoRoot $VenvDirName
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Virtual environment python not found at $venvPython"
    }

    # Activation is best-effort; script always uses explicit venv python path anyway.
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        try {
            Write-Section "Activate venv (best-effort)"
            . $activateScript
        } catch {
            Write-Warning "Failed to activate venv (continuing with explicit python path): $($_.Exception.Message)"
        }
    }

    return [pscustomobject]@{
        RepoRoot   = $RepoRoot
        VenvDir    = $VenvDirName
        VenvPath   = $venvPath
        VenvPython = $venvPython
        Boot       = $boot
        Created    = $created
    }
}

function Ensure-ProjectDepsForPackaging($Ctx) {
    # Marker ensures we only do this once per venv, but still covers "venv existed but deps never installed".
    $marker = Join-Path $Ctx.VenvPath ".ibeis_headless_installed"
    if (Test-Path $marker) {
        return
    }

    Write-Section "Install project deps into venv (editable) .[headless]"
    Push-Location $Ctx.RepoRoot
    try {
        & $Ctx.VenvPython -m pip install -U pip setuptools wheel | Out-Host
        & $Ctx.VenvPython -m pip install -e ".[headless]" | Out-Host
        New-Item -ItemType File -Force $marker | Out-Null
    } finally {
        Pop-Location
    }
}

function Install-LocalPurePythonTpl($Ctx, [string]$DiagDir) {
    # Keep this allowlist narrow. Native-extension packages belong to the
    # published dependency path because installer CI needs to prove their
    # Windows wheels can be resolved exactly as an end user would resolve them.
    $packagePaths = [ordered]@{
        "utool" = "tpl/utool"
        "guitool_ibeis" = "tpl/guitool_ibeis"
    }

    Write-Section "Install local pure-Python tpl wheels"
    Write-Host "This is an integration build. Release installers must use PyPI dependencies."

    $wheelhouse = Join-Path $Ctx.RepoRoot "dist\tpl_wheelhouse"
    Remove-Item -Recurse -Force $wheelhouse -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $wheelhouse | Out-Null

    $manifestLines = @(
        "IBEIS local tpl integration packages",
        "repo=$($Ctx.RepoRoot)",
        ""
    )
    $builtWheels = @()

    foreach ($packageName in $packagePaths.Keys) {
        $relpath = $packagePaths[$packageName]
        $srcPath = Join-Path $Ctx.RepoRoot $relpath
        $pyprojectPath = Join-Path $srcPath "pyproject.toml"

        if (-not (Test-Path $pyprojectPath)) {
            if (-not (Test-Command "git")) {
                throw "Local tpl package '$packageName' is not populated at $relpath and git is unavailable"
            }
            Write-Host "Initializing submodule: $relpath"
            Push-Location $Ctx.RepoRoot
            try {
                $treeEntry = (& git ls-tree HEAD -- $relpath)
                $pinnedRevision = if ($treeEntry) { ($treeEntry -split '\s+')[2] } else { "unknown" }
                try {
                    & git submodule update --init -- $relpath | Out-Host
                    if ($LASTEXITCODE -ne 0) {
                        throw "git submodule update exited with code $LASTEXITCODE"
                    }
                } catch {
                    throw (
                        "Unable to initialize local tpl package '$packageName' at $relpath. " +
                        "The parent repository pins submodule commit $pinnedRevision. " +
                        "That commit must be pushed to the submodule's Git remote before CI can build it; " +
                        "a PyPI release is not required. Original error: $($_.Exception.Message)"
                    )
                }
            } finally {
                Pop-Location
            }
        }
        if (-not (Test-Path $pyprojectPath)) {
            throw "Local tpl package '$packageName' is missing $pyprojectPath"
        }

        $revision = "unknown"
        $dirty = "unknown"
        if (Test-Command "git") {
            try {
                $revision = (& git -C $srcPath rev-parse HEAD).Trim()
                $status = (& git -C $srcPath status --porcelain)
                $dirty = if ($status) { "true" } else { "false" }
            } catch {
                Write-Warning "Could not determine git revision for $packageName"
            }
        }

        Write-Host "Building local wheel: $packageName from $relpath @ $revision (dirty=$dirty)"
        $before = @(Get-ChildItem $wheelhouse -Filter "*.whl" -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
        & $Ctx.VenvPython -m pip wheel --no-deps --wheel-dir $wheelhouse $srcPath | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "Wheel build failed for $packageName (exit $LASTEXITCODE)"
        }
        $after = @(Get-ChildItem $wheelhouse -Filter "*.whl" -File)
        $newWheels = @($after | Where-Object { $before -notcontains $_.FullName })
        if ($newWheels.Count -ne 1) {
            throw "Expected exactly one wheel for $packageName, found $($newWheels.Count) new wheels"
        }
        $wheel = $newWheels[0]
        if ($wheel.Name -notmatch '-none-any\.whl$') {
            throw "Refusing non-pure wheel in -LocalPurePythonTpl mode: $($wheel.Name)"
        }
        $builtWheels += $wheel
        $manifestLines += "$packageName`t$revision`tdirty=$dirty`t$($wheel.Name)"
    }

    Write-Host "Installing local tpl wheels over the published dependency set:"
    $builtWheels | ForEach-Object { Write-Host "  $($_.FullName)" }
    $wheelPaths = @($builtWheels | ForEach-Object { $_.FullName })
    & $Ctx.VenvPython -m pip install --force-reinstall --no-deps @wheelPaths | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Installing local tpl wheels failed (exit $LASTEXITCODE)"
    }

    Write-Section "Verify local tpl package origins"
    $verifyCode = @'
import importlib
import importlib.metadata
for name in ['utool', 'guitool_ibeis']:
    mod = importlib.import_module(name)
    print(f'{name}: version={importlib.metadata.version(name)} file={mod.__file__}')
'@
    & $Ctx.VenvPython -c $verifyCode | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Local tpl verification failed (exit $LASTEXITCODE)"
    }

    $manifestPath = Join-Path $DiagDir "local_tpl_packages.txt"
    $manifestLines | Set-Content -Path $manifestPath
    Write-Host "Wrote: $manifestPath"
}

function Install-BuildDeps($Ctx) {
    Write-Section "Install build deps into venv"
    Push-Location $Ctx.RepoRoot
    try {
        & $Ctx.VenvPython -m pip install -U pip setuptools wheel PyInstaller pywin32-ctypes pefile | Out-Host
    } finally {
        Pop-Location
    }

    Write-Section "Python sanity"
    & $Ctx.VenvPython -c "import sys; print('python:', sys.executable); print('version:', sys.version)" | Out-Host

    Write-Section "win32ctypes import test"
    & $Ctx.VenvPython -c "import win32ctypes.pywin32; import win32ctypes.pywin32.win32api, win32ctypes.pywin32.pywintypes; print('win32ctypes OK')" | Out-Host
}

function Invoke-PyInstallerBuild([string]$RepoRoot, [string]$InstallersDir, [string]$VenvPy) {
    Write-Section "PyInstaller build"
    Push-Location $RepoRoot
    try {
        & $VenvPy -m PyInstaller --clean -y (Join-Path $InstallersDir "pyinstaller-ibeis.spec") | Out-Host
    } finally {
        Pop-Location
    }
}

function Assert-DistPresent([string]$AppDir) {
    if (-not (Test-Path $AppDir)) { throw "Missing $AppDir (PyInstaller output not found). Run with -PyInstaller first." }
    if (-not (Test-Path (Join-Path $AppDir "IBEIS.exe"))) { throw "Missing IBEIS.exe in $AppDir" }
    if (-not (Test-Path (Join-Path $AppDir "IBEIS-console.exe"))) { throw "Missing IBEIS-console.exe in $AppDir" }
}

function Invoke-Checks([string]$AppDir, [string]$DiagDir, [switch]$DoSmokeTest) {
    Write-Section "Post-build checks"
    Write-Host "AppDir = $AppDir"
    Assert-DistPresent -AppDir $AppDir

    Write-Host "`nKey files:"
    Get-ChildItem $AppDir -Filter "IBEIS*.exe" | Format-Table Name, Length, LastWriteTime

    $internal = Join-Path $AppDir "_internal"
    Write-Section "Runtime DLL quick scan (dist\_internal)"
    if (Test-Path $internal) {
        Get-ChildItem $internal -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^(vcruntime|msvcp|api-ms-win-crt).*\.dll$' } |
            Sort-Object Name |
            Format-Table Name, Length, LastWriteTime
    } else {
        Write-Warning "No _internal dir found at $internal"
    }

    Write-Section "Frozen selftest (source introspection)"
    $SelftestLog = Join-Path $DiagDir "frozen_selftest.txt"
    $env:IBEIS_FROZEN_SELFTEST = "1"
    try {
        & (Join-Path $AppDir "IBEIS-console.exe") 2>&1 | Tee-Object -FilePath $SelftestLog
        if ($LASTEXITCODE -ne 0) {
            throw "Frozen console selftest FAILED (exit $LASTEXITCODE). See $SelftestLog"
        }

        Write-Section "Frozen selftest (windowed startup)"
        $GuiExe = Join-Path $AppDir "IBEIS.exe"
        $GuiProc = Start-Process -FilePath $GuiExe -WorkingDirectory $AppDir -PassThru
        if (-not $GuiProc.WaitForExit(20000)) {
            Stop-Process -Id $GuiProc.Id -Force -ErrorAction SilentlyContinue
            throw "Frozen windowed selftest timed out after 20 seconds"
        }
        $GuiProc.Refresh()
        if ($GuiProc.ExitCode -ne 0) {
            throw "Frozen windowed selftest FAILED (exit $($GuiProc.ExitCode))"
        }
    } finally {
        Remove-Item Env:IBEIS_FROZEN_SELFTEST -ErrorAction SilentlyContinue
    }

    if ($DoSmokeTest) {
        Write-Section "Smoke test (IBEIS-console.exe)"
        $SmokeOut = Join-Path $DiagDir "smoke_test_stdout.txt"
        $SmokeErr = Join-Path $DiagDir "smoke_test_stderr.txt"
        $SmokeMerged = Join-Path $DiagDir "smoke_test.txt"
        $exe = Join-Path $AppDir "IBEIS-console.exe"

        try {
            $p = Start-Process -FilePath $exe -WorkingDirectory $AppDir -NoNewWindow -PassThru `
                -RedirectStandardOutput $SmokeOut -RedirectStandardError $SmokeErr
            Wait-Process -Id $p.Id -Timeout 20 -ErrorAction SilentlyContinue | Out-Null
            if (-not $p.HasExited) {
                Write-Warning "Smoke test timed out; stopping process."
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
            Write-Warning "Smoke test failed to start: $($_.Exception.Message)"
        }

        $parts = @()
        if (Test-Path $SmokeOut) {
            $parts += "===== STDOUT ====="
            $parts += (Get-Content $SmokeOut)
        }
        if (Test-Path $SmokeErr) {
            $parts += "===== STDERR ====="
            $parts += (Get-Content $SmokeErr)
        }
        if ($parts.Count -gt 0) {
            $parts | Set-Content -Path $SmokeMerged
            Write-Host "Wrote: $SmokeMerged"
        } else {
            Write-Warning "Smoke test produced no output files."
        }
    }
}

function Find-Iscc {
    # Machine-scope installs (winget default, and GitHub Actions runner images)
    $candidatePaths = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ -and $_.Trim() -ne "" }

    foreach ($candidate in $candidatePaths) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $pathHit = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($pathHit -and $pathHit.Source -and (Test-Path $pathHit.Source)) {
        return $pathHit.Source
    }
    return $null
}

function Ensure-InnoSetup {
    Write-Section "Ensure Inno Setup"

    $iscc = Find-Iscc
    if ($iscc) {
        Write-Host "Found ISCC.exe: $iscc"
        return $iscc
    }

    if (Test-Command "winget") {
        try {
            winget install --id JRSoftware.InnoSetup --source winget --accept-source-agreements --accept-package-agreements | Out-Host
        } catch {
            Write-Warning "winget install Inno Setup failed (may already be installed). Continuing."
        }
    } else {
        Write-Warning "winget not found; skipping auto-install attempt."
    }

    $iscc = Find-Iscc
    if (-not $iscc) {
        throw "Could not find ISCC.exe in PATH or common install locations (Program Files, Program Files (x86), LOCALAPPDATA\Programs)."
    }
    return $iscc
}

function Get-IbeisVersion([string]$RepoRoot) {
    $initPath = Join-Path $RepoRoot "ibeis\__init__.py"
    $match = Select-String -Path $initPath -Pattern "^__version__\s*=\s*'([^']+)'" | Select-Object -First 1
    if (-not $match) {
        throw "Could not parse __version__ from $initPath"
    }
    return $match.Matches[0].Groups[1].Value
}

function Invoke-InnoBuild([string]$RepoRoot, [string]$InstallersDir, [string]$AppDir) {
    Write-Section "Inno Setup build"
    Assert-DistPresent -AppDir $AppDir

    $iscc = Ensure-InnoSetup
    Write-Host "Using ISCC.exe at: $iscc"

    $version = Get-IbeisVersion -RepoRoot $RepoRoot
    Write-Host "AppVersion = $version (from ibeis/__init__.py)"

    Push-Location $RepoRoot
    try {
        & $iscc "/DAppVersion=$version" (Join-Path $InstallersDir "win_installer_script.iss") | Out-Host
    } finally {
        Pop-Location
    }
}

# ------------------------------
# Entry
# ------------------------------
if ($ShowUsage) {
    Write-Host $UsageText
    return
}

$RepoRoot = Resolve-RepoRoot
$InstallersDir = Join-Path $RepoRoot "dev\_installers"
$DistDir = Join-Path $RepoRoot "dist"
$DiagDir = Join-Path $DistDir "diagnostics"

# If -SmokeTest was specified, imply -Checks (unless DiagnosticsOnly)
if ($SmokeTest -and -not $DiagnosticsOnly -and -not $Checks) {
    $Checks = $true
}

# Targets: if user didn't select any, default is PyInstaller + Inno
$anyTargetSpecified = $PyInstaller -or $Checks -or $Inno -or $DiagnosticsOnly
if (-not $anyTargetSpecified) {
    $PyInstaller = $true
    $Inno = $true
}

# Clean (do this before transcript so we don't delete our own transcript)
if ($Clean) {
    Write-Section "Clean build/dist"
    Remove-Item -Recurse -Force (Join-Path $RepoRoot "build"), (Join-Path $RepoRoot "dist") -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force $DiagDir | Out-Null
$Transcript = Join-Path $DiagDir "build_transcript.txt"
Start-Transcript -Path $Transcript -Force | Out-Null

try {
    Write-Section "Environment"
    Write-Host "RepoRoot      = $RepoRoot"
    Write-Host "InstallersDir = $InstallersDir"
    Write-Host "DistDir       = $DistDir"
    Write-Host "DiagDir       = $DiagDir"
    Write-Host "PSVersion     = $($PSVersionTable.PSVersion)"
    Write-Host ("Targets       = PyInstaller={0}, Checks={1}, Inno={2}, DiagnosticsOnly={3}" -f $PyInstaller,$Checks,$Inno,$DiagnosticsOnly)
    Write-Host "LocalTpl      = $LocalPurePythonTpl"

    # venv/uv only needed for DiagnosticsOnly or PyInstaller builds
    if ($DiagnosticsOnly) {
        Write-Section "DiagnosticsOnly"
        $Ctx = Ensure-Venv -RepoRoot $RepoRoot -VenvDirName $VenvDir -PyVer $PythonVersion
        Write-Host ("VenvCreated   = {0}" -f $Ctx.Created)
        Install-BuildDeps -Ctx $Ctx

        Write-Host "`nTranscript: $Transcript"
        Write-Host "Diagnostics:"
        Get-ChildItem $DiagDir | Format-Table Name, Length, LastWriteTime
        return
    }

    $AppDir = Join-Path $DistDir "IBEIS-dist"

    if ($PyInstaller) {
        $Ctx = Ensure-Venv -RepoRoot $RepoRoot -VenvDirName $VenvDir -PyVer $PythonVersion
        Write-Host ("VenvCreated   = {0}" -f $Ctx.Created)

        # Install the ordinary PyPI-backed project dependency set first.
        Ensure-ProjectDepsForPackaging -Ctx $Ctx

        # Integration CI then replaces only the selected pure-Python packages
        # with wheels built from the exact tpl/ revisions in this checkout.
        if ($LocalPurePythonTpl) {
            Install-LocalPurePythonTpl -Ctx $Ctx -DiagDir $DiagDir
        }

        # Ensure build tooling deps (PyInstaller, etc.)
        Install-BuildDeps -Ctx $Ctx

        Invoke-PyInstallerBuild -RepoRoot $RepoRoot -InstallersDir $InstallersDir -VenvPy $Ctx.VenvPython
    }

    if ($Checks) {
        Invoke-Checks -AppDir $AppDir -DiagDir $DiagDir -DoSmokeTest:$SmokeTest
    }

    if ($Inno) {
        Invoke-InnoBuild -RepoRoot $RepoRoot -InstallersDir $InstallersDir -AppDir $AppDir
    }

    Write-Section "Done"
    Write-Host "Transcript: $Transcript"
    Write-Host "Diagnostics:"
    Get-ChildItem $DiagDir | Format-Table Name, Length, LastWriteTime
}
finally {
    Stop-Transcript | Out-Null
}

