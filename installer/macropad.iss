; Installer for the Macro Pad app (Inno Setup 6).
; Build:  ISCC.exe /DMyAppVersion=1.1.0 installer\macropad.iss   (after PyInstaller)
;
; - Language: English first (German can be picked in the first dialog)
; - Asks where to install and whether to make a desktop shortcut
; - "Only for me" needs no admin rights; "for all users" (Program Files) asks Windows for them
; - The app's own updates run this installer silently with /RELAUNCH=1

#define MyAppName "Macro Pad"
#define MyAppExe "MacroPad.exe"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif

[Setup]
AppId={{8D0E7C61-3F7A-4C35-9B7E-6A1E2B5C9F11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Gengodih
DefaultDirName={autopf}\Macro Pad
DefaultGroupName=Macro Pad
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
OutputDir=..\dist
OutputBaseFilename=MacroPad-Setup-{#MyAppVersion}
SetupIconFile=..\app\macropad_app\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=yes
LanguageDetectionMethod=none
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\MacroPad\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; files of the previous version that are no longer part of the app
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Macro Pad"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\Macro Pad"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; the app reads this once, on its first start, to pick its language
Root: HKCU; Subkey: "Software\MacroPad"; ValueType: string; ValueName: "Language"; ValueData: "{language}"; Flags: uninsdeletekey
; remove the app's autostart entry when it is uninstalled (the app itself creates it)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "MacroPad"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,Macro Pad}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#MyAppExe}"; Flags: nowait; Check: IsRelaunch

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM {#MyAppExe} /F"; Flags: runhidden; RunOnceId: "StopApp"

[Code]
function IsRelaunch: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;
