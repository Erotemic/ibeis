#cd ~/code/ibeis
python -m pip install -U PyInstaller
python -m PyInstaller -y dev/_installers/pyinstaller-ibeis.spec

# Need INNO on windows
winget search innosetup

Set-Alias iscc
iscc "dev\_installers\ibeis.iss"

#"$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" "dev\_installers\win_installer_script.iss"
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" ".\dev\_installers\win_installer_script.iss"

