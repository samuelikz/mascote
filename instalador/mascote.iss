; Instalador por máquina (pede administrador; instala em Program Files). Dados, memórias e IA baixada
; ficam na pasta do usuário (%LOCALAPPDATA%\Mascote). Telas: nome → IA e inicialização → instalar.
; Abrir o .exe com o pet já instalado mostra Alterar / Reparar / Remover. Reparar reinstala tudo.
; A IA embutida (llama.cpp + Gemma) é baixada no fim pelo próprio Mascote.exe, da release "ia-v1" do GitHub.
; Teste: ISCC /DTeste=1 gera uma cópia isolada (outro AppId, pasta e registro).
#ifndef Versao
  #define Versao "1.2.0"
#endif
#ifdef Teste
  #define Produto "Mascote Teste"
  #define Chave "MascoteTeste"
  #define Id "{{0B6A2C55-7E31-4D8F-9A40-3C1E6F2D9B78}"
  #define Saida "Mascote-teste-setup"
#else
  #define Produto "Mascote"
  #define Chave "Mascote"
  #define Id "{{F6490E09-0B3C-4962-AF77-5E2009D06ED9}"
  #define Saida "MascoteSetup"
#endif

[Setup]
AppId={#Id}
AppName={#Produto}
AppVersion={#Versao}
AppPublisher=Samuel
DefaultDirName={autopf}\{#Chave}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=admin
UsedUserAreasWarning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename={#Saida}
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\Mascote.exe
UninstallDisplayName={#Produto}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "..\dist\Mascote\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{userprograms}\{#Produto}"; Filename: "{app}\Mascote.exe"
Name: "{userstartup}\{#Produto}"; Filename: "{app}\Mascote.exe"; Check: IniciarMarcado

[Registry]
Root: HKCU; Subkey: "Software\{#Chave}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#Chave}"; ValueType: string; ValueName: "Nome"; ValueData: "{code:Nome}"
Root: HKCU; Subkey: "Software\{#Chave}"; ValueType: string; ValueName: "IA"; ValueData: "{code:ModoIA}"
Root: HKCU; Subkey: "Software\{#Chave}"; ValueType: string; ValueName: "ModeloOllama"; ValueData: "{code:ModeloOllama}"
Root: HKCU; Subkey: "Software\{#Chave}"; ValueType: string; ValueName: "Iniciar"; ValueData: "{code:Iniciar}"

[Run]
; baixa (ou copia do Ollama) o modelo; se falhar, o pet oferece depois
Filename: "{app}\Mascote.exe"; Parameters: "--baixar-modelo"; StatusMsg: "Baixando a IA..."; Flags: runasoriginaluser waituntilterminated; Check: IAEmbutida and not WizardSilent
Filename: "{app}\Mascote.exe"; Description: "Abrir o {#Produto} agora"; Flags: nowait postinstall skipifsilent runasoriginaluser
; atualização pelo próprio pet (modo silencioso): reabre sozinho no fim
Filename: "{app}\Mascote.exe"; Flags: nowait runasoriginaluser; Check: WizardSilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Mascote.exe /T"; Flags: runhidden; RunOnceId: "fechar"

[UninstallDelete]
; llama.cpp e modelo não vêm no instalador (são baixados), então saem explicitamente; "dados" fica
Type: filesandordirs; Name: "{localappdata}\{#Chave}\modelo"
Type: filesandordirs; Name: "{localappdata}\{#Chave}\llama"

[Code]
const
  CHAVE = 'Software\{#Chave}';
  DESINSTALAR = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#Id}_is1';
var
  PaginaManutencao: TInputOptionWizardPage;
  PaginaNome: TInputQueryWizardPage;
  PaginaIA: TWizardPage;
  OpEmbutida, OpOllama: TNewRadioButton;
  EdModelo: TNewEdit;
  CkIniciar: TNewCheckBox;
  Instalado, Fechando: Boolean;

function LerPref(Nome, Padrao: String): String;
begin
  if not RegQueryStringValue(HKCU, CHAVE, Nome, Result) or (Trim(Result) = '') then
    Result := Padrao;
end;

function Nome(Param: String): String;
begin
  Result := Trim(PaginaNome.Values[0]);
end;

function ModoIA(Param: String): String;
begin
  if OpOllama.Checked then Result := 'ollama' else Result := 'embutida';
end;

function ModeloOllama(Param: String): String;
begin
  Result := Trim(EdModelo.Text);
end;

function Iniciar(Param: String): String;
begin
  if CkIniciar.Checked then Result := '1' else Result := '0';
end;

function IniciarMarcado: Boolean;
begin
  Result := CkIniciar.Checked;
end;

function IAEmbutida: Boolean;
begin
  Result := OpEmbutida.Checked;
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  { o AppId tem '{{' escapado: sem ExpandConstant a chave procurada nunca existe }
  Instalado := RegKeyExists(HKLM, ExpandConstant(DESINSTALAR)) or
    FileExists(ExpandConstant('{autopf}\{#Chave}\unins000.exe'));
  { as versões antigas brigariam pelos atalhos e pela pasta }
  if FileExists(ExpandConstant('{localappdata}\Mascote\unins000.exe')) then begin
    MsgBox('Encontrei a versão antiga do Mascote. Desinstale ela primeiro (Configurações → Aplicativos → Mascote → Desinstalar). Suas memórias e lembretes ficam guardados.', mbError, MB_OK);
    Result := False;
  end else if not Instalado and FileExists(ExpandConstant('{autopf}\{#Chave}\Mascote.exe')) then begin
    MsgBox('Encontrei o Mascote instalado pelo MSI. Desinstale ele primeiro (Configurações → Aplicativos → Mascote → Desinstalar). Suas memórias e lembretes ficam guardados.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure TrocouIA(Sender: TObject);
begin
  EdModelo.Enabled := OpOllama.Checked;
end;

procedure InitializeWizard;
begin
  PaginaManutencao := CreateInputOptionPage(wpWelcome, 'O {#Produto} já está instalado',
    'O que você quer fazer?', '', True, False);
  PaginaManutencao.Add('Alterar: mudar nome, IA ou inicialização');
  PaginaManutencao.Add('Reparar: reinstalar tudo com as escolhas atuais');
  PaginaManutencao.Add('Remover o {#Produto} (memórias e lembretes ficam guardados)');
  PaginaManutencao.SelectedValueIndex := 0;

  PaginaNome := CreateInputQueryPage(PaginaManutencao.ID, 'Dê um nome ao seu mascote',
    'É assim que ele vai se chamar e falar de si.',
    'Dá pra mudar depois clicando com o botão direito nele → Mudar meu nome…');
  PaginaNome.Add('Nome do mascote:', False);
  PaginaNome.Values[0] := LerPref('Nome', 'Mascote');
  PaginaNome.Edits[0].MaxLength := 40;

  PaginaIA := CreateCustomPage(PaginaNome.ID, 'Qual cérebro o mascote vai usar?', 'A IA roda no seu PC, sem internet.');
  OpEmbutida := TNewRadioButton.Create(PaginaIA);
  OpEmbutida.Parent := PaginaIA.Surface;
  OpEmbutida.Width := PaginaIA.SurfaceWidth;
  OpEmbutida.Caption := 'IA embutida (Gemma 2 9B)';
  OpEmbutida.OnClick := @TrocouIA;
  with TNewStaticText.Create(PaginaIA) do begin
    Parent := PaginaIA.Surface;
    Top := ScaleY(18);
    Left := ScaleX(18);
    Caption := 'Baixa 5,5 GB do GitHub do projeto durante a instalação (ou copia do Ollama, se já estiver lá).';
  end;

  OpOllama := TNewRadioButton.Create(PaginaIA);
  OpOllama.Parent := PaginaIA.Surface;
  OpOllama.Top := ScaleY(44);
  OpOllama.Width := PaginaIA.SurfaceWidth;
  OpOllama.Caption := 'Usar o Ollama já instalado neste PC (não baixa nada).';
  OpOllama.OnClick := @TrocouIA;

  EdModelo := TNewEdit.Create(PaginaIA);
  EdModelo.Parent := PaginaIA.Surface;
  EdModelo.Top := ScaleY(70);
  EdModelo.Left := ScaleX(18);
  EdModelo.Width := ScaleX(200);
  EdModelo.MaxLength := 80;
  EdModelo.Text := LerPref('ModeloOllama', 'gemma2:9b');

  CkIniciar := TNewCheckBox.Create(PaginaIA);
  CkIniciar.Parent := PaginaIA.Surface;
  CkIniciar.Top := ScaleY(115);
  CkIniciar.Width := PaginaIA.SurfaceWidth;
  CkIniciar.Caption := 'Iniciar o mascote junto com o Windows';
  CkIniciar.Checked := LerPref('Iniciar', '1') = '1';

  OpOllama.Checked := LerPref('IA', 'embutida') = 'ollama';
  OpEmbutida.Checked := not OpOllama.Checked;
  TrocouIA(nil);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := ((PageID = PaginaManutencao.ID) and not Instalado) or
    (((PageID = PaginaNome.ID) or (PageID = PaginaIA.ID)) and Instalado and (PaginaManutencao.SelectedValueIndex = 1));
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Desinstalador: String;
  Codigo: Integer;
begin
  Result := True;
  if (CurPageID = PaginaManutencao.ID) and (PaginaManutencao.SelectedValueIndex = 2) then begin
    if RegQueryStringValue(HKLM, ExpandConstant(DESINSTALAR), 'UninstallString', Desinstalador) then
      Exec(RemoveQuotes(Desinstalador), '', '', SW_SHOW, ewWaitUntilTerminated, Codigo);
    Fechando := True;
    WizardForm.Close;
    Result := False;
  end else if (CurPageID = PaginaNome.ID) and (Nome('') = '') then begin
    MsgBox('Dê um nome ao mascote.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if Fechando then Confirm := False;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  { fecha o pet antes de atualizar; o llama-server morre junto pelo Job do Windows.
    Sem /T: quando a atualização vem do pet, este instalador é filho dele e o /T o mataria também. }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM Mascote.exe', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { Alterar desmarcando "iniciar com o Windows" precisa apagar o atalho que já existe }
  if (CurStep = ssPostInstall) and not CkIniciar.Checked then
    DeleteFile(ExpandConstant('{userstartup}\{#Produto}.lnk'));
end;
