Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

$DistRoot = Join-Path $RepoRoot "dist"
$DiagDir = Join-Path $DistRoot "diagnostics"
New-Item -ItemType Directory -Path $DiagDir -Force | Out-Null

$TranscriptPath = Join-Path $DiagDir "build_transcript.txt"
Start-Transcript -Path $TranscriptPath -Force

try {
    $VenvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPy)) {
        throw "Venv python not found at $VenvPy"
    }

    & $VenvPy -m pip install --upgrade pip
    & $VenvPy -m pip install --upgrade pyinstaller==6.18.0 pywin32-ctypes pefile

    & $VenvPy -m PyInstaller --noconfirm --clean "dev/_installers/pyinstaller-ibeis.spec"

    $AppDir = Join-Path $RepoRoot "dist\IBEIS-dist"
    $InternalDir = Join-Path $AppDir "_internal"
    if (-not (Test-Path $AppDir)) {
        throw "PyInstaller output not found: ${AppDir}"
    }

    $runtimePatterns = @('msvcp140*.dll', 'vcruntime140*.dll', 'concrt140.dll', 'vcomp140.dll')
    $runtimeRows = @()
    foreach ($pattern in $runtimePatterns) {
        $hits = @(Get-ChildItem -Path $InternalDir -Filter $pattern -ErrorAction SilentlyContinue)
        foreach ($hit in $hits) {
            $runtimeRows += $hit.FullName
        }
    }
    $runtimeRows | Sort-Object -Unique | Set-Content -Path (Join-Path $DiagDir "vc_runtime_in_internal.txt")

    $hesaffDll = Join-Path $InternalDir "pyhesaff\hesaff.dll"
    if (Test-Path $hesaffDll) {
        $searchDirs = @(
            $InternalDir,
            (Join-Path $InternalDir "pyhesaff"),
            (Join-Path $InternalDir "cv2"),
            "C:\Windows\System32",
            "C:\Windows\SysWOW64"
        )
        $cmd = @($VenvPy, "dev/_installers/all_deps.py", $hesaffDll) + $searchDirs
        & $cmd[0] $cmd[1] $cmd[2] $cmd[3] $cmd[4] $cmd[5] $cmd[6] | Set-Content -Path (Join-Path $DiagDir "deps_hesaff.txt")
    }

    $ucrtCheck = Join-Path $DiagDir "ucrt_presence.txt"
    $ucrtRows = @()
    $sys32 = "C:\Windows\System32"
    if (Test-Path (Join-Path $sys32 "ucrtbase.dll")) { $ucrtRows += "FOUND ucrtbase.dll" } else { $ucrtRows += "MISSING ucrtbase.dll" }
    $apiSetHits = @(Get-ChildItem -Path $sys32 -Filter "api-ms-win-crt-*.dll" -ErrorAction SilentlyContinue)
    $ucrtRows += "api-ms-win-crt count: $($apiSetHits.Count)"
    $ucrtRows += ($apiSetHits | Select-Object -ExpandProperty Name)
    $ucrtRows | Set-Content -Path $ucrtCheck

    if ($env:IBEIS_SMOKE_TEST -eq '1') {
        $env:IBEIS_DLL_DEBUG = '1'
        & (Join-Path $AppDir "IBEIS-console.exe") --help
    }
}
finally {
    Stop-Transcript
}
