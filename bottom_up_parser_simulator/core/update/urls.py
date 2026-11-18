"""URL scheme validation for the update system.

Updates are fetched over HTTPS to protect the manifest and the update package
from tampering in transit. ``file://`` URLs are also accepted strictly for
testing and offline/air-gapped scenarios. Plain ``http://`` is rejected so an
attacker on the network cannot feed the application an unverified package.
"""

from __future__ import annotations

from urllib.parse import urlparse


# Schemes permitted for manifest and package URLs.
ALLOWED_SCHEMES = frozenset({"https", "file"})


def scheme_of(url: str) -> str:
    """Return the lowercase scheme of a URL.

    Args:
        url: The URL to inspect.

    Returns:
        The lowercase scheme (e.g. ``"https"``), or an empty string.
    """
    try:
        return urlparse(url).scheme.lower()
    except ValueError:
        return ""


def is_secure_url(url: str) -> bool:
    """Return ``True`` if the URL uses an allowed (secure) scheme.

    Args:
        url: The URL to check.

    Returns:
        ``True`` for ``https`` and ``file`` URLs, ``False`` otherwise.
    """
    return scheme_of(url) in ALLOWED_SCHEMES