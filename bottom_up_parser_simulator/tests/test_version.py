"""Tests for semantic versioning helpers."""

from __future__ import annotations

import pytest

from core import version as v


def test_parse_simple():
    ver = v.Version.parse("1.2.3")
    assert ver.major == 1 and ver.minor == 2 and ver.patch == 3
    assert ver.prerelease == ""
    assert str(ver) == "1.2.3"


def test_parse_with_v_prefix_and_prerelease():
    ver = v.Version.parse("v2.0.0-rc.1")
    assert ver.major == 2
    assert ver.prerelease == "rc.1"
    assert str(ver) == "2.0.0-rc.1"


def test_parse_invalid_raises():
    with pytest.raises(v.VersionError):
        v.Version.parse("1.2")
    with pytest.raises(v.VersionError):
        v.Version.parse("abc")
    with pytest.raises(v.VersionError):
        v.Version.parse("")


def test_compare_patch():
    assert v.compare_versions("1.0.0", "1.0.1") == -1
    assert v.compare_versions("1.0.1", "1.0.0") == 1
    assert v.compare_versions("1.0.0", "1.0.0") == 0


def test_compare_numeric_not_lexical():
    # 1.10.0 must be newer than 1.9.0.
    assert v.compare_versions("1.9.0", "1.10.0") == -1
    assert v.is_newer("1.10.0", "1.9.0") is True


def test_prerelease_sorts_before_release():
    assert v.compare_versions("1.0.0-rc.1", "1.0.0") == -1
    assert v.compare_versions("1.0.0", "1.0.0-rc.1") == 1


def test_prerelease_ordering():
    assert v.compare_versions("1.0.0-alpha", "1.0.0-beta") == -1
    assert v.compare_versions("1.0.0-rc.2", "1.0.0-rc.10") == -1
    assert v.compare_versions("1.0.0-alpha.1", "1.0.0-alpha") == 1


def test_is_newer_uses_current_when_omitted():
    assert v.is_newer("999.0.0") is True
    assert v.is_newer("0.0.1") is False


def test_current_version_matches_constant():
    assert str(v.current_version()) == v.APP_VERSION


def test_format_version():
    assert v.format_version("1.2.3") == "1.2.3"
    assert v.format_version(v.Version(2, 0, 0)) == "2.0.0"


# ----------------------------------------------------------------------
# version.json
# ----------------------------------------------------------------------
def test_read_installed_version_from_file(tmp_path, monkeypatch):
    import json

    version_file = tmp_path / "version.json"
    version_file.write_text(
        json.dumps(
            {
                "version": "3.4.5",
                "build": "999",
                "release_date": "2027-01-02",
                "channel": "beta",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BUP_VERSION_FILE", str(version_file))

    info = v.read_installed_version()
    assert info["version"] == "3.4.5"
    assert info["build"] == "999"
    assert info["release_date"] == "2027-01-02"
    assert info["channel"] == "beta"
    assert info["source"] == str(version_file)


def test_read_installed_version_falls_back(tmp_path, monkeypatch):
    # Isolate from the real version.json so built-in defaults are used.
    monkeypatch.setattr(v, "_version_file_candidates", lambda: [tmp_path / "missing.json"])
    info = v.read_installed_version()
    assert info["version"] == v.APP_VERSION
    assert info["build"] == v.BUILD_NUMBER
    assert info["source"] == ""


def test_build_and_release_constants_exist():
    assert isinstance(v.BUILD_NUMBER, str) and v.BUILD_NUMBER
    assert isinstance(v.RELEASE_DATE, str)