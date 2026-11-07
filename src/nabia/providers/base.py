"""Shared lifecycle for provider clients."""

from collections.abc import Iterable
from types import TracebackType
from typing import ClassVar, Self

from nabia.core.config import NabiaSettings
from nabia.core.http import ErrorParser, HttpClient


class BaseClient:
    """Base class for provider clients.

    Owns an :class:`~nabia.core.http.HttpClient` configured for the
    provider. Use clients as context managers so connections are
    released::

        with OpenMeteoClient() as client:
            ...

    Args:
        nabia_settings: Shared HTTP/cache settings; read from the
            environment if omitted.
        secret_params: Query parameter names holding credentials.
        error_parser: Provider-specific extraction of error reasons.
        http: Pre-built HTTP client (advanced use and tests); when
            given, the other arguments are ignored.
    """

    #: Provider identifier used in output, logs and errors.
    PROVIDER: ClassVar[str]

    def __init__(
        self,
        *,
        nabia_settings: NabiaSettings | None = None,
        secret_params: Iterable[str] = (),
        error_parser: ErrorParser | None = None,
        http: HttpClient | None = None,
    ) -> None:
        self._http = http or HttpClient(
            provider=self.PROVIDER,
            settings=nabia_settings,
            secret_params=secret_params,
            error_parser=error_parser,
        )

    def close(self) -> None:
        """Release network resources."""
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
