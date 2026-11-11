; Inno Setup script — expects the app folder in ..\dist\DigiConnect (with engine\ inside)
[Setup]
AppName=DigiConnect
AppVersion=2.0.0
SetupIconFile=..\assets\DigiConnect.ico
UninstallDisplayIcon={app}\DigiConnect.exe
AppPublisher=HELLAS Zone (SA7SVR)
DefaultDirName={autopf}\DigiConnect
DefaultGroupName=DigiConnect
OutputDir=..\installer_out
OutputBaseFilename=DigiConnect-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\dist\DigiConnect\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{group}\DigiConnect"; Filename: "{app}\DigiConnect.exe"
Name: "{autodesktop}\DigiConnect"; Filename: "{app}\DigiConnect.exe"
[Run]
Filename: "{app}\DigiConnect.exe"; Description: "Start DigiConnect"; Flags: nowait postinstall skipifsilent
