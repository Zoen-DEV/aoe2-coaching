; Instalador de AoE2 Coaching (Inno Setup 6). Lo compila empaquetar.py:
;   ISCC /DVersion=1.0.0 /DFuente=<carpeta de PyInstaller> /DSalida=<carpeta> /DIcono=<.ico>
;        /DMarca=<imágenes y letra de marca_instalador.py> aoe2c.iss
;
; - Se instala en %LOCALAPPDATA%\AoE2Coaching, sin permisos de administrador.
; - Acceso en el menú Inicio (y en el escritorio, si se elige) y desinstalador.
; - Antes de copiar, cierra la copia abierta de AoE2C (AoE2Coaching.exe --salir).
; - Las actualizaciones de la app lo abren con /SILENT: pone la versión nueva encima y
;   vuelve a abrir AoE2C (la entrada de [Run] no lleva skipifsilent).
; - Al desinstalar pregunta con dos casillas: quitar del juego lo de AoE2C (marcada) y
;   borrar el historial y la configuración (sin marcar). Lo hace AoE2Coaching.exe
;   --desinstalar (ver desinstalar.py); si el juego está abierto, pide cerrarlo.

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Fuente
  #define Fuente "..\..\..\build\desktop\dist\AoE2Coaching"
#endif
#ifndef Salida
  #define Salida "..\..\..\build\instalador"
#endif
#ifndef Icono
  #define Icono "..\..\..\build\marca\aoe2c.ico"
#endif
#ifndef Marca
  #define Marca "..\..\..\build\marca\instalador"
#endif
#define Exe "AoE2Coaching.exe"
; Los colores del panel (estilo.py).
#define Fondo "#13110e"
#define Oro "#e9c992"
#define Secundario "#c2b7a5"
#define Repo "https://github.com/Zoen-DEV/aoe2-coaching"

