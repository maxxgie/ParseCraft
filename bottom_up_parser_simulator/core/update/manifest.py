"""Update manifest parsing and validation.

An update manifest is a JSON document served by the update server that
describes the latest available release. Example::

    {
      "version": "1.2.0",
      "release_date": "2026-11-18",
      "release_notes": "- Added automatic updates\\n- Fixed crash on export",
      "download_url": "https://example.com/ParseCraft-1.2.0-win64.zip",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb924...",
      "size": 15728640,
      "min_version": "1.0.0",
      "mandatory": false,
      "package_type": "zip"
    }

The manifest is deliberately small and dependency-free so it can be fetched and
validated with the standard library only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from core.version import Version, VersionError, is_newer


class ManifestError(ValueError):
    """Raised when a manifest is malformed or invalid."""


# Recognised package types.
PACKAGE_TYPE_ZIP = "zip"
PACKAGE_TYPE_INSTALLER = "installer"
VALID_PACKAGE_TYPES = frozenset({PACKAGE_TYPE_ZIP, PACKAGE_TYPE_INSTALLER})


@dataclass
class ReleaseManifest:
    """A parsed update manifest.

    The manifest accepts two equivalent version keys (``version`` and
    ``latest_version``) and either a string or a list of strings for
    ``release_notes`` so it can consume the documented server schema::

        {
          "latest_version": "1.1.0",
          "download_url": "https://server.com/releases/app-1.1.0.exe",
          "release_notes": ["Added new parser features", "Fixed LR table generation"]
        }

    Attributes:
        app_name: Optional application name advertised by the manifest.
        version: The release version string.
        build: Optional build number associated with the release.
        release_date: Release date (ISO-8601 date or free text).
        release_notes: Markdown/plain-text release notes.
        download_url: URL to download the update package.
        sha256: Expected SHA-256 hex digest of the package.
        size: Package size in bytes (may be 0 if unknown).
        min_version: Minimum installed version required to apply this update.
        mandatory: Whether the update is mandatory.
        package_type: Either ``"zip"`` or ``"installer"``.
    """

    version: str
    app_name: str = ""
    build: str = ""
    release_date: str = ""
    release_notes: str = ""
    download_url: str = ""
    sha256: str = ""
    size: int = 0
    min_version: str = ""
    mandatory: bool = False
    package_type: str = PACKAGE_TYPE_ZIP

    def __post_init__(self) -> None:
        """Validate core invariants after construction."""
        if not self.version:
            raise ManifestError("Manifest is missing required field: version")
        # Validate that the version is parseable.
        try:
            Version.parse(self.version)
        except VersionError as exc:
            raise ManifestError(str(exc)) from exc
        if self.package_type not in VALID_PACKAGE_TYPES:
            raise ManifestError(
                f"Unsupported package_type: {self.package_type!r} "
                f"(expected one of {sorted(VALID_PACKAGE_TYPES)})"
            )
        if self.size < 0:
            raise ManifestError("Manifest field 'size' must be non-negative")
        if self.sha256:
            self.sha256 = self.sha256.strip().lower()
            if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
                raise ManifestError("Manifest field 'sha256' must be a 64-character hex digest")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReleaseManifest":
        """Build a manifest from a parsed JSON object.

        Args:
            data: The decoded JSON object.

        Returns:
            The parsed :class:`ReleaseManifest`.

        Raises:
            ManifestError: If required fields are missing or invalid.
        """
        if not isinstance(data, dict):
            raise ManifestError("Manifest root must be a JSON object")
        version = str(data.get("version", "")).strip()
        if not version:
            # Accept the documented ``latest_version`` key as an alias.
            version = str(data.get("latest_version", "")).strip()
        return cls(
            version=version,
            app_name=str(data.get("app_name", "")).strip(),
            build=str(data.get("build", "")).strip(),
            release_date=str(data.get("release_date", "")),
            release_notes=_coerce_notes(data.get("release_notes", "")),
            download_url=str(data.get("download_url", "")),
            sha256=str(data.get("sha256", "")),
            size=_coerce_int(data.get("size", 0)),
            min_version=str(data.get("min_version", "")),
            mandatory=bool(data.get("mandatory", False)),
            package_type=str(data.get("package_type", PACKAGE_TYPE_ZIP)).strip().lower(),
        )

    @classmethod
    def from_json(cls, text: str) -> "ReleaseManifest":
        """Parse a manifest from a JSON string.

        Args:
            text: The JSON document.

        Returns:
            The parsed :class:`ReleaseManifest`.

        Raises:
            ManifestError: If the JSON is invalid or the manifest is malformed.
        """
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"Invalid manifest JSON: {exc}") from exc
        return cls.from_dict(data)

    # -- comparison ------------------------------------------------------
    def is_newer_than(self, installed: "Version | str") -> bool:
        """Return ``True`` if this release is newer than ``installed``.

        Args:
            installed: The installed version.

        Returns:
            ``True`` if this manifest's version is strictly newer.
        """
        try:
            return is_newer(self.version, installed)
        except VersionError:
            return False

    def is_compatible_with(self, installed: "Version | str") -> bool:
        """Return ``True`` if ``installed`` meets the manifest's ``min_version``.

        Args:
            installed: The installed version.

        Returns:
            ``True`` if the installed version is greater than or equal to
            ``min_version`` (or no minimum is specified).
        """
        if not self.min_version:
            return True
        try:
            from core.version import compare_versions

            return compare_versions(installed, self.min_version) >= 0
        except VersionError:
            return False

    def requires_download(self) -> bool:
        """Return ``True`` if this manifest points at a downloadable package."""
        return bool(self.download_url)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict for this manifest."""
        return {
            "version": self.version,
            "app_name": self.app_name,
            "build": self.build,
            "release_date": self.release_date,
            "release_notes": self.release_notes,
            "download_url": self.download_url,
            "sha256": self.sha256,
            "size": self.size,
            "min_version": self.min_version,
            "mandatory": self.mandatory,
            "package_type": self.package_type,
        }


def _coerce_notes(value: Any) -> str:
    """Normalize release notes to a single string.

    Accepts either a string or a list of strings (the documented server schema)
    and renders a list as a bullet list.

    Args:
        value: Raw ``release_notes`` value.

    Returns:
        A string suitable for display.
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(f"- {item}" if not item.startswith("-") else item for item in items)
    return str(value)


def _coerce_int(value: Any) -> int:
    """Coerce a value to int, defaulting to 0 for non-numeric input.

    Negative values are preserved so that :meth:`ReleaseManifest.__post_init__`
    can reject them.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_manifest(text: str) -> ReleaseManifest:
    """Parse a manifest from a JSON string.

    Args:
        text: The JSON document.

    Returns:
        The parsed :class:`ReleaseManifest`.
    """
    return ReleaseManifest.from_json(text)