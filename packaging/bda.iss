; Installeur Windows de BDA (Inno Setup 6.3+), à compiler depuis la racine du
; dépôt une fois `pyinstaller packaging/bda.spec` passé :
;
;     ISCC.exe /DAppVersion=1.0.5 packaging/bda.iss
;
; `packaging/package.py` le fait tout seul sur Windows quand ISCC est trouvé
; (chemin par défaut d'Inno Setup 6 ou variable d'environnement ISCC), et
; c'est ainsi que le job de release le produit. Résultat :
;
;     dist/BDA-<version>-windows-setup.exe
;
; Choix à connaître :
; - Installation **par utilisateur** (`{userpf}` = %LocalAppData%\Programs),
;   sans droits d'administrateur. C'est aussi ce qui permet à la mise à jour
;   intégrée (`logos/selfupdate.py`) de remplacer le dossier BDA sans
;   élévation : une installation dans Program Files l'en empêcherait.
; - Le dossier `_internal` de PyInstaller est vidé avant une réinstallation,
;   sinon les bibliothèques d'une ancienne version resteraient à côté des
;   nouvelles.
; - Le désinstalleur retire tout le dossier de l'application, y compris ce
;   qu'une mise à jour intégrée y a déposé depuis, mais **jamais** `~/.bda`
;   (base, corpus déposé, réglages), qui appartient à l'opérateur.
; - Le corpus de prédications n'est pas plus embarqué ici que dans l'archive :
;   c'est `bda.spec` qui décide (BDA_BUNDLE_PREDICATIONS).
; - L'AppId ci-dessous est aussi dans `logos/selfupdate.py` (INNO_APP_ID) :
;   la mise à jour intégrée s'en sert pour mettre à jour la version affichée
;   dans « Applications installées ». Ne pas le changer sans l'autre.

#ifndef AppVersion
  #error "Passer la version : ISCC.exe /DAppVersion=1.2.3 packaging/bda.iss"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\BDA"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

[Setup]
AppId={A3F5C7E9-2B4D-4E6F-8A1C-3D5E7F9B1C2D}
AppName=BDA
AppVersion={#AppVersion}
AppVerName=BDA {#AppVersion}
AppPublisher=Logos Tabernacle
VersionInfoVersion={#AppVersion}
DefaultDirName={userpf}\BDA
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=BDA-{#AppVersion}-windows-setup
SetupIconFile=icons\bda.ico
UninstallDisplayIcon={app}\BDA.exe
UninstallDisplayName=BDA
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Une réinstallation par-dessus une autre version ne doit pas laisser les
; bibliothèques de l'ancienne à côté des nouvelles.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{userprograms}\BDA"; Filename: "{app}\BDA.exe"
Name: "{userdesktop}\BDA"; Filename: "{app}\BDA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BDA.exe"; Description: "{cm:LaunchProgram,BDA}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Tout le dossier, y compris ce qu'une mise à jour intégrée y a mis depuis.
Type: filesandordirs; Name: "{app}"
