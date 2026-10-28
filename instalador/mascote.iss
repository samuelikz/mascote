; Instalador por usuário (sem admin). Dados ficam em {localappdata}\Mascote\dados e sobrevivem à desinstalação.
[Setup]
AppId={{6F1C7A52-3B0E-4C55-9E64-0D5B6E8A2F11}
AppName=Mascote
AppVersion=1.0
AppPublisher=Samuel
DefaultDirName={localappdata}\Mascote
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\instalador
OutputBaseFilename=MascoteSetup
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\Mascote.exe
Compression=lzma2/fast
SolidCompression=no
; um .exe do Windows não passa de 4 GB e o modelo tem 5,4 GB: o instalador sai em partes (.bin) ao lado do .exe
DiskSpanning=yes
DiskSliceSize=max
CloseApplications=yes
WizardStyle=modern

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "iniciar"; Description: "Iniciar o Mascote junto com o Windows"

[Files]
Source: "..\dist\Mascote\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\recursos\llama\*"; DestDir: "{app}\recursos\llama"; Flags: recursesubdirs ignoreversion
Source: "..\recursos\modelo\gemma2-9b.gguf"; DestDir: "{app}\recursos\modelo"; Flags: nocompression ignoreversion

[Icons]
Name: "{userprograms}\Mascote"; Filename: "{app}\Mascote.exe"
Name: "{userstartup}\Mascote"; Filename: "{app}\Mascote.exe"; Tasks: iniciar

[Run]
Filename: "{app}\Mascote.exe"; Description: "Abrir o Mascote agora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM Mascote.exe /T"; Flags: runhidden; RunOnceId: "fechar"
