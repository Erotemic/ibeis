; dev/_installers/win_installer_script.iss

#define AppName "IBEIS"
#define AppVersion "2.4.1"
#define AppPublisher "IBEIS"
#define AppExeName "IBEIS.exe"
#define AppConsoleExeName "IBEIS-console.exe"

; PyInstaller output folder (relative to this .iss file in dev/_installers/)
#define DistDir "..\..\dist\IBEIS-dist"

; Icon that already exists in dev/_installers/
#define IconFile "ibsicon.ico"

; Optional: if you place vcredist_x64.exe next to this .iss, it will be bundled
#define VCRedistExe "vcredist_x64.exe"
#define HaveVCRedist FileExists(AddBackslash(SourcePath) + VCRedistExe)

[Setup]
AppId={{47BE3DA2-261D-4672-9849-18BB2EB382FC}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile={#IconFile}

OutputDir=..\..\dist\installer
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes

ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Files]
; Copy everything PyInstaller produced (EXEs + _internal + DLLs + data files)
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

; Copy icon into install dir (so shortcuts can reference it)
Source: "{#IconFile}"; DestDir: "{app}"; Flags: ignoreversion

#if HaveVCRedist
; Bundle VC++ redist only if the file exists next to the .iss
Source: "{#VCRedistExe}"; DestDir: "{tmp}"; Flags: deleteafterinstall
#endif

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#IconFile}"
Name: "{group}\{#AppName} (Console)"; Filename: "{app}\{#AppConsoleExeName}"; IconFilename: "{app}\{#IconFile}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#IconFile}"

[Run]
#if HaveVCRedist
Filename: "{tmp}\{#VCRedistExe}"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ Runtime..."
#endif

Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

