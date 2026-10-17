[Setup]
AppId={{6C479E2C-7C41-48B9-84B3-F26814F15727}
AppName=Assistente IA
AppVersion=0.2.0
DefaultDirName={localappdata}\Programs\AssistenteIA
DefaultGroupName=Assistente IA
PrivilegesRequired=lowest
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
OutputDir=..\dist-installer
OutputBaseFilename=AssistenteIA-Setup
UninstallDisplayIcon={app}\AssistenteIA.exe

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\AssistenteIA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Assistente IA"; Filename: "{app}\AssistenteIA.exe"
Name: "{autodesktop}\Assistente IA"; Filename: "{app}\AssistenteIA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AssistenteIA.exe"; Description: "Abrir Assistente IA"; Flags: nowait postinstall skipifsilent
