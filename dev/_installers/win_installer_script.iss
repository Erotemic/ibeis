; dev/_installers/win_installer_script.iss

#define AppName "IBEIS"
; AppVersion is normally passed by build_installer.ps1 (read from
; ibeis/__init__.py); this fallback is only for direct ISCC invocations.
#ifndef AppVersion
#define AppVersion "2.4.1"
#endif
#define AppPublisher "IBEIS"
#define AppExeName "IBEIS.exe"
#define AppConsoleExeName "IBEIS-console.exe"

#define DistDir "..\..\dist\IBEIS-dist"
#define IconFile "ibsicon.ico"

; Optional: place vcredist_x64.exe in dev/_installers next to this .iss
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

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; \
  Excludes: "_internal\share\jupyter\*,*.map"
Source: "{#IconFile}"; DestDir: "{app}"; Flags: ignoreversion

#if HaveVCRedist
Source: "{#VCRedistExe}"; DestDir: "{tmp}"; Flags: deleteafterinstall
#endif

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#IconFile}"
Name: "{group}\{#AppName} (Console)"; Filename: "{app}\{#AppConsoleExeName}"; IconFilename: "{app}\{#IconFile}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#IconFile}"

[Run]
#if HaveVCRedist
Filename: "{tmp}\{#VCRedistExe}"; Parameters: "/install /quiet /norestart"; \
  StatusMsg: "Installing Microsoft Visual C++ Runtime..."; Check: VCRedistNeedsInstall; Flags: waituntilterminated
#endif

Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function ReadVcInstalled(const Root: Integer; const SubKey: string; var Installed: Cardinal): Boolean;
begin
  Result := RegQueryDWordValue(Root, SubKey, 'Installed', Installed);
end;

function VCRedistNeedsInstall(): Boolean;
var
  Installed: Cardinal;
begin
  Result := True;

  { Current 64-bit key on modern systems }
  if ReadVcInstalled(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', Installed) then
  begin
    if Installed = 1 then
    begin
      Result := False;
      Exit;
    end;
  end;

  { Fallbacks for differing installer / registry views }
  if ReadVcInstalled(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', Installed) then
  begin
    if Installed = 1 then
    begin
      Result := False;
      Exit;
    end;
  end;

  if ReadVcInstalled(HKLM32, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', Installed) then
  begin
    if Installed = 1 then
    begin
      Result := False;
      Exit;
    end;
  end;
end;
