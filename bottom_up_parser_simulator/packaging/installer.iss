; -*- coding: utf-8 -*-
; Inno Setup script for ParseCraft.
;
; Build the PyInstaller output first (see packaging/build.ps1), then compile:
;     iscc packaging\installer.iss
;
; The installer:
;   * installs into Program Files (default: {autopf}\ParseCraft),
;   * lets the user choose the installation directory,
;   * creates Start Menu shortcuts (and an optional desktop shortcut),
;   * registers an uninstall entry in "Apps & Features" with the app version,
;   * supports upgrading an existing installation (same AppId upgrades in place),
;   * never touches per-user data (stored in %APPDATA%\ParseCraft).

#define MyAppName "ParseCraft"
#ifndef MyAppVersion
#define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "Compiler Construction"
#define MyAppExeName "ParseCraft.exe"
; A stable AppId is required so that new versions upgrade the existing install.
#define MyAppId "{{7A9C1E2B-3F4D-4A5B-8C6D-1E2F3A4B5C6D}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=
OutputDir=dist\installer
OutputBaseFilename=ParseCraft-{#MyAppVersion}-Setup
SetupIconFile=
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
; Close any running ParseCraft instance before overwriting files. This is what
; prevents "DeleteFile failed; code 5. Access is denied" when the running
; executable is locked by the OS.
CloseApplications=yes
RestartApp=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; The whole onedir build (exe, runtime, version.json, Updater.exe).
Source: "..\dist\ParseCraft\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; (none)

[Run]
; Launch the application after installation. skipifsilent is intentionally
; omitted so that auto-updates (which run the installer silently) still
; relaunch the app. The external Updater.exe handles waiting for the app to
; exit before invoking the installer, so this relaunch is the final step.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall

[UninstallDelete]
; Per-user data is intentionally NOT removed on uninstall.
Type: filesandordirs; Name: "{app}\__pycache__"