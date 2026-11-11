; DigiConnect - Windows installer script (Inno Setup 6)
; Packages the deployed dist\ folder (DigiConnect.exe + Qt runtime) into a
; single DigiConnect-Setup.exe that installs the app, creates shortcuts and
; registers an uninstaller.

#define MyAppName "DigiConnect"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "HELLAS Zone - SA7SVR"
#define MyAppURL "https://hellaszone.com"
#define MyAppExeName "DigiConnect.exe"

[Setup]
AppId={{9F1D7C2A-4B3E-4E8A-9C21-DIGICONNECT01}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\DigiConnect
DefaultGroupName=DigiConnect
DisableProgramGroupPage=yes
OutputDir=installer_out
OutputBaseFilename=DigiConnect-Setup
SetupIconFile=images\droidstar.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\DigiConnect"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall DigiConnect"; Filename: "{uninstallexe}"
Name: "{autodesktop}\DigiConnect"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,DigiConnect}"; Flags: nowait postinstall skipifsilent
