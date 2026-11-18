# Build the Windows installer for ParseCraft.
#
# Prerequisites:
#   * Python with the runtime dependencies installed (pip install -r requirements.txt)
#   * PyInstaller           (pip install pyinstaller)
#   * Inno Setup 6+         (https://jrsoftware.org/isinfo.php) with ISCC.exe on PATH
#
# Usage (from the repository root):
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#
# Output:
#   dist\ParseCraft\   (onedir application)
#   dist\Updater\Updater.exe        (standalone updater)
#   dist\installer\ParseCraft-<version>-Setup.exe

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== Generating version_info.txt ==" -ForegroundColor Cyan
python packaging\make_version_info.py

Write-Host "== Building application ==" -ForegroundColor Cyan
python -m PyInstaller --noconfirm packaging\app.spec

Write-Host "== Building updater ==" -ForegroundColor Cyan
python -m PyInstaller --noconfirm packaging\updater.spec

Write-Host "== Copying Updater.exe next to the application ==" -ForegroundColor Cyan
$UpdaterSrc = Join-Path $Root "dist\Updater\Updater.exe"
$AppDir = Join-Path $Root "dist\ParseCraft"
if (-not (Test-Path -LiteralPath $AppDir)) {
    throw "Application output not found: $AppDir"
}
Copy-Item -LiteralPath $UpdaterSrc -Destination $AppDir -Force

Write-Host "== Compiling installer with Inno Setup ==" -ForegroundColor Cyan
$Iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $Iscc) {
    $Candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $Candidates) {
        if (Test-Path -LiteralPath $candidate) { $Iscc = $candidate; break }
    }
}
if (-not $Iscc) {
    throw "ISCC.exe (Inno Setup) not found. Install Inno Setup 6+ and retry."
}
$IsccPath = if ($Iscc -is [System.Management.Automation.ApplicationInfo]) { $Iscc.Source } else { $Iscc }
& $IsccPath (Join-Path $Root "packaging\installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed with code $LASTEXITCODE" }

Write-Host "== Build complete ==" -ForegroundColor Green
Write-Host "Installer: dist\installer\ParseCraft-<version>-Setup.exe"