# Releasing a New Version

ParseCraft uses **GitHub Releases** as its update server. There is no custom
server: the application reads `manifest.json` from the repository and downloads
the installer attached to the matching GitHub Release.

* Repository: <https://github.com/maxxgie/ParseCraft>
* Application directory: `bottom_up_parser_simulator/`
* Manifest: `bottom_up_parser_simulator/manifest.json`
* Manifest URL used by the app:
  `https://raw.githubusercontent.com/maxxgie/ParseCraft/main/bottom_up_parser_simulator/manifest.json`

## End-to-end flow

```
Developer: bump version -> commit -> tag v1.1.0 -> push tag
           -> GitHub Actions builds the installer and creates the Release
           -> update manifest.json (version + sha256 + download_url) -> push

User:      launch ParseCraft -> read manifest.json from GitHub -> compare versions
           -> download installer -> verify SHA-256 -> install -> restart
```

## 1. Update the version

The single source of truth is `bottom_up_parser_simulator/version.json`.
`core/version.py` reads it at startup (falling back to the built-in constants
when the file is absent), so the application always knows its installed
version, build, and release date.

```json
{
  "version": "1.1.0",
  "build": "101",
  "release_date": "2026-11-18",
  "channel": "stable"
}
```

Follow semantic versioning: `MAJOR.MINOR.PATCH`.

## 2. Commit the changes

```powershell
git add -A
git commit -m "Release v1.1.0"
git push origin main
```

## 3. Create and push a tag

The release workflow triggers on tags matching `v*`:

```powershell
git tag v1.1.0
git push origin v1.1.0
```

## 4. GitHub Actions builds and publishes

The workflow at `.github/workflows/release.yml` (repository root) runs on the
`windows-latest` runner, builds the application with PyInstaller, compiles the
installer with Inno Setup 6, computes the installer SHA-256, and creates a
GitHub Release with the installer attached.

## 5. Update `manifest.json`

Point the manifest at the new release and record the installer's SHA-256 so the
application can reject corrupted downloads. The `download_url` is the
browser-download URL of the release asset:

```
https://github.com/maxxgie/ParseCraft/releases/download/v<version>/<installer-file>
```

```json
{
  "app_name": "ParseCraft",
  "latest_version": "1.1.0",
  "build": "101",
  "release_date": "2026-11-18",
  "download_url": "https://github.com/maxxgie/ParseCraft/releases/download/v1.1.0/ParseCraft-1.1.0-Setup.exe",
  "sha256": "<64-hex-sha256-of-the-installer>",
  "min_version": "1.0.0",
  "package_type": "installer",
  "release_notes": [
    "Added LR parser improvements",
    "Added ACTION/GOTO table generation",
    "Fixed parser visualization bugs"
  ]
}
```

Compute the hash on Windows with:

```powershell
Get-FileHash .\dist\installer\ParseCraft-1.1.0-Setup.exe -Algorithm SHA256
```

Commit and push the updated manifest to `main`:

```powershell
git add bottom_up_parser_simulator/manifest.json
git commit -m "Update manifest for v1.1.0"
git push origin main
```

Users are offered the update the next time they launch ParseCraft.

## Manual build (without the workflow)

On a Windows machine with Python, [PyInstaller](https://pyinstaller.org/), and
[Inno Setup 6](https://jrsoftware.org/isinfo.php) installed:

```powershell
cd bottom_up_parser_simulator
pip install -r requirements.txt
pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Output:

```
dist\ParseCraft\                              (onedir application)
dist\Updater\Updater.exe                      (standalone updater)
dist\installer\ParseCraft-<version>-Setup.exe
```

## How the application finds the manifest

The manifest URL is resolved with this priority:

1. **User setting** — `manifest_url` in the in-app settings.
2. **Environment variable** — `BUP_UPDATES_URL`.
3. **Default constant** — `DEFAULT_MANIFEST_URL` in `core/version.py`
   (points at the GitHub raw manifest above).

Only `https` (and `file` for testing) URLs are accepted; plain `http` is
rejected. Every download is verified against the manifest `sha256` before the
installer is launched.

## Testing an update locally

Simulate the full flow (detection, notification, download, verification,
install, restart, rollback) without a real release:

```powershell
python scripts\simulate_update.py --installed 1.0.0 --available 1.1.0
```

To test against a local manifest file instead of GitHub:

```powershell
$env:BUP_UPDATES_URL = "file:///C:/path/to/manifest.json"
python main.py
```