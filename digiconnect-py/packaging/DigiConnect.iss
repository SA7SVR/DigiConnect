; DigiConnect installer (Inno Setup 6). Expects the app folder in ..\dist\DigiConnect (with engine\ inside).
; Build: ISCC.exe /DAppVer=2.0.2 packaging\DigiConnect.iss   (the version comes from app/version.py in CI)
#ifndef AppVer
  #define AppVer "0.0.0"
#endif
#define AppName "DigiConnect"

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=HELLAS Zone (SA7SVR)
AppPublisherURL=https://hellaszone.com
AppSupportURL=https://hellaszone.com
VersionInfoVersion={#AppVer}.0
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
VersionInfoCompany=HELLAS Zone (SA7SVR)
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName} {#AppVer}
UninstallDisplayIcon={app}\DigiConnect.ico
SetupIconFile=..\assets\DigiConnect.ico
WizardImageFile=installer\wizard.bmp
WizardSmallImageFile=installer\wizard_small.bmp
WizardStyle=modern
DisableWelcomePage=no
OutputDir=..\installer_out
OutputBaseFilename=DigiConnect-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=auto
LanguageDetectionMethod=uilanguage

[Languages]
Name: "el"; MessagesFile: "installer\Greek.isl"; InfoBeforeFile: "installer\info_before_el.txt"; InfoAfterFile: "installer\info_after_el.txt"
Name: "en"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "installer\info_before_en.txt"; InfoAfterFile: "installer\info_after_en.txt"

[CustomMessages]
el.TaskDesktop=Εικονίδιο στην επιφάνεια εργασίας
el.TaskGroup=Συντομεύσεις
el.RunApp=Εκκίνηση του DigiConnect
el.UninstallShortcut=Απεγκατάσταση του DigiConnect
en.TaskDesktop=Desktop icon
en.TaskGroup=Shortcuts
en.RunApp=Start DigiConnect
en.UninstallShortcut=Uninstall DigiConnect

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:TaskGroup}"

[Files]
Source: "..\dist\DigiConnect\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; the icon file itself is installed, so every shortcut shows our logo whatever the exe resource says
Source: "..\assets\DigiConnect.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\DigiConnect.exe"; IconFilename: "{app}\DigiConnect.ico"
Name: "{group}\{cm:UninstallShortcut}"; Filename: "{uninstallexe}"; IconFilename: "{app}\DigiConnect.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\DigiConnect.exe"; IconFilename: "{app}\DigiConnect.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\DigiConnect.exe"; Description: "{cm:RunApp}"; Flags: nowait postinstall skipifsilent
