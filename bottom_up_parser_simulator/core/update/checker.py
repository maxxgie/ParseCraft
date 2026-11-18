"""Fetching and parsing update manifests from the update server.

The checker is transport-agnostic: it fetches the manifest JSON from a URL
(``https://`` in production, ``file://`` for tests/offline use) and parses it
into a :class:`~core.update.manifest.ReleaseManifest`. All network and parse
errors are surfaced as :class:`CheckError` so callers can fail gracefully.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from typing import Optional

from core.logging_config import get_logger
from core.update.downloader import validate_download_url
from core.update.manifest import ManifestError, ReleaseManifest
from core.update.urls import is_secure_url
from core.version import DEFAULT_MANIFEST_URL


logger = get_logger(__name__)

# Default network timeout for manifest checks.
DEFAULT_CHECK_TIMEOUT = 15.0


class CheckError(Exception):
    """Raised when the update manifest cannot be retrieved or parsed."""


def resolve_manifest_url(explicit: Optional[str] = None) -> str:
    """Resolve the manifest URL from explicit value, env var, or default.

    Args:
        explicit: An explicit URL (e.g. from preferences).

    Returns:
        The resolved manifest URL.
    """
    if explicit:
        return explicit
    env_url = os.environ.get("BUP_UPDATES_URL")
    if env_url:
        return env_url
    return DEFAULT_MANIFEST_URL


def fetch_manifest(
    url: Optional[str] = None,
    *,
    timeout: float = DEFAULT_CHECK_TIMEOUT,
) -> ReleaseManifest:
    """Fetch and parse the latest release manifest.

    Args:
        url: Manifest URL. Defaults to the resolved default URL.
        timeout: Network timeout in seconds.

    Returns:
        The parsed :class:`ReleaseManifest`.

    Raises:
        CheckError: If the manifest cannot be fetched or parsed.
    """
    resolved = resolve_manifest_url(url)
    if not is_secure_url(resolved):
        raise CheckError(
            f"Refusing to fetch manifest over insecure URL (HTTPS required): {resolved}"
        )
    logger.info("Checking for updates at %s", resolved)
    request = urllib.request.Request(
        resolved, headers={"User-Agent": "ParseCraft"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
    except urllib.error.URLError as exc:
        raise CheckError(f"Failed to reach update server: {exc}") from exc
    except OSError as exc:
        raise CheckError(f"Failed to read update manifest: {exc}") from exc

    try:
        manifest = ReleaseManifest.from_json(body)
    except ManifestError as exc:
        raise CheckError(f"Invalid update manifest: {exc}") from exc
    try:
        validate_download_url(manifest.download_url)
    except ValueError as exc:
        raise CheckError(f"Manifest download_url is invalid: {exc}") from exc
    return manifest


def check_for_update(
    installed: "object | str",
    *,
    url: Optional[str] = None,
    timeout: float = DEFAULT_CHECK_TIMEOUT,
) -> Optional[ReleaseManifest]:
    """Check whether a newer version is available.

    Args:
        installed: The installed version (string or Version).
        url: Optional manifest URL override.
        timeout: Network timeout in seconds.

    Returns:
        A :class:`ReleaseManifest` if a newer version exists, else ``None``.

    Raises:
        CheckError: If the manifest cannot be retrieved or parsed.
    """
    manifest = fetch_manifest(url, timeout=timeout)
    if manifest.is_newer_than(installed) and manifest.is_compatible_with(installed):
        return manifest
    logger.info(
        "No newer version available (installed=%s, latest=%s)", installed, manifest.version
    )
    return None