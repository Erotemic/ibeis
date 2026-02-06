#define MyAppName "IBEIS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "IBEIS"
#define MyAppExeName "IBEIS.exe"
#define MyConsoleExeName "IBEIS-console.exe"

[Setup]
AppId={{47BE3DA2-261D-4672-9849-18BB2EB382FC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
OutputBaseFilename=ibeis-windows-setup
SetupIconFile=ibsicon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\IBEIS-dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Optional: place vcredist_x64.exe beside this .iss in dev/_installers
Source: "vcredist_x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist

[Icons]
Name: "{group}\IBEIS"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\IBEIS Console"; Filename: "{app}\{#MyConsoleExeName}"
Name: "{autodesktop}\IBEIS"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\vcredist_x64.exe"; Parameters: "/install /quiet /norestart"; Flags: runhidden waituntilterminated; Check: NeedsVCRedist
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
function NeedsVCRedist(): Boolean;
var
  Installed: Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
  begin
    Result := (Installed <> 1);
  end;
end;
