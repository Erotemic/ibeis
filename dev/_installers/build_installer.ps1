# dev/_installers/build_installer.ps1
# Minimal build notes for IBEIS (PyInstaller + Inno Setup) + embedded diagnostics.
# Run from repo root:
#   powershell -ExecutionPolicy Bypass -File .\dev\_installers\build_installer.ps1 -SmokeTest

[CmdletBinding()]
param(
    [switch]$NoClean,
    [switch]$SkipPyInstaller,
    [switch]$SkipInno,
    [switch]$SmokeTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host ("=" * 80)
    Write-Host $Title
    Write-Host ("=" * 80)
}

function Resolve-RepoRoot {
    # If this script lives in dev/_installers, repo root is two levels up.
    $installersDir = (Resolve-Path $PSScriptRoot).Path
    $cand = Join-Path $installersDir "..\.."
    if (Test-Path (Join-Path $cand "dev\_installers")) {
        return (Resolve-Path $cand).Path
    }

    # If this script is moved somewhere else, try current working directory.
    if (Test-Path (Join-Path (Get-Location) "dev\_installers")) {
        return (Resolve-Path (Get-Location)).Path
    }

    throw "Could not resolve repo root. Expected dev/_installers relative to script or cwd."
}

$RepoRoot = Resolve-RepoRoot
$InstallersDir = Join-Path $RepoRoot "dev\_installers"
$DistDir = Join-Path $RepoRoot "dist"
$DiagDir = Join-Path $DistDir "diagnostics"
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

    $VenvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPy)) {
        Write-Section "Create venv (.venv)"
        # Use whatever python is on PATH to create venv.
        python -m venv (Join-Path $RepoRoot ".venv")
    }

    Write-Section "Python / pip sanity"
    & $VenvPy -c "import sys; print('python:', sys.executable); print('version:', sys.version)"
    & $VenvPy -m pip --version
    & $VenvPy -m pip install -U pip setuptools wheel | Out-Host

    # Tools needed for build + diagnostics
    & $VenvPy -m pip install -U PyInstaller pywin32-ctypes pefile | Out-Host

    # Sanity check that win32ctypes works in the venv
    & $VenvPy -c "import win32ctypes.pywin32; import win32ctypes.pywin32.win32api, win32ctypes.pywin32.pywintypes; print('win32ctypes OK')" | Out-Host

    #if (-not $NoClean) {
    #    Write-Section "Clean build/dist"
    #    Remove-Item -Recurse -Force (Join-Path $RepoRoot "build"), (Join-Path $RepoRoot "dist") -ErrorAction SilentlyContinue
    #    New-Item -ItemType Directory -Force $DistDir | Out-Null
    #    New-Item -ItemType Directory -Force $DiagDir | Out-Null
    #}

    if (-not $SkipPyInstaller) {
        #Write-Section "PyInstaller build"
        #Push-Location $RepoRoot
        #try {
        #    & $VenvPy -m PyInstaller --clean -y (Join-Path $InstallersDir "pyinstaller-ibeis.spec") | Out-Host
        #} finally {
        #    Pop-Location
        #}

        Write-Section "Post-build checks"
        $AppDir = Join-Path $DistDir "IBEIS-dist"
        $InternalDir = Join-Path $AppDir "_internal"
        $PyhesaffDir = Join-Path $InternalDir "pyhesaff"

        Write-Host "AppDir      = $AppDir"
        Write-Host "InternalDir = $InternalDir"
        Write-Host "PyhesaffDir = $PyhesaffDir"

        if (-not (Test-Path $AppDir)) { throw "Missing $AppDir (PyInstaller output not found)" }
        if (-not (Test-Path (Join-Path $AppDir "IBEIS-console.exe"))) { throw "Missing IBEIS-console.exe in $AppDir" }

        Write-Host "`nKey files:"
        Get-ChildItem $AppDir -Filter "IBEIS*.exe" | Format-Table Name, Length, LastWriteTime

        if (-not (Test-Path (Join-Path $PyhesaffDir "hesaff.dll"))) {
            throw "Missing hesaff.dll in $PyhesaffDir"
        }

        Write-Host "`npyhesaff payload:"
        Get-ChildItem $PyhesaffDir | Sort-Object Name | Format-Table Name, Length

        # VC runtime presence in dist (critical for customer machines)
        Write-Host "`nVC runtime DLLs in dist (_internal):"
        $vc = @(Get-ChildItem $InternalDir -Filter "msvcp140*.dll" -ErrorAction SilentlyContinue)

        if ($vc.Count -eq 0) {
            Write-Warning "No msvcp140*.dll found in $InternalDir."

            # Extra diagnostic: did they land somewhere else?
            $vc_any = @(Get-ChildItem $AppDir -Recurse -Filter "msvcp140*.dll" -ErrorAction SilentlyContinue)
            if ($vc_any.Count -eq 0) {
                Write-Warning "No msvcp140*.dll found anywhere under $AppDir."
            } else {
                Write-Warning "Found msvcp140*.dll elsewhere under $AppDir:"
                $vc_any | Select-Object FullName, Length | Format-Table -AutoSize
            }
        } else {
            $vc | Select-Object FullName, Length | Format-Table -AutoSize
        }



        # Run your CLI deps checker and save output
        Write-Section "Dependency scan (all_deps.py) -> deps_hesaff.txt"
        $DepsOut = Join-Path $DiagDir "deps_hesaff.txt"
        $AllDeps = Join-Path $InstallersDir "all_deps.py"
        if (Test-Path $AllDeps) {
            & $VenvPy $AllDeps `
                (Join-Path $PyhesaffDir "hesaff.dll") `
                $AppDir `
                $InternalDir `
                (Join-Path $InternalDir "numpy.libs") `
                (Join-Path $InternalDir "scipy.libs") `
                (Join-Path $InternalDir "cv2") `
                2>&1 | Tee-Object -FilePath $DepsOut | Out-Host
            Write-Host "Wrote: $DepsOut"
        } else {
            Write-Warning "Missing all_deps.py at $AllDeps (skipping dependency scan)"
        }

        if ($SmokeTest) {
            Write-Section "Smoke test (IBEIS-console.exe with IBEIS_DLL_DEBUG=1) -> smoke_test.txt"
            $SmokeOut = Join-Path $DiagDir "smoke_test.txt"
            $exe = Join-Path $AppDir "IBEIS-console.exe"

            $env:IBEIS_DLL_DEBUG = "1"

            # Run briefly then stop (prevents hanging on GUI loop)
            $p = Start-Process -FilePath $exe -WorkingDirectory $AppDir -NoNewWindow -PassThru `
                -RedirectStandardOutput $SmokeOut -RedirectStandardError $SmokeOut

            try {
                Wait-Process -Id $p.Id -Timeout 20 -ErrorAction SilentlyContinue | Out-Null
                if (-not $p.HasExited) {
                    Write-Warning "Smoke test timed out; stopping process."
                    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
                }
            } finally {
                Remove-Item Env:\IBEIS_DLL_DEBUG -ErrorAction SilentlyContinue
            }

            Write-Host "Wrote: $SmokeOut"
        }
    }

    if (-not $SkipInno) {
        Write-Section "Inno Setup install + build installer"

        # Install Inno Setup if needed
        try {
            winget install --id JRSoftware.InnoSetup --source winget --accept-source-agreements --accept-package-agreements | Out-Host
        } catch {
            Write-Warning "winget install Inno Setup failed (may already be installed). Continuing."
        }

        $iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
        if (-not (Test-Path $iscc)) {
            throw "Could not find ISCC.exe at expected path: $iscc"
        }

        Push-Location $RepoRoot
        try {
            & $iscc (Join-Path $InstallersDir "win_installer_script.iss") | Out-Host
        } finally {
            Pop-Location
        }
    }

    Write-Section "Done"
    Write-Host "Transcript: $Transcript"
    Write-Host "Diagnostics:"
    Get-ChildItem $DiagDir | Format-Table Name, Length, LastWriteTime
}
finally {
    Stop-Transcript | Out-Null
}

function Debug-Notes {
@'

# TO RUN:

powershell -ExecutionPolicy Bypass -File .\dev\_installers\build_installer.ps1 -SmokeTest


# Notes / manual debug commands

# If you need activation:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\.venv\Scripts\Activate.ps1

# CLI deps checker:
# python .\dev\_installers\all_deps.py `
#   .\dist\IBEIS-dist\_internal\pyhesaff\hesaff.dll `
#   .\dist\IBEIS-dist `
#   .\dist\IBEIS-dist\_internal `
#   .\dist\IBEIS-dist\_internal\numpy.libs `
#   .\dist\IBEIS-dist\_internal\scipy.libs `
#   .\dist\IBEIS-dist\_internal\cv2
'@
}

