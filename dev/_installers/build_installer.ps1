# Minimal build notes for IBEIS (PyInstaller + Inno Setup)
# - Has a Debug-Notes function so nothing “runs” when you open the file.

function Debug-Notes {
@'

-Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
-.\.venv\Scripts\Activate.ps1

# Debugging / notes (manual)
# winget search Dependencies
# winget install --id JacquelinPotier.AllDllsDependencies --source winget --accept-source-agreements --accept-package-agreements
# AllDllDeps64.exe  (open hesaff.dll)

# CLI deps checker (your script)
python .\dev\_installers\all_deps.py `
  .\dist\IBEIS-dist\_internal\pyhesaff\hesaff.dll `
  .\dist\IBEIS-dist `
  .\dist\IBEIS-dist\_internal `
  .\dist\IBEIS-dist\_internal\numpy.libs `
  .\dist\IBEIS-dist\_internal\scipy.libs `
  .\dist\IBEIS-dist\_internal\cv2
'@
}

Remove-Item -Recurse -Force .\build, .\dist -ErrorAction SilentlyContinue

# Setup
python -m pip install -U PyInstaller pywin32-ctypes
python -c "import win32ctypes.pywin32; import win32ctypes.pywin32.win32api, win32ctypes.pywin32.pywintypes; print('win32ctypes OK')"

# Make standalone distribution
python -m PyInstaller --clean -y dev/_installers/pyinstaller-ibeis.spec

# Test if you want
#.\dist\IBEIS-dist\IBEIS-console.exe


# Make installer
winget install --id JRSoftware.InnoSetup --source winget --accept-source-agreements --accept-package-agreements
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" ".\dev\_installers\win_installer_script.iss"