[Setup]
; El AppId no cambia nunca: con él Windows reconoce que es la misma app al actualizar.
AppId={{2605D640-CD22-4A33-8C00-8723C2C2F299}
AppName=AoE2 Coaching
AppVersion={#Version}
AppVerName=AoE2 Coaching {#Version}
AppPublisher=Zoen-DEV
AppPublisherURL={#Repo}
AppSupportURL={#Repo}/issues
AppUpdatesURL={#Repo}/releases
VersionInfoVersion={#Version}
VersionInfoProductName=AoE2 Coaching
DefaultDirName={localappdata}\AoE2Coaching
DisableDirPage=yes
; La bienvenida muestra la barra lateral con el escudo (las actualizaciones van en silencio).
DisableWelcomePage=no
DefaultGroupName=AoE2 Coaching
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir={#Salida}
OutputBaseFilename=AoE2Coaching-Setup-{#Version}
SetupIconFile={#Icono}
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName=AoE2 Coaching
Compression=lzma2/max
SolidCompression=yes
; La marca del panel: oscuro siempre, fondo cálido con brillos dorado y granate, la barra
; lateral con el escudo en la bienvenida y el final, y el escudo en la cabecera. Las
; imágenes las arma marca_instalador.py en varios tamaños (Setup elige según los DPI).
WizardStyle=modern dark hidebevels
WizardBackColor={#Fondo}
WizardBackImageFile={#Marca}\fondo-*.png
WizardImageFile={#Marca}\lateral-*.png
WizardSmallImageFile={#Marca}\cabecera-*.png
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=auto

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
es.Escritorio=Crear un acceso directo en el escritorio
en.Escritorio=Create a desktop shortcut
es.Abrir=Abrir AoE2 Coaching
en.Abrir=Open AoE2 Coaching
es.DesTitulo=Desinstalar AoE2 Coaching
en.DesTitulo=Uninstall AoE2 Coaching
es.DesTexto=AoE2 Coaching se va a quitar de esta PC.
en.DesTexto=AoE2 Coaching will be removed from this PC.
es.DesJuego=Quitar del juego las guías, mapas y mods de AoE2C
en.DesJuego=Remove AoE2C's guides, maps and mods from the game
es.DesDatos=Borrar el historial y la configuración (no se puede deshacer)
en.DesDatos=Delete my history and settings (can't be undone)
es.DesSeguir=Desinstalar
en.DesSeguir=Uninstall
es.DesCancelar=Cancelar
en.DesCancelar=Cancel
es.DesJuegoAbierto=Age of Empires II está abierto. Ciérralo y pulsa Reintentar para quitar del juego las guías, mapas y mods de AoE2C, o Cancelar para dejarlos.
en.DesJuegoAbierto=Age of Empires II is open. Close it and press Retry to remove AoE2C's guides, maps and mods from the game, or Cancel to leave them.
es.DesFallo=No se pudo quitar todo lo de AoE2C. Lo que quede se puede borrar a mano: el mod "guia-apertura-castillos" en la carpeta mods\local del perfil del juego y la carpeta %APPDATA%\AoE2Coaching.
en.DesFallo=Not everything from AoE2C could be removed. You can delete what's left by hand: the "guia-apertura-castillos" mod in the game profile's mods\local folder and the %APPDATA%\AoE2Coaching folder.

[Tasks]
Name: "escritorio"; Description: "{cm:Escritorio}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Las bibliotecas de la versión anterior: así no quedan archivos viejos mezclados.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Fuente}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; La letra de los títulos: solo la usa el asistente, no se instala.
Source: "{#Marca}\cinzel.ttf"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\AoE2 Coaching"; Filename: "{app}\{#Exe}"
Name: "{autodesktop}\AoE2 Coaching"; Filename: "{app}\{#Exe}"; Tasks: escritorio

[Run]
Filename: "{app}\{#Exe}"; Description: "{cm:Abrir}"; Flags: nowait postinstall

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  QuitarDelJuego, BorrarDatos: Boolean;
  ConCinzel: Boolean;

const
  FR_PRIVATE = $10;

{ Carga una fuente solo para este proceso (no la instala en Windows). }
function AddFontResourceEx(Archivo: String; Banderas: Cardinal; Reservado: Cardinal): Integer;
  external 'AddFontResourceExW@gdi32.dll stdcall';

{ Títulos en oro (con Cinzel, como el panel, si cargó) y textos en el gris cálido. }
procedure Titulo(L: TNewStaticText; Tamano: Integer);
begin
  L.StyleElements := L.StyleElements - [seFont];
  L.Font.Color := StrToColor('{#Oro}');
  L.Font.Style := [fsBold];
  if ConCinzel then
    L.Font.Name := 'Cinzel';
  if Tamano > 0 then
    L.Font.Size := Tamano;
end;

procedure Secundario(L: TNewStaticText);
begin
  L.StyleElements := L.StyleElements - [seFont];
  L.Font.Color := StrToColor('{#Secundario}');
end;

procedure InitializeWizard();
begin
  ExtractTemporaryFile('cinzel.ttf');
  ConCinzel := AddFontResourceEx(ExpandConstant('{tmp}\cinzel.ttf'), FR_PRIVATE, 0) > 0;
  Titulo(WizardForm.WelcomeLabel1, 0);
  Titulo(WizardForm.FinishedHeadingLabel, 0);
  Titulo(WizardForm.PageNameLabel, 0);
  Secundario(WizardForm.WelcomeLabel2);
  Secundario(WizardForm.FinishedLabel);
  Secundario(WizardForm.PageDescriptionLabel);
end;

{ Antes de copiar archivos: cerrar la copia abierta (la de la bandeja). }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\{#Exe}')) then
    Exec(ExpandConstant('{app}\{#Exe}'), '--salir', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
end;

{ Las dos casillas de la desinstalación. }
function PreguntarDesinstalacion(): Boolean;
var
  Ventana: TSetupForm;
  Cabecera, Texto: TNewStaticText;
  Juego, Datos: TNewCheckBox;
  Seguir, Cancelar: TNewButton;
begin
  { Inno Setup 6.7: ancho, alto y si se puede estirar a lo ancho / a lo alto. }
  Ventana := CreateCustomForm(ScaleX(460), ScaleY(184), False, True);
  try
    Ventana.Caption := CustomMessage('DesTitulo');

    Cabecera := TNewStaticText.Create(Ventana);
    Cabecera.Parent := Ventana;
    Cabecera.Left := ScaleX(16);
    Cabecera.Top := ScaleY(14);
    Cabecera.Caption := CustomMessage('DesTitulo');
    Titulo(Cabecera, 12);

    Texto := TNewStaticText.Create(Ventana);
    Texto.Parent := Ventana;
    Texto.Left := ScaleX(16);
    Texto.Top := ScaleY(46);
    Texto.Caption := CustomMessage('DesTexto');
    Secundario(Texto);

    Juego := TNewCheckBox.Create(Ventana);
    Juego.Parent := Ventana;
    Juego.Left := ScaleX(16);
    Juego.Top := ScaleY(78);
    Juego.Width := Ventana.ClientWidth - ScaleX(32);
    Juego.Height := ScaleY(20);
    Juego.Caption := CustomMessage('DesJuego');
    Juego.Checked := True;

    Datos := TNewCheckBox.Create(Ventana);
    Datos.Parent := Ventana;
    Datos.Left := ScaleX(16);
    Datos.Top := ScaleY(106);
    Datos.Width := Ventana.ClientWidth - ScaleX(32);
    Datos.Height := ScaleY(20);
    Datos.Caption := CustomMessage('DesDatos');
    Datos.Checked := False;

    Cancelar := TNewButton.Create(Ventana);
    Cancelar.Parent := Ventana;
    Cancelar.Width := ScaleX(90);
    Cancelar.Height := ScaleY(26);
    Cancelar.Left := Ventana.ClientWidth - Cancelar.Width - ScaleX(16);
    Cancelar.Top := Ventana.ClientHeight - Cancelar.Height - ScaleY(16);
    Cancelar.Caption := CustomMessage('DesCancelar');
    Cancelar.ModalResult := mrCancel;
    Cancelar.Cancel := True;

    Seguir := TNewButton.Create(Ventana);
    Seguir.Parent := Ventana;
    Seguir.Width := ScaleX(110);
    Seguir.Height := ScaleY(26);
    Seguir.Left := Cancelar.Left - Seguir.Width - ScaleX(8);
    Seguir.Top := Cancelar.Top;
    Seguir.Caption := CustomMessage('DesSeguir');
    Seguir.ModalResult := mrOk;
    Seguir.Default := True;

    Ventana.ActiveControl := Seguir;
    Result := Ventana.ShowModal() = mrOk;
    QuitarDelJuego := Juego.Checked;
    BorrarDatos := Datos.Checked;
  finally
    Ventana.Free();
  end;
end;

function InitializeUninstall(): Boolean;
begin
  QuitarDelJuego := True;
  BorrarDatos := False;
  Result := True;
  if not UninstallSilent then
    Result := PreguntarDesinstalacion();
end;

function Opciones(ConJuego: Boolean): String;
begin
  Result := '--desinstalar';
  if ConJuego then
    Result := Result + ' --juego';
  if BorrarDatos then
    Result := Result + ' --datos';
end;

{ Antes de borrar los archivos: AoE2C limpia lo suyo (con el juego cerrado). }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Exe: String;
  Codigo: Integer;
  ConJuego: Boolean;
begin
  if CurUninstallStep <> usUninstall then
    Exit;
  Exe := ExpandConstant('{app}\{#Exe}');
  if not FileExists(Exe) then
    Exit;
  ConJuego := QuitarDelJuego;
  while True do
  begin
    if not Exec(Exe, Opciones(ConJuego), '', SW_HIDE, ewWaitUntilTerminated, Codigo) then
      Break;
    if Codigo = 2 then
    begin
      { El juego está abierto: se reintenta o se sigue sin tocar el juego. }
      if UninstallSilent or (MsgBox(CustomMessage('DesJuegoAbierto'), mbError, MB_RETRYCANCEL) <> IDRETRY) then
        ConJuego := False;
    end
    else
    begin
      if (Codigo <> 0) and not UninstallSilent then
        MsgBox(CustomMessage('DesFallo'), mbInformation, MB_OK);
      Break;
    end;
  end;
end;
