; dev/_installers/win_installer_script.iss

#define AppName "IBEIS"
#define AppVersion "2.4.1"
#define AppPublisher "IBEIS"
#define AppExeName "IBEIS.exe"
#define AppConsoleExeName "IBEIS-console.exe"

#define IconFile "ibsicon.ico"

; Optional: bundle VC++ runtime if present next to this .iss
#define VCRedistExe "vcredist_x64.exe"
#define HaveVCRedist FileExists(AddBackslash(SourcePath) + VCRedistExe)

; PyInstaller output (relative to dev/_installers/)
#define DistDir "..\..\dist\IBEIS-dist"
#define OutDir  "..\..\dist\installer"

[Setup]
AppId={{47BE3DA2-261D-4672-9849-18BB2EB382FC}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile={#IconFile}

OutputDir={#OutDir}
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes

ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Files]
; Copy the entire PyInstaller output
; Exclude deep JupyterLab assets + source maps (path-length killers)
Source: "{#DistDir}\*"; DestDir: "{app}"; \
  Flags: recursesubdirs createallsubdirs ignoreversion; \
  Excludes: "_internal\share\jupyter\labextensions\*;*.map"

; Install icon for shortcuts
Source: "{#IconFile}"; DestDir: "{app}"; Flags: ignoreversion

#if HaveVCRedist
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
Filename: "{tmp}\{#VCRedistExe}"; \
  Parameters: "/install /quiet /norestart"; \
  StatusMsg: "Installing Microsoft Visual C++ Runtime..."
#endif

