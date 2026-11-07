"""On-disk cache for successful HTTP responses.

Privacy and security notes:

* Cache keys are hashes computed *without* secret parameters, so API
  keys are never written to disk.
* Only the response body is stored: no request or response headers.
* The cache file lives in the user's private cache directory. It still
  reveals which locations and dates were queried, so it is disabled by
  default (``NABIA_CACHE_ENABLED``).
"""

import hashlib
import json
import os
import sqlite3
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Protocol

from nabia.core.security import secret_params

_SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    key        TEXT PRIMARY KEY,
    body       BLOB NOT NULL,
    expires_at REAL NOT NULL
)
"""


class ResponseCache(Protocol):
    """Minimal interface the HTTP client needs from a cache backend."""

    def get(self, key: str) -> bytes | None:
        """Return the cached body, or ``None`` if absent or expired."""
        ...

    def set(self, key: str, body: bytes, ttl_seconds: float) -> None:
        """Store ``body`` under ``key`` for ``ttl_seconds``."""
        ...


def make_cache_key(
    method: str,
    url: str,
    params: Mapping[str, str | int | float],
) -> str:
    """Build a stable cache key that excludes secret parameters."""
    secrets = secret_params()
    safe_params = sorted(
        (key, str(value))
        for key, value in params.items()
        if key.lower() not in secrets
    )
    payload = json.dumps([method.upper(), url, safe_params])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SQLiteResponseCache:
    """Response cache backed by a single SQLite file.

    A connection is opened per operation, which keeps the class safe to
    share between threads at a negligible cost for this workload.

    Args:
        path: SQLite file; parent directories are created on demand.
        clock: Time source in seconds, injectable for tests.
    """

    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._path = path
        self._clock = clock
        self._initialized = False

    @property
    def path(self) -> Path:
        """Location of the SQLite file."""
        return self._path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if not self._initialized:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self._path)) as conn, conn:
            if not self._initialized:
                conn.execute(_SCHEMA)
                self._restrict_permissions()
                self._initialized = True
            yield conn

    def _restrict_permissions(self) -> None:
        # Owner read/write only on POSIX; Windows relies on the
        # per-user profile directory ACLs.
        if os.name == "posix":
            self._path.chmod(0o600)

    def get(self, key: str) -> bytes | None:
        """Return the cached body, or ``None`` if absent or expired."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT body, expires_at FROM responses WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            body, expires_at = row
            if expires_at <= self._clock():
                conn.execute("DELETE FROM responses WHERE key = ?", (key,))
                return None
            return bytes(body)

    def set(self, key: str, body: bytes, ttl_seconds: float) -> None:
        """Store ``body`` under ``key`` for ``ttl_seconds``."""
        if ttl_seconds <= 0:
            return
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO responses VALUES (?, ?, ?)",
                (key, body, self._clock() + ttl_seconds),
            )

    def purge_expired(self) -> int:
        """Delete expired entries and return how many were removed."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM responses WHERE expires_at <= ?",
                (self._clock(),),
            )
            return cursor.rowcount

    def clear(self) -> None:
        """Delete every cached entry."""
        with self._connect() as conn:
            conn.execute("DELETE FROM responses")
