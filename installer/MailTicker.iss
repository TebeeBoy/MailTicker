; Mail Ticker telepítő (Inno Setup 6)
;
; Felhasználónként, rendszergazdai jog nélkül telepít a %LOCALAPPDATA%\Programs\MailTicker
; mappába – ez írható, így a program önfrissítése is működik. Start menü, opcionális
; Asztal-ikon és automatikus indítás, eltávolítás a „Programok és szolgáltatások” alól.
;
; Fordítás (a verziót a build szkript adja át):  ISCC /DAppVersion=0.6.0 installer\MailTicker.iss
; A kész telepítő: dist\MailTicker-Setup-<verzió>.exe
;
; Csendes frissítés (ezt használja a program):  MailTicker-Setup-x.y.z.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

; Az AppGuid-ot soha nem szabad megváltoztatni: ez alapján ismeri fel a frissítés a meglévő telepítést.
#define AppGuid "1D064C70-D692-4D3E-B1A3-416ED2614F73"
#define AppName "Mail Ticker"
#define AppExe "MailTicker.exe"
#define RunKey "Software\Microsoft\Windows\CurrentVersion\Run"
#define RunValue "MailTicker"

[Setup]
AppId={{{#AppGuid}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=TebeeBoy
AppPublisherURL=https://github.com/TebeeBoy/MailTicker
AppSupportURL=https://github.com/TebeeBoy/MailTicker/issues
AppUpdatesURL=https://github.com/TebeeBoy/MailTicker/releases
PrivilegesRequired=lowest
DefaultDirName={autopf}\MailTicker
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=..\assets\mailticker.ico
OutputDir=..\dist
OutputBaseFilename=MailTicker-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} telepítő
; a futó példányt mi magunk állítjuk le (PrepareToInstall), a Restart Managerre nincs szükség
CloseApplications=no

[Languages]
Name: "hu"; MessagesFile: "compiler:Languages\Hungarian.isl"

[Tasks]
Name: "desktopicon"; Description: "Parancsikon az Asztalon"; GroupDescription: "További parancsikonok:"; Flags: unchecked
Name: "autostart"; Description: "Indítás a Windows-zal"; GroupDescription: "Indítás:"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName} eltávolítása"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Ugyanaz a bejegyzés, amit a program menüjének „Indítás a Windows-zal” pontja kezel.
; Csendes frissítésnél (a program önfrissítése) nem írjuk, hogy a menüben kikapcsolt automatikus
; indítás kikapcsolva maradjon.
Root: HKCU; Subkey: "{#RunKey}"; ValueType: string; ValueName: "{#RunValue}"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart; Check: not IsSilentUpgrade

[Run]
Filename: "{app}\{#AppExe}"; Description: "{#AppName} indítása"; Flags: nowait postinstall skipifsilent
; csendes frissítés után a program magától újraindul
Filename: "{app}\{#AppExe}"; Parameters: "--after-update"; Flags: nowait; Check: WizardSilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "StopMailTicker"

[UninstallDelete]
; a hordozható (nem telepített) önfrissítés maradéka, ha lenne
Type: files; Name: "{app}\{#AppExe}.old"

[Code]
var
  WasInstalled: Boolean;

function InitializeSetup: Boolean;
begin
  WasInstalled := RegKeyExists(HKEY_CURRENT_USER,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{{#AppGuid}}_is1');
  Result := True;
end;

function IsSilentUpgrade: Boolean;
begin
  Result := WizardSilent and WasInstalled;
end;

procedure StopRunningTicker;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningTicker;
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { a programból bekapcsolt automatikus indítást is eltávolítjuk; a beállítások (%APPDATA%\MailTicker) megmaradnak }
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, '{#RunKey}', '{#RunValue}');
end;
