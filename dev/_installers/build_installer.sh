#cd ~/code/ibeis
python -m pip install -U PyInstaller
python -m PyInstaller -y dev/_installers/pyinstaller-ibeis.spec

Remove-Item -Recurse -Force .\build, .\dist -ErrorAction SilentlyContinue

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
python -m pip install -U pywin32-ctypes
python -m PyInstaller --clean -y dev/_installers/pyinstaller-ibeis.spec

python -m pip install -U pywin32-ctypes
python -c "import win32ctypes.pywin32; import win32ctypes.pywin32.win32api, win32ctypes.pywin32.pywintypes; print('win32ctypes OK')"


# Test
.\dist\IBEIS-dist\IBEIS-console.exe


# Need INNO on windows
winget search innosetup

Set-Alias iscc
iscc "dev\_installers\ibeis.iss"

#"$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" "dev\_installers\win_installer_script.iss"
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" ".\dev\_installers\win_installer_script.iss"


# Debugging
winget search Dependencies
#
winget install --id JacquelinPotier.AllDllsDependencies --source winget --accept-source-agreements --accept-package-agreements
AllDllDeps64.exe


#
