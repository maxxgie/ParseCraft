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
; Per-user install under %LOCALAPPDATA%\Programs\ParseCraft. This matches the
; runtime path used by core.paths.get_install_dir() when frozen, so the
; Updater.exe can overwrite files without admin elevation and without the
; running app holding a lock (the app is always closed first).
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=none
LicenseFile=
OutputDir=dist\installer
OutputBaseFilename=ParseCraft-{#MyAppVersion}-Setup
SetupIconFile=
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
; The external Updater.exe ensures the running app is fully gone before this
; installer is invoked, so CloseApplications is not needed and would only
; cause Inno Setup to wait for a process that has already exited.
CloseApplications=no
RestartApp=no

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
; The external Updater.exe handles relaunching the app after the installer
; finishes, so we do not launch it here.

[UninstallDelete]
; Per-user data is intentionally NOT removed on uninstall.
Type: filesandordirs; Name: "{app}\__pycache__"