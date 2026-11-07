"""Helpers that keep credentials out of logs, errors and caches.

Two leak vectors are covered:

* URLs carrying secrets as query parameters (``?apikey=...``) are
  redacted before being logged or attached to exceptions.
* ``httpx`` logs every request URL at INFO level. A filter is installed
  on its logger to redact those records as well.
"""

import logging
import re
from collections.abc import Iterable
from functools import lru_cache
from threading import Lock

import httpx

REDACTED = "***"

#: Query parameter names always treated as secrets (case-insensitive).
DEFAULT_SECRET_PARAMS: frozenset[str] = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "key",
        "password",
        "secret",
        "token",
    }
)

_registry_lock = Lock()
_secret_params: set[str] = set(DEFAULT_SECRET_PARAMS)


def register_secret_params(names: Iterable[str]) -> None:
    """Register extra query parameter names to redact globally."""
    with _registry_lock:
        _secret_params.update(name.lower() for name in names)


def secret_params() -> frozenset[str]:
    """Return every registered secret parameter name (lower case)."""
    with _registry_lock:
        return frozenset(_secret_params)


_USERINFO = re.compile(r"(://)[^/@\s]+@")


@lru_cache(maxsize=8)
def _secret_pattern(names: frozenset[str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(name) for name in sorted(names))
    return re.compile(rf"(?i)([?&;\s]|^)({alternatives})=([^&\s\"']+)")


def redact_text(text: str) -> str:
    """Mask ``name=value`` pairs for secret names inside free text."""
    pattern = _secret_pattern(secret_params())
    return pattern.sub(rf"\1\2={REDACTED}", text)


def redact_url(url: str | httpx.URL) -> str:
    """Return ``url`` with secret query values and user info masked."""
    without_userinfo = _USERINFO.sub(rf"\1{REDACTED}@", str(url))
    return redact_text(without_userinfo)


class SecretRedactingFilter(logging.Filter):
    """Logging filter that redacts secrets from formatted messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Rewrite the record message in place; never drop it."""
        message = record.getMessage()
        redacted = redact_text(message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


_filter = SecretRedactingFilter()


def install_log_redaction(
    logger_names: Iterable[str] = ("httpx", "httpcore"),
) -> None:
    """Attach the redacting filter to library loggers (idempotent)."""
    for name in logger_names:
        logger = logging.getLogger(name)
        if _filter not in logger.filters:
            logger.addFilter(_filter)
