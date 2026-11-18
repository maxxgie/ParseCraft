"""Semantic versioning and canonical application metadata.

The application version follows semantic versioning (``MAJOR.MINOR.PATCH``)
with an optional pre-release suffix (for example ``1.2.0-rc.1``). The update
system compares versions numerically so that ``1.10.0`` is correctly treated as
newer than ``1.9.0``.

This module is the single source of truth for the application name, version,
and organization. ``gui/settings.py`` re-exports these values for backward
compatibility.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Canonical application metadata
# ---------------------------------------------------------------------------
APP_NAME = "ParseCraft"
APP_VERSION = "1.0.0"
APP_ORGANIZATION = "Compiler Construction"

# Build number and release date. These are overridden by ``version.json`` when
# that file is present (packaged builds ship it next to the executable).
BUILD_NUMBER = "100"
RELEASE_DATE = ""

# Update channel. Packagers may override this (e.g. "beta") per build.
UPDATE_CHANNEL = "stable"

# GitHub Releases backend. ParseCraft is hosted in the ``maxxgie/ParseCraft``
# repository; the application itself lives in the ``bottom_up_parser_simulator``
# subdirectory, so the manifest is read from that path on the ``main`` branch.
# Users can override the resolved URL via the ``BUP_UPDATES_URL`` environment
# variable or the in-app setting.
GITHUB_REPO_OWNER = "maxxgie"
GITHUB_REPO_NAME = "ParseCraft"
GITHUB_REPO = f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"

# Path (within the repository) to the directory that contains ``manifest.json``.
GITHUB_REPO_SUBDIR = "bottom_up_parser_simulator"

# Default update manifest URL (GitHub raw file). Resolution priority is:
# user setting -> BUP_UPDATES_URL environment variable -> this default.
DEFAULT_MANIFEST_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/"
    f"{GITHUB_REPO_SUBDIR}/manifest.json"
)

# Name of the central version file.
VERSION_FILENAME = "version.json"


def _version_file_candidates() -> list[Path]:
    """Return candidate paths for ``version.json``, in priority order.

    Returns:
        A list of candidate paths (may not all exist).
    """
    candidates: list[Path] = []
    env_path = os.environ.get("BUP_VERSION_FILE")
    if env_path:
        candidates.append(Path(env_path))
    if getattr(sys, "frozen", False):
        # Packaged: next to the executable (and in the PyInstaller bundle dir).
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / VERSION_FILENAME)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / VERSION_FILENAME)
    # Source checkout: project root (parent of ``core/``).
    candidates.append(Path(__file__).resolve().parent.parent / VERSION_FILENAME)
    return candidates


def _load_version_file() -> Dict[str, Any]:
    """Load and parse ``version.json`` from the first readable candidate.

    Returns:
        The parsed mapping, or an empty dict if no file is found/readable.
    """
    for candidate in _version_file_candidates():
        try:
            if candidate.is_file():
                with candidate.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def _apply_version_file() -> None:
    """Override module-level metadata from ``version.json`` when available."""
    global APP_VERSION, BUILD_NUMBER, RELEASE_DATE, UPDATE_CHANNEL
    data = _load_version_file()
    if not data:
        return
    version = str(data.get("version", "")).strip()
    if version:
        APP_VERSION = version
    build = data.get("build")
    if build is not None and str(build).strip():
        BUILD_NUMBER = str(build).strip()
    release_date = str(data.get("release_date", "")).strip()
    if release_date:
        RELEASE_DATE = release_date
    channel = str(data.get("channel", "")).strip()
    if channel:
        UPDATE_CHANNEL = channel


_apply_version_file()


def read_installed_version() -> Dict[str, Any]:
    """Return the installed version metadata.

    Reads ``version.json`` when present and falls back to the built-in
    constants. This is what the application calls at startup to learn its own
    installed version, build, and release date.

    Returns:
        A dict with keys ``version``, ``build``, ``release_date``, ``channel``,
        and ``source`` (the path of the version file, if one was read).
    """
    data = _load_version_file()
    source = ""
    for candidate in _version_file_candidates():
        try:
            if candidate.is_file():
                source = str(candidate)
                break
        except OSError:
            continue
    version = str(data.get("version", "")).strip() or APP_VERSION
    build = data.get("build")
    return {
        "version": version,
        "build": str(build).strip() if build is not None and str(build).strip() else BUILD_NUMBER,
        "release_date": str(data.get("release_date", "")).strip() or RELEASE_DATE,
        "channel": str(data.get("channel", "")).strip() or UPDATE_CHANNEL,
        "source": source,
    }

# Semantic version pattern: MAJOR.MINOR.PATCH with optional pre-release.
_VERSION_RE = re.compile(
    r"^\s*v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?\s*$"
)


class VersionError(ValueError):
    """Raised when a version string cannot be parsed."""


@dataclass(frozen=True)
class Version:
    """A parsed semantic version.

    Attributes:
        major: Major version number.
        minor: Minor version number.
        patch: Patch version number.
        prerelease: Optional pre-release identifier (e.g. ``rc.1``).
    """

    major: int
    minor: int
    patch: int
    prerelease: str = ""

    @classmethod
    def parse(cls, text: str) -> "Version":
        """Parse a semantic version string.

        Args:
            text: Version string such as ``"1.2.3"`` or ``"1.2.3-rc.1"``.

        Returns:
            The parsed :class:`Version`.

        Raises:
            VersionError: If the string is not a valid semantic version.
        """
        match = _VERSION_RE.match(text or "")
        if not match:
            raise VersionError(f"Invalid version string: {text!r}")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=match.group("prerelease") or "",
        )

    @property
    def core(self) -> Tuple[int, int, int]:
        """Return the ``(major, minor, patch)`` tuple."""
        return (self.major, self.minor, self.patch)

    def is_prerelease(self) -> bool:
        """Return ``True`` if this is a pre-release version."""
        return bool(self.prerelease)

    def is_newer_than(self, other: "Version") -> bool:
        """Return ``True`` if this version is strictly newer than ``other``."""
        return compare_versions(self, other) > 0

    def __str__(self) -> str:
        """Return the canonical string form of the version."""
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += f"-{self.prerelease}"
        return text


def parse_version(text: str) -> Version:
    """Parse a semantic version string.

    Args:
        text: Version string.

    Returns:
        The parsed :class:`Version`.
    """
    return Version.parse(text)


def current_version() -> Version:
    """Return the currently installed application version.

    Returns:
        The :class:`Version` parsed from :data:`APP_VERSION`.
    """
    return Version.parse(APP_VERSION)


def _compare_core(a: Version, b: Version) -> int:
    """Compare the numeric core of two versions."""
    if a.core < b.core:
        return -1
    if a.core > b.core:
        return 1
    return 0


def compare_versions(a: "Version | str", b: "Version | str") -> int:
    """Compare two versions.

    Pre-release versions sort *before* their corresponding release (per
    semver: ``1.0.0-rc.1`` < ``1.0.0``). Pre-release identifiers are compared
    using a simplified rule: numeric identifiers compare numerically and
    alphanumeric identifiers compare lexically, with numeric identifiers
    sorting before alphanumeric ones.

    Args:
        a: First version (or version string).
        b: Second version (or version string).

    Returns:
        ``-1`` if ``a < b``, ``0`` if equal, ``1`` if ``a > b``.

    Raises:
        VersionError: If either argument cannot be parsed.
    """
    va = a if isinstance(a, Version) else Version.parse(a)
    vb = b if isinstance(b, Version) else Version.parse(b)

    core = _compare_core(va, vb)
    if core != 0:
        return core

    # Same core: a version without pre-release is newer than one with.
    if not va.prerelease and not vb.prerelease:
        return 0
    if not va.prerelease:
        return 1
    if not vb.prerelease:
        return -1

    a_parts = va.prerelease.split(".")
    b_parts = vb.prerelease.split(".")
    for a_part, b_part in zip(a_parts, b_parts):
        result = _compare_prerelease_part(a_part, b_part)
        if result != 0:
            return result
    # All shared parts equal: the longer identifier list is newer.
    if len(a_parts) < len(b_parts):
        return -1
    if len(a_parts) > len(b_parts):
        return 1
    return 0


def _compare_prerelease_part(a: str, b: str) -> int:
    """Compare a single dot-separated pre-release identifier."""
    a_num = a.isdigit()
    b_num = b.isdigit()
    if a_num and b_num:
        ai, bi = int(a), int(b)
        return (ai > bi) - (ai < bi)
    if a_num and not b_num:
        return -1  # numeric identifiers have lower precedence
    if not a_num and b_num:
        return 1
    return (a > b) - (a < b)


def is_newer(candidate: "Version | str", installed: "Version | str | None" = None) -> bool:
    """Return ``True`` if ``candidate`` is newer than ``installed``.

    Args:
        candidate: The available (candidate) version.
        installed: The installed version. Defaults to :func:`current_version`.

    Returns:
        ``True`` if ``candidate`` is strictly newer than ``installed``.
    """
    if installed is None:
        installed = current_version()
    return compare_versions(candidate, installed) > 0


def format_version(version: "Version | str") -> str:
    """Return a display string for a version.

    Args:
        version: A :class:`Version` or version string.

    Returns:
        The canonical version string.
    """
    return str(version if isinstance(version, Version) else Version.parse(version))