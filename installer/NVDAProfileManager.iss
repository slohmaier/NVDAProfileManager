; NVDA Profile Manager - Inno Setup Script
;
; Built by `scons installer`, which first signs the payload exe with the Certum
; SimplySign cloud certificate (via sign-products.ps1), compiles this script, then
; signs the produced Setup.exe. Version is passed in with ISCC /DMyAppVersion=X.Y.Z.
;
; No Certum material (seed, cert, ssign) ever lives in this repository. The
; signing step only references the shared script in the ownCloud secrets share.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName       "NVDA Profile Manager"
#define MyAppShortName  "NVDAProfileManager"
#define MyAppPublisher  "Stefan Lohmaier"
#define MyAppURL        "https://github.com/slohmaier/NVDAProfileManager"
#define MyAppExeName    "NVDAProfileManager.exe"
#define MyAppId         "{{8B2E5D41-7C3A-4E9F-B6A2-1D4F0C7A9E52}}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright=Copyright (C) 2025-2026 Stefan Lohmaier

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
AllowNoIcons=yes
PrivilegesRequired=admin

Compression=lzma2
SolidCompression=yes
OutputDir=output
OutputBaseFilename={#MyAppShortName}-Setup-{#MyAppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
WizardStyle=modern

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md";           DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";                        Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}";  Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";                  Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM {#MyAppExeName} 2>nul"; Flags: runhidden; RunOnceId: "KillApp"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  { Close a running instance so its files aren't locked during install. }
  Exec(ExpandConstant('{cmd}'), '/C taskkill /F /IM {#MyAppExeName} 2>nul', '',
       SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
