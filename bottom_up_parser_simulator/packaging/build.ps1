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
#   dist\Updater.exe   (standalone updater, onefile)
#   dist\installer\ParseCraft-<version>-Setup.exe

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# --- Signing configuration (from environment) ---
$SigningEnabled = [System.String]::IsNullOrWhiteSpace($env:SIGNING_ENABLED) -eq $false -and $env:SIGNING_ENABLED.Trim().ToLower() -eq "true"
$PfxPath = $env:PFX_CERTIFICATE_PATH
$PfxPassword = $env:PFX_CERTIFICATE_PASSWORD
$TimestampServer = if ([System.String]::IsNullOrWhiteSpace($env:TIMESTAMP_SERVER)) { "http://timestamp.digicert.com" } else { $env:TIMESTAMP_SERVER }

function Find-SignTool {
    $cmd = Get-Command signtool -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $kits = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "${env:ProgramFiles}\Windows Kits\10\bin"
    )
    foreach ($base in $kits) {
        if (Test-Path -LiteralPath $base) {
            $found = Get-ChildItem -Path $base -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) { return $found.FullName }
        }
    }
    return $null
}

function Sign-Binary($file) {
    if (-not $SigningEnabled) { return }
    $SignTool = Find-SignTool
    if (-not $SignTool) { throw "signtool.exe not found. Install Windows SDK or add to PATH." }
    if ([System.String]::IsNullOrWhiteSpace($PfxPath) -or -not (Test-Path -LiteralPath $PfxPath)) {
        throw "PFX certificate not found: $PfxPath"
    }
    if ([System.String]::IsNullOrWhiteSpace($PfxPassword)) {
        throw "PFX_CERTIFICATE_PASSWORD is required when SIGNING_ENABLED=true."
    }
    Write-Host "== Signing $file ==" -ForegroundColor Cyan
    & $SignTool sign /fd SHA256 /f $PfxPath /p $PfxPassword /tr $TimestampServer /td SHA256 $file
    if ($LASTEXITCODE -ne 0) { throw "Signing failed for $file (exit $LASTEXITCODE)" }
}

function Verify-Signature($file) {
    if (-not $SigningEnabled) { return }
    $SignTool = Find-SignTool
    if (-not $SignTool) { throw "signtool.exe not found." }
    Write-Host "== Verifying signature: $file ==" -ForegroundColor Cyan
    & $SignTool verify /pa $file
    if ($LASTEXITCODE -ne 0) { throw "Signature verification failed for $file" }
}

Write-Host "== Generating version_info.txt ==" -ForegroundColor Cyan
python packaging\make_version_info.py 2>&1
if ($LASTEXITCODE -ne 0) { throw "make_version_info.py failed (exit $LASTEXITCODE)" }

Write-Host "== Building application ==" -ForegroundColor Cyan
# PyInstaller writes progress to stderr; suppress the NativeCommandError that
# $ErrorActionPreference="Stop" would otherwise raise on stderr output.
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
python -m PyInstaller --noconfirm packaging\app.spec 2>&1
$appExit = $LASTEXITCODE
$ErrorActionPreference = $prev
if ($appExit -ne 0) { throw "PyInstaller app build failed (exit $appExit)" }

Write-Host "== Building updater ==" -ForegroundColor Cyan
$ErrorActionPreference = "Continue"
python -m PyInstaller --noconfirm packaging\updater.spec 2>&1
$updaterExit = $LASTEXITCODE
$ErrorActionPreference = $prev
if ($updaterExit -ne 0) { throw "PyInstaller updater build failed (exit $updaterExit)" }

Write-Host "== Copying Updater.exe next to the application ==" -ForegroundColor Cyan
$UpdaterSrc = Join-Path $Root "dist\Updater.exe"
$AppDir = Join-Path $Root "dist\ParseCraft"
if (-not (Test-Path -LiteralPath $AppDir)) {
    throw "Application output not found: $AppDir"
}
Copy-Item -LiteralPath $UpdaterSrc -Destination $AppDir -Force
Sign-Binary (Join-Path $AppDir "ParseCraft.exe")

Write-Host "== Compiling installer with Inno Setup ==" -ForegroundColor Cyan
$Iscc = Get-Command iscc -ErrorAction SilentlyContinue
    if (-not $Iscc) {
        $Candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
            "$env:USERPROFILE\.chocolatey\innosetup\ISCC.exe",
            "C:\ProgramData\chocolatey\innosetup\ISCC.exe"
        )
        foreach ($candidate in $Candidates) {
            if (Test-Path -LiteralPath $candidate) { $Iscc = $candidate; break }
        }
    }
    if (-not $Iscc) {
        $found = Get-ChildItem -Path "${env:ProgramFiles(x86)}\Inno Setup*" -Recurse -Filter "ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { $Iscc = $found.FullName }
    }
if (-not $Iscc) {
        throw "ISCC.exe (Inno Setup) not found. Install Inno Setup 6+ and retry."
    }
    $IsccPath = if ($Iscc -is [System.Management.Automation.ApplicationInfo]) { $Iscc.Source } else { $Iscc }
    $versionFromManifest = (Get-Content (Join-Path $Root "manifest.json") | ConvertFrom-Json).latest_version
    $ErrorActionPreference = "Continue"
    & $IsccPath (Join-Path $Root "packaging\installer.iss") /DMyAppVersion=$versionFromManifest 2>&1
    $isccExit = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($isccExit -ne 0) { throw "Inno Setup compilation failed with code $isccExit" }

    $Installer = Get-ChildItem -Path (Join-Path $Root "packaging\dist\installer") -Filter "*.exe" | Select-Object -First 1
    if (-not $Installer) { throw "Installer not found after build." }
    Sign-Binary $Installer.FullName
    Verify-Signature (Join-Path $AppDir "ParseCraft.exe")
    Verify-Signature $Installer.FullName

if (-not $SigningEnabled) {
    Write-Host "Build completed without code signing." -ForegroundColor Yellow
}

Write-Host "== Build complete ==" -ForegroundColor Green
Write-Host "Installer: dist\installer\ParseCraft-<version>-Setup.exe"