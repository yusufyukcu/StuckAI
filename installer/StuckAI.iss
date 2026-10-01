; Inno Setup script for StuckAI
; Adjust paths if your executable name or layout differs.

[Setup]
AppId={{5D3E2A7F-9B83-4C5C-9D2A-8E1C9F4B7A2D}}
AppName=StuckAI
AppVersion=1.0.0
AppPublisher=StuckAI
DefaultDirName={autopf}\StuckAI
DefaultGroupName=StuckAI
AllowNoIcons=yes
DisableDirPage=no
DisableProgramGroupPage=no
OutputDir=..\dist\installer
OutputBaseFilename=StuckAI-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\StuckAI.exe
SetupIconFile=..\dist\app.dist\ui\assets\app.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
; Copy build output into {app} (flat)
Source: "..\\dist\\app.dist\\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion



[Dirs]
Name: "{app}\\data"; Permissions: users-modify
Name: "{app}\\data\\cache"; Permissions: users-modify
Name: "{app}\\data\\cache\\integrity"; Permissions: users-modify
Name: "{app}\\downloads"; Permissions: users-modify
Name: "{app}\\history"; Permissions: users-modify

[Icons]
; Start Menu shortcut
Name: "{group}\\StuckAI"; Filename: "{app}\\StuckAI.exe"; IconFilename: "{app}\\ui\\assets\\app.ico"; WorkingDir: "{app}"
; Desktop shortcut (pre-selected via task)
Name: "{commondesktop}\\StuckAI"; Filename: "{app}\\StuckAI.exe"; Tasks: desktopicon; IconFilename: "{app}\\ui\\assets\\app.ico"; WorkingDir: "{app}"

[Run]
; Offer to run the app after install
Filename: "{app}\\StuckAI.exe"; Description: "Run StuckAI"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"  
