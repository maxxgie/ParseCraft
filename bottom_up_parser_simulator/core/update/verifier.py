"""Integrity and authenticity verification for update packages.

Two layers of protection are provided:

* **Integrity** — a SHA-256 digest of the downloaded package is compared with
  the digest published in the (HTTPS-fetched) manifest. This is mandatory and
  prevents corrupted or truncated downloads from being installed.
* **Authenticity** — an optional detached signature check. If a public key is
  configured and the ``cryptography`` package is available, an Ed25519
  signature is verified. When no key is configured, authenticity relies on the
  transport security (HTTPS) of the manifest and package download, which is the
  standard trust model for update systems without a full code-signing PKI.

All failures raise :class:`VerificationError` so callers can abort safely.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional


class VerificationError(Exception):
    """Raised when integrity or authenticity verification fails."""


_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def sha256_file(path: "str | Path") -> str:
    """Compute the SHA-256 hex digest of a file.

    Args:
        path: Path to the file.

    Returns:
        The lowercase hex digest.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute the SHA-256 hex digest of a byte string.

    Args:
        data: The bytes to hash.

    Returns:
        The lowercase hex digest.
    """
    return hashlib.sha256(data).hexdigest()


def verify_sha256(path: "str | Path", expected: str) -> bool:
    """Verify a file's SHA-256 digest against an expected value.

    Args:
        path: Path to the file.
        expected: Expected lowercase hex digest.

    Returns:
        ``True`` if the digest matches.

    Raises:
        VerificationError: If the file is missing or the digest does not match.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise VerificationError(f"Cannot verify missing file: {file_path}")
    expected = (expected or "").strip().lower()
    if not expected:
        raise VerificationError("No expected SHA-256 digest provided")
    actual = sha256_file(file_path)
    if actual != expected:
        raise VerificationError(
            f"Integrity check failed: expected {expected}, computed {actual}"
        )
    return True


def verify_signature(
    package_path: "str | Path",
    signature_path: "str | Path",
    public_key_pem: "str | Path",
) -> bool:
    """Verify a detached Ed25519 signature over a package.

    This requires the optional ``cryptography`` dependency. If it is not
    installed, a :class:`VerificationError` is raised so callers can decide
    whether to abort or continue with integrity-only verification.

    Args:
        package_path: Path to the package file.
        signature_path: Path to the detached signature (raw bytes).
        public_key_pem: Path to the PEM-encoded Ed25519 public key.

    Returns:
        ``True`` if the signature is valid.

    Raises:
        VerificationError: If the dependency is missing or verification fails.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise VerificationError(
            "Signature verification requires the 'cryptography' package"
        ) from exc

    package = Path(package_path)
    signature = Path(signature_path)
    key_file = Path(public_key_pem)
    for required in (package, signature, key_file):
        if not required.exists():
            raise VerificationError(f"Signature verification: missing {required}")

    try:
        public_key = Ed25519PublicKey.from_public_bytes(_load_public_key_bytes(key_file))
        package_bytes = package.read_bytes()
        signature_bytes = signature.read_bytes()
        public_key.verify(signature_bytes, package_bytes)
    except InvalidSignature as exc:
        raise VerificationError("Authenticity check failed: invalid signature") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise VerificationError(f"Authenticity check failed: {exc}") from exc
    return True


def _load_public_key_bytes(key_file: Path) -> bytes:
    """Load raw public key bytes from a PEM or raw file.

    Args:
        key_file: Path to the key file.

    Returns:
        Raw public key bytes (32 bytes for Ed25519).
    """
    data = key_file.read_bytes()
    if b"-----BEGIN" in data:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        key = load_pem_public_key(data)
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        return key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return data


def verify_package(
    path: "str | Path",
    expected_sha256: str,
    signature_path: Optional["str | Path"] = None,
    public_key_pem: Optional["str | Path"] = None,
) -> None:
    """Run the full verification pipeline for a downloaded package.

    Integrity is always checked. Authenticity (signature) is checked only when
    both a signature path and public key are supplied.

    Args:
        path: Path to the downloaded package.
        expected_sha256: Expected SHA-256 digest from the manifest.
        signature_path: Optional detached signature file.
        public_key_pem: Optional PEM public key for signature verification.

    Raises:
        VerificationError: If any check fails.
    """
    verify_sha256(path, expected_sha256)
    if signature_path is not None and public_key_pem is not None:
        verify_signature(path, signature_path, public_key_pem)