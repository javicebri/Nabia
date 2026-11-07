"""TLS certificate verification policy.

``system`` (default) verifies certificates against the operating
system trust store through :mod:`truststore`, as browsers and pip do.
This keeps Nabia working behind antivirus HTTPS scanning or corporate
proxies whose root certificates are installed in the OS.

``truststore`` cannot read the Android store: on Android (and any
platform not listed below) Nabia falls back to the Mozilla bundle from
``certifi``, which is httpx's default. Verification is never disabled.
"""

import logging
import ssl
import sys
from enum import StrEnum

import truststore

logger = logging.getLogger(__name__)

_SYSTEM_STORE_PLATFORMS = frozenset({"win32", "darwin", "linux"})


class SslTrust(StrEnum):
    """Source of trusted root certificates."""

    SYSTEM = "system"
    CERTIFI = "certifi"


def system_store_supported() -> bool:
    """Return whether truststore can read this platform's store."""
    # Android reports sys.platform == "linux" before Python 3.13.
    if hasattr(sys, "getandroidapilevel"):
        return False
    return sys.platform in _SYSTEM_STORE_PLATFORMS


def build_verify(trust: SslTrust) -> ssl.SSLContext | bool:
    """Return the ``verify`` argument for :class:`httpx.Client`.

    Returns:
        An SSL context bound to the system store, or ``True`` to use
        httpx's default ``certifi`` bundle.
    """
    if trust is SslTrust.SYSTEM:
        if system_store_supported():
            return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        logger.info(
            "System trust store not supported on %s; using certifi.",
            sys.platform,
        )
    return True
