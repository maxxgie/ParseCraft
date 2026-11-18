"""Tests for update manifest parsing and validation."""

from __future__ import annotations

import json

import pytest

from core.update.manifest import ManifestError, ReleaseManifest, parse_manifest


def _manifest_dict(**overrides):
    data = {
        "version": "1.2.0",
        "release_date": "2026-11-18",
        "release_notes": "- New feature\n- Bug fix",
        "download_url": "https://example.com/app-1.2.0.zip",
        "sha256": "a" * 64,
        "size": 1024,
        "min_version": "1.0.0",
        "mandatory": False,
        "package_type": "zip",
    }
    data.update(overrides)
    return data


def test_parse_valid_manifest():
    manifest = ReleaseManifest.from_dict(_manifest_dict())
    assert manifest.version == "1.2.0"
    assert manifest.size == 1024
    assert manifest.sha256 == "a" * 64
    assert manifest.package_type == "zip"
    assert manifest.mandatory is False


def test_parse_from_json_string():
    manifest = parse_manifest(json.dumps(_manifest_dict()))
    assert manifest.version == "1.2.0"


def test_missing_version_raises():
    with pytest.raises(ManifestError):
        ReleaseManifest.from_dict(_manifest_dict(version=""))


def test_invalid_version_raises():
    with pytest.raises(ManifestError):
        ReleaseManifest.from_dict(_manifest_dict(version="not-a-version"))


def test_invalid_sha256_raises():
    with pytest.raises(ManifestError):
        ReleaseManifest.from_dict(_manifest_dict(sha256="xyz"))


def test_invalid_package_type_raises():
    with pytest.raises(ManifestError):
        ReleaseManifest.from_dict(_manifest_dict(package_type="dmg"))


def test_negative_size_raises():
    with pytest.raises(ManifestError):
        ReleaseManifest.from_dict(_manifest_dict(size=-5))


def test_invalid_json_raises():
    with pytest.raises(ManifestError):
        parse_manifest("{ not json")


def test_is_newer_than():
    manifest = ReleaseManifest.from_dict(_manifest_dict(version="1.2.0"))
    assert manifest.is_newer_than("1.1.0") is True
    assert manifest.is_newer_than("1.2.0") is False
    assert manifest.is_newer_than("1.3.0") is False


def test_is_compatible_with_min_version():
    manifest = ReleaseManifest.from_dict(_manifest_dict(min_version="1.1.0"))
    assert manifest.is_compatible_with("1.0.0") is False
    assert manifest.is_compatible_with("1.1.0") is True
    assert manifest.is_compatible_with("1.2.0") is True


def test_no_min_version_always_compatible():
    manifest = ReleaseManifest.from_dict(_manifest_dict(min_version=""))
    assert manifest.is_compatible_with("0.0.1") is True


def test_requires_download():
    with_url = ReleaseManifest.from_dict(_manifest_dict())
    without_url = ReleaseManifest.from_dict(_manifest_dict(download_url=""))
    assert with_url.requires_download() is True
    assert without_url.requires_download() is False


def test_to_dict_roundtrip():
    manifest = ReleaseManifest.from_dict(_manifest_dict())
    again = ReleaseManifest.from_dict(manifest.to_dict())
    assert again.version == manifest.version
    assert again.sha256 == manifest.sha256


def test_invalid_manifest_root_not_object():
    with pytest.raises(ManifestError):
        ReleaseManifest.from_dict(["not", "a", "dict"])


# ----------------------------------------------------------------------
# Documented server schema
# ----------------------------------------------------------------------
def test_latest_version_alias():
    manifest = ReleaseManifest.from_dict(
        {
            "latest_version": "1.1.0",
            "download_url": "https://server.com/releases/app-1.1.0.exe",
            "release_notes": ["Added new parser features", "Fixed LR table generation"],
        }
    )
    assert manifest.version == "1.1.0"
    assert manifest.download_url.endswith("app-1.1.0.exe")


def test_release_notes_list_becomes_bullet_list():
    manifest = ReleaseManifest.from_dict(
        {"version": "1.1.0", "release_notes": ["Feature A", "Fix B"]}
    )
    assert "- Feature A" in manifest.release_notes
    assert "- Fix B" in manifest.release_notes


def test_release_notes_string_preserved():
    manifest = ReleaseManifest.from_dict({"version": "1.1.0", "release_notes": "single note"})
    assert manifest.release_notes == "single note"


def test_build_field():
    manifest = ReleaseManifest.from_dict({"version": "1.1.0", "build": "101"})
    assert manifest.build == "101"
    assert manifest.to_dict()["build"] == "101"