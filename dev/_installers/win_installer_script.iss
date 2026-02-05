; dev/_installers/win_installer_script.iss

#define AppName "IBEIS"
#define AppVersion "2.4.1"
#define AppPublisher "IBEIS"
#define AppExeName "IBEIS.exe"
#define AppConsoleExeName "IBEIS-console.exe"

#define IconFile "ibsicon.ico"

; Optional: if you drop vcredist_x64.exe next to this .iss, it will be bundled
#define VCRedistExe "vcredist_x64.exe"
#define HaveVCRedist FileExists(AddBackslash(SourcePath) + VCRedistExe)

; IMPORTANT:
; Use a SHORT (8.3) absolute path for the PyInstaller dist folder to reduce path length issues
#define DistDir GetShortName(SourcePath + "..\..\dist\IBEIS-dist")
#define OutDir  (SourcePath + "..\..\dist\installer")

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
; Copy everything PyInstaller produced
; Exclude JupyterLab labextensions (very deep paths + not needed for the desktop app)
; Also exclude source maps to reduce size
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; \
    Excludes: "_internal\share\jupyter\labextensions\*;*.map"

; Put the icon in the install directory for shortcuts
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
Filename: "{tmp}\{#VCRedistExe}"; Parameters: "/install /quiet /norestart"; \
  StatusMsg: "Installing Microsoft Visual C++ Runtime..."; Check: VCRedistNeedsInstall
#endif

Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function VCRedistNeedsInstall(): Boolean;
var
  Installed: Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKLM,
     'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
     'Installed', Installed) then
  begin
    Result := (Installed = 0);
  end;
end;

