"""Configuration loaded from environment variables or a ``.env`` file.

Rules:

* Credentials are typed as :class:`pydantic.SecretStr`, so they are
  masked in ``repr()``, logs and tracebacks.
* Credentials never have defaults in code; they come from the
  environment (or the consumer project's ``.env``) only.
* Every remote URL must use HTTPS.
"""

from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from platformdirs import user_cache_path
from pydantic import AfterValidator, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from nabia._meta import __version__
from nabia.core.errors import ConfigurationError
from nabia.core.tls import SslTrust


def _require_https(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise ValueError(f"URL must use https: {url!r}")
    return url


#: String annotated type that only accepts ``https://`` URLs.
HttpsUrl = Annotated[str, AfterValidator(_require_https)]


class EnvSettings(BaseSettings):
    """Base class for every Nabia settings model.

    Subclasses only need to declare ``env_prefix`` in their
    ``model_config``; the rest of the configuration is inherited.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )


def _default_cache_path() -> Path:
    return user_cache_path("nabia", appauthor=False) / "http-cache.sqlite3"


class NabiaSettings(EnvSettings):
    """Settings shared by every provider client (prefix ``NABIA_``).

    Attributes:
        timeout_seconds: Per-request timeout.
        max_retries: Retries for transient failures (network, 429, 5xx).
        user_agent: ``User-Agent`` header sent to every provider.
        cache_enabled: Cache successful responses on disk.
        cache_path: SQLite file used by the response cache.
        cache_ttl_seconds: Lifetime of cached responses.
        ssl_trust: Root certificates used to verify TLS (see
            :mod:`nabia.core.tls`).
    """

    model_config = SettingsConfigDict(env_prefix="NABIA_")

    ssl_trust: SslTrust = SslTrust.SYSTEM
    timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    max_retries: int = Field(default=3, ge=0, le=10)
    user_agent: str = Field(default=f"nabia/{__version__}", min_length=1)
    cache_enabled: bool = False
    cache_path: Path = Field(default_factory=_default_cache_path)
    cache_ttl_seconds: float = Field(default=3600.0, ge=0)


def require_secret(value: SecretStr | None, env_var: str) -> str:
    """Return the plain secret or raise a helpful configuration error.

    Args:
        value: Secret loaded by a settings model, if any.
        env_var: Environment variable the user must define.

    Raises:
        ConfigurationError: If the secret is missing or blank.
    """
    if value is None or not value.get_secret_value().strip():
        raise ConfigurationError(
            f"Missing credential: define {env_var} in the environment "
            "or in the project's .env file."
        )
    return value.get_secret_value()
