; Inno Setup 6 script for piewall. Built by packaging/build.ps1:
;   iscc /DAppVersion=0.1.0 /DSourceDir=<dist\onedir\piewall> /O<outdir> packaging\piewall.iss
; Installs per user by default (no UAC); the dialog or /ALLUSERS switches to a machine-wide install.

#ifndef AppVersion
  #error AppVersion is required: iscc /DAppVersion=x.y.z
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\onedir\piewall"
#endif
; Numeric 4-part version for the setup exe's own version resource.
#ifndef FileVersion
  #define FileVersion AppVersion + ".0"
#endif

#define AppName "piewall"
#define AppPublisher "Theeraphat"
#define AppExe "piewall.exe"

[Setup]
; Never change AppId: Windows uses it to find existing installs for upgrades and uninstall.
AppId={{86E8688D-A0E2-4AE4-8F5E-DB295D89E276}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=© 2026 Theeraphat
VersionInfoVersion={#FileVersion}
VersionInfoProductVersion={#FileVersion}
VersionInfoProductTextVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} setup
VersionInfoCopyright=© 2026 Theeraphat
; {autopf} = %LOCALAPPDATA%\Programs per user, C:\Program Files for all users.
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile=..\src\piewall\assets\piewall.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputBaseFilename=piewall-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no
; Signing (see packaging/README.md): uncomment and define a "signtool" in the IDE or with /S on iscc.
; SignTool=signtool
; SignedUninstaller=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add piewall-cli and piewall-mcp to PATH"; GroupDescription: "Command line:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Manage Windows Firewall rules"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  UserEnvKey = 'Environment';
  MachineEnvKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

{ PATH lives in HKCU for per-user installs, HKLM for all-users installs. }
function EnvRoot: Integer;
begin
  if IsAdminInstallMode then Result := HKEY_LOCAL_MACHINE else Result := HKEY_CURRENT_USER;
end;

function EnvKey: String;
begin
  if IsAdminInstallMode then Result := MachineEnvKey else Result := UserEnvKey;
end;

function NormDir(const S: String): String;
begin
  Result := Lowercase(RemoveBackslashUnlessRoot(Trim(S)));
end;

{ Rebuild PATH without Dir. Returns True if Dir was present. }
function StripDir(const Path, Dir: String; var Rest: String): Boolean;
var
  Remaining, Entry: String;
  P: Integer;
begin
  Result := False;
  Rest := '';
  Remaining := Path;
  while Remaining <> '' do
  begin
    P := Pos(';', Remaining);
    if P = 0 then
    begin
      Entry := Remaining;
      Remaining := '';
    end else begin
      Entry := Copy(Remaining, 1, P - 1);
      Remaining := Copy(Remaining, P + 1, Length(Remaining));
    end;
    if NormDir(Entry) = NormDir(Dir) then
      Result := True
    else if Trim(Entry) <> '' then
    begin
      if Rest <> '' then Rest := Rest + ';';
      Rest := Rest + Entry;
    end;
  end;
end;

procedure AddToPath(const Dir: String);
var
  Path, Rest: String;
begin
  if not RegQueryStringValue(EnvRoot, EnvKey, 'Path', Path) then Path := '';
  if StripDir(Path, Dir, Rest) then Exit;  { already there }
  if Rest <> '' then Rest := Rest + ';';
  if not RegWriteExpandStringValue(EnvRoot, EnvKey, 'Path', Rest + Dir) then
    Log('Could not add ' + Dir + ' to PATH');
end;

procedure RemoveFromPath(const Dir: String);
var
  Path, Rest: String;
begin
  if not RegQueryStringValue(EnvRoot, EnvKey, 'Path', Path) then Exit;
  if StripDir(Path, Dir, Rest) then
    if not RegWriteExpandStringValue(EnvRoot, EnvKey, 'Path', Rest) then
      Log('Could not remove ' + Dir + ' from PATH');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('addtopath') then
      AddToPath(ExpandConstant('{app}'))
    else
      RemoveFromPath(ExpandConstant('{app}'));  { task unticked on upgrade }
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromPath(ExpandConstant('{app}'));
end;
