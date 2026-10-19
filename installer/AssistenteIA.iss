[Setup]
AppId={{6C479E2C-7C41-48B9-84B3-F26814F15727}
AppName=Assistente IA
AppVersion=0.5.6
SetupIconFile=..\resources\assistente_ia.ico
DefaultDirName={localappdata}\Programs\AssistenteIA
DefaultGroupName=Assistente IA
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no
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
Source: "reiniciar_memoria.flag"; DestDir: "{localappdata}\AssistenteIA"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{localappdata}\AssistenteIA\memoria.db"
Type: files; Name: "{localappdata}\AssistenteIA\memoria.db-wal"
Type: files; Name: "{localappdata}\AssistenteIA\memoria.db-shm"
Type: files; Name: "{localappdata}\AssistenteIA\memoria.db-journal"
Type: files; Name: "{localappdata}\AssistenteIA\memoria_antes_v2_*.db"
Type: files; Name: "{localappdata}\AssistenteIA\perfil_voz.json"
Type: filesandordirs; Name: "{localappdata}\AssistenteIA\backups"

[UninstallDelete]
Type: files; Name: "{localappdata}\AssistenteIA\perfil_voz.json"
Type: files; Name: "{localappdata}\AssistenteIA\modelos\voxceleb_resnet34.onnx"

[Icons]
Name: "{group}\Assistente IA"; Filename: "{app}\AssistenteIA.exe"; IconFilename: "{app}\AssistenteIA.exe"
Name: "{autodesktop}\Assistente IA"; Filename: "{app}\AssistenteIA.exe"; IconFilename: "{app}\AssistenteIA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AssistenteIA.exe"; Description: "Abrir Assistente IA"; Flags: nowait postinstall skipifsilent
