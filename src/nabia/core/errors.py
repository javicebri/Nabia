"""Exception hierarchy for Nabia.

Every exception raised on purpose by Nabia derives from
:class:`NabiaError`, so consumers can catch library errors with a
single ``except`` clause. Messages never include secrets: URLs are
redacted before they reach an exception.
"""


class NabiaError(Exception):
    """Base class for all errors raised by Nabia."""


class ConfigurationError(NabiaError):
    """Invalid or missing configuration (e.g. a required API key)."""


class MissingDependencyError(NabiaError, ImportError):
    """An optional dependency (``nabia[extra]``) is missing."""


class UnsupportedVariableError(NabiaError, ValueError):
    """A variable is not mapped for the provider/resolution."""


class UnitConversionError(NabiaError, ValueError):
    """No conversion is defined between two units."""


class ProviderError(NabiaError):
    """Base class for failures while talking to a remote provider.

    Args:
        message: Human-readable description, free of secrets.
        provider: Provider identifier (e.g. ``"open_meteo"``).
        url: Request URL, already redacted.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.url = url


class ProviderConnectionError(ProviderError):
    """Network failure or timeout persisting after all retries."""


class ProviderHTTPError(ProviderError):
    """The provider answered with an unexpected HTTP status code."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int,
        url: str | None = None,
    ) -> None:
        super().__init__(message, provider=provider, url=url)
        self.status_code = status_code


class AuthenticationError(ProviderHTTPError):
    """The provider rejected the credentials (HTTP 401/403)."""


class RateLimitError(ProviderHTTPError):
    """The provider throttled the client (HTTP 429)."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int = 429,
        url: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(
            message, provider=provider, status_code=status_code, url=url
        )
        self.retry_after = retry_after


class ProviderServerError(ProviderHTTPError):
    """The provider failed on its side (HTTP 5xx)."""


class NoDataError(ProviderError):
    """A requested variable came back with no values at all.

    Raised instead of returning a column of ``None``: the selected
    source may not provide the variable, or the period may not be
    available yet. Partially missing values are still returned.
    """


class ProviderContractError(ProviderError):
    """The response does not match what Nabia expects.

    This usually means the upstream API changed (renamed fields, new
    structure). It is raised loudly on purpose: returning silently
    wrong data is worse than failing.
    """


class UnitMismatchError(ProviderContractError):
    """The provider reported a different unit than the mapping table."""
