"""Development test mode: simulate the full update workflow end-to-end.

This script exercises the real update pipeline (detection -> download ->
verification -> install -> restart -> rollback) inside a throwaway sandbox, so
the update system can be validated without a real server or a real install.

Usage:
    python scripts/simulate_update.py
    python scripts/simulate_update.py --installed 1.0.0 --available 1.1.0

It prints a PASS/FAIL line for every step and exits non-zero if any step fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

# Make the project root importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.update.checker import check_for_update  # noqa: E402
from core.update.downloader import download  # noqa: E402
from core.update.installer import apply_zip_update  # noqa: E402
from core.update.manifest import ReleaseManifest  # noqa: E402
from core.update.verifier import verify_sha256  # noqa: E402
from core.version import compare_versions  # noqa: E402


class Reporter:
    """Collects and prints step results."""

    def __init__(self) -> None:
        self.failures = 0

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        status = "PASS" if condition else "FAIL"
        if not condition:
            self.failures += 1
        line = f"[{status}] {name}"
        if detail:
            line += f" - {detail}"
        print(line)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_zip(zip_path: Path, files: dict) -> None:
    with zipfile.ZipFile(zip_path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def _make_install(install_dir: Path, version: str) -> None:
    install_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        install_dir / "version.json",
        {"version": version, "build": "100", "release_date": "2026-11-18"},
    )
    (install_dir / "app.exe").write_bytes(b"APP-BINARY-" + version.encode())
    (install_dir / "resources.dat").write_bytes(b"resources-" + version.encode())


def run(installed: str, available: str) -> int:
    """Run the simulated update flow and return a process exit code."""
    reporter = Reporter()
    sandbox = Path(tempfile.mkdtemp(prefix="bup_update_sim_"))
    install_dir = sandbox / "install"
    server_dir = sandbox / "server"
    cache_dir = sandbox / "cache"
    server_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Current install.
    _make_install(install_dir, installed)

    # New package (what the "server" would serve).
    new_payload = {
        "version.json": json.dumps(
            {"version": available, "build": "101", "release_date": "2026-12-01"}
        ),
        "app.exe": "APP-BINARY-" + available,
        "resources.dat": "resources-" + available,
        "new_feature.txt": "brand new feature",
    }
    package_path = server_dir / f"app-{available}.zip"
    _make_zip(package_path, new_payload)
    digest = hashlib.sha256(package_path.read_bytes()).hexdigest()

    # Remote manifest (GitHub Releases schema: app_name + latest_version +
    # release_date + download_url + sha256 + release_notes list).
    manifest_path = server_dir / "manifest.json"
    _write_json(
        manifest_path,
        {
            "app_name": "ParseCraft",
            "latest_version": available,
            "build": "101",
            "release_date": "2026-12-01",
            "download_url": package_path.as_uri(),
            "sha256": digest,
            "size": package_path.stat().st_size,
            "min_version": "1.0.0",
            "package_type": "zip",
            "release_notes": [
                "Added new parser features",
                "Fixed LR table generation",
            ],
        },
    )

    print(f"Simulating update: installed={installed} available={available}")
    print(f"Sandbox: {sandbox}\n")

    # 1. Detection ------------------------------------------------------
    manifest = check_for_update(installed, url=manifest_path.as_uri())
    if manifest is None:
        reporter.check(
            "Detection: no update (already up to date)",
            compare_versions(installed, available) >= 0,
            f"installed={installed} available={available}",
        )
        print("\nNo update available; nothing to do.")
        return 0 if reporter.failures == 0 else 1
    reporter.check(
        "Detection: newer version found",
        manifest.version == available,
        f"manifest={manifest.version}",
    )
    reporter.check(
        "Notification: release notes available",
        bool(manifest.release_notes),
        f"notes_lines={len(manifest.release_notes.splitlines())}",
    )

    # 2. Download -------------------------------------------------------
    downloaded = cache_dir / package_path.name
    download(manifest.download_url, downloaded, expected_size=manifest.size)
    reporter.check("Download: file exists", downloaded.exists())
    reporter.check(
        "Download: size matches", downloaded.stat().st_size == package_path.stat().st_size
    )

    # 3. Integrity verification ----------------------------------------
    try:
        verify_sha256(downloaded, manifest.sha256)
        reporter.check("Verification: SHA-256 matches", True)
    except Exception as exc:  # noqa: BLE001
        reporter.check("Verification: SHA-256 matches", False, str(exc))

    # 4. Install (with backup) -----------------------------------------
    result = apply_zip_update(downloaded, install_dir, backup=True)
    reporter.check("Install: applied", result.success, result.error or "")
    reporter.check("Install: backup created", result.backup_dir is not None and result.backup_dir.exists())
    new_version = json.loads((install_dir / "version.json").read_text())["version"]
    reporter.check(
        "Install: version updated",
        new_version == available,
        f"version.json={new_version}",
    )
    reporter.check(
        "Install: new files present", (install_dir / "new_feature.txt").exists()
    )
    reporter.check(
        "Restart: relaunch ready",
        (install_dir / "app.exe").exists()
        and (install_dir / "app.exe").read_bytes() == b"APP-BINARY-" + available.encode(),
    )

    # 5. Rollback on a corrupt package ---------------------------------
    bad_install = sandbox / "install_bad"
    _make_install(bad_install, installed)
    bad_package = sandbox / "corrupt.zip"
    bad_package.write_bytes(b"this is not a valid zip")
    bad_result = apply_zip_update(bad_package, bad_install, backup=True)
    reporter.check("Rollback: failed update rejected", bad_result.success is False)
    reporter.check(
        "Rollback: original files intact",
        (bad_install / "app.exe").read_bytes() == b"APP-BINARY-" + installed.encode(),
    )
    reporter.check(
        "Rollback: original version intact",
        json.loads((bad_install / "version.json").read_text())["version"] == installed,
    )

    # 6. Version comparison sanity -------------------------------------
    reporter.check(
        "Version compare: available > installed",
        compare_versions(available, installed) > 0,
    )

    print()
    if reporter.failures:
        print(f"RESULT: {reporter.failures} check(s) FAILED")
        return 1
    print("RESULT: ALL CHECKS PASSED")
    return 0


def main(argv=None) -> int:
    """Parse arguments and run the simulation."""
    parser = argparse.ArgumentParser(description="Simulate the update workflow")
    parser.add_argument("--installed", default="1.0.0", help="Installed version")
    parser.add_argument("--available", default="1.1.0", help="Available version")
    args = parser.parse_args(argv)
    return run(args.installed, args.available)


if __name__ == "__main__":
    sys.exit(main())