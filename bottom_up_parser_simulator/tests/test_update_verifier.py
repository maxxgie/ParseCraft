"""Tests for update package integrity verification."""

from __future__ import annotations

import hashlib

import pytest

from core.update.verifier import (
    VerificationError,
    sha256_bytes,
    sha256_file,
    verify_package,
    verify_sha256,
)


def test_sha256_bytes_matches_hashlib():
    data = b"hello world"
    assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()


def test_sha256_file_matches_hashlib(tmp_path):
    path = tmp_path / "file.bin"
    payload = b"some binary content" * 100
    path.write_bytes(payload)
    assert sha256_file(path) == hashlib.sha256(payload).hexdigest()


def test_verify_sha256_success(tmp_path):
    path = tmp_path / "pkg.zip"
    payload = b"package-bytes"
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    assert verify_sha256(path, digest) is True


def test_verify_sha256_mismatch_raises(tmp_path):
    path = tmp_path / "pkg.zip"
    path.write_bytes(b"package-bytes")
    with pytest.raises(VerificationError):
        verify_sha256(path, "0" * 64)


def test_verify_sha256_missing_file_raises(tmp_path):
    with pytest.raises(VerificationError):
        verify_sha256(tmp_path / "missing.zip", "a" * 64)


def test_verify_sha256_empty_expected_raises(tmp_path):
    path = tmp_path / "pkg.zip"
    path.write_bytes(b"x")
    with pytest.raises(VerificationError):
        verify_sha256(path, "")


def test_verify_package_integrity_only(tmp_path):
    path = tmp_path / "pkg.zip"
    payload = b"package"
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    verify_package(path, digest)  # no signature -> integrity only
    assert True


def test_verify_package_detects_corruption(tmp_path):
    path = tmp_path / "pkg.zip"
    path.write_bytes(b"original")
    digest = hashlib.sha256(b"original").hexdigest()
    # Corrupt the file after computing the expected digest.
    path.write_bytes(b"tampered!")
    with pytest.raises(VerificationError):
        verify_package(path, digest)