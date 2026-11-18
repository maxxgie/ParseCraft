"""Update package: manifest parsing, download, verification, installation.

This package implements the automatic update system:

* :mod:`core.update.manifest` — parse and validate release manifests.
* :mod:`core.update.checker` — fetch and compare manifests.
* :mod:`core.update.downloader` — download packages with progress/cancel.
* :mod:`core.update.verifier` — SHA-256 integrity and optional signatures.
* :mod:`core.update.installer` — apply updates with backup and rollback.
* :mod:`core.update.manager` — high-level orchestration facade.
"""

from core.update.checker import (
    CheckError,
    check_for_update,
    fetch_manifest,
    resolve_manifest_url,
)
from core.update.downloader import (
    DownloadCancelled,
    DownloadError,
    download,
    download_to_cache,
    filename_from_url,
)
from core.update.installer import (
    ApplyResult,
    InstallError,
    PendingUpdate,
    apply_pending_update,
    apply_zip_update,
    clear_pending_update,
    launch_installer,
    launch_updater,
    read_pending_update,
    relaunch_application,
    write_pending_update,
)
from core.update.history import UpdateHistoryStore, get_history_path
from core.update.manager import UpdateManager
from core.update.manifest import (
    ManifestError,
    ReleaseManifest,
    parse_manifest,
)
from core.update.verifier import (
    VerificationError,
    sha256_bytes,
    sha256_file,
    verify_package,
    verify_sha256,
    verify_signature,
)

__all__ = [
    # manifest
    "ManifestError",
    "ReleaseManifest",
    "parse_manifest",
    # checker
    "CheckError",
    "check_for_update",
    "fetch_manifest",
    "resolve_manifest_url",
    # downloader
    "DownloadCancelled",
    "DownloadError",
    "download",
    "download_to_cache",
    "filename_from_url",
    # verifier
    "VerificationError",
    "sha256_bytes",
    "sha256_file",
    "verify_package",
    "verify_sha256",
    "verify_signature",
    # installer
    "ApplyResult",
    "InstallError",
    "PendingUpdate",
    "apply_pending_update",
    "apply_zip_update",
    "clear_pending_update",
    "launch_installer",
    "launch_updater",
    "read_pending_update",
    "relaunch_application",
    "write_pending_update",
    # history
    "UpdateHistoryStore",
    "get_history_path",
    # manager
    "UpdateManager",
]