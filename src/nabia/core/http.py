"""Synchronous HTTP client shared by every provider.

Responsibilities:

* Timeouts and retries with exponential backoff for transient failures
  (network errors, HTTP 429 and 5xx), honouring ``Retry-After``.
* Mapping of HTTP failures to :mod:`nabia.core.errors` exceptions.
* Optional on-disk caching of successful responses.
* Redaction of secrets in logs and exception messages.
* Validation of response bodies against pydantic schemas.

Redirects are never followed, so credentials sent in headers cannot be
forwarded to a different host.
"""

import logging
import random
import time
from collections.abc import Callable, Iterable, Mapping
from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, ValidationError

from nabia.core.cache import (
    ResponseCache,
    SQLiteResponseCache,
    make_cache_key,
)
from nabia.core.config import NabiaSettings
from nabia.core.errors import (
    AuthenticationError,
    ProviderConnectionError,
    ProviderContractError,
    ProviderHTTPError,
    ProviderServerError,
    RateLimitError,
)
from nabia.core.security import (
    install_log_redaction,
    redact_text,
    redact_url,
    register_secret_params,
)
from nabia.core.tls import build_verify

logger = logging.getLogger(__name__)

#: Query parameters accepted by :meth:`HttpClient.get`.
Params = Mapping[str, str | int | float]

#: Extracts a human-readable reason from an error response, if any.
ErrorParser = Callable[[httpx.Response], str | None]

RETRYABLE_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})

_BACKOFF_BASE_SECONDS = 0.5
_BACKOFF_CAP_SECONDS = 30.0
_MAX_DETAIL_CHARS = 300


class HttpClient:
    """HTTP client bound to one provider.

    Args:
        provider: Provider identifier used in logs and errors.
        settings: Shared settings; read from the environment if omitted.
        secret_params: Extra query parameter names holding credentials.
        error_parser: Provider-specific extraction of error reasons.
        cache: Cache backend; defaults to SQLite when enabled in
            settings.
        transport: Custom httpx transport (tests, proxies).
        sleep: Sleep function, injectable to speed up tests.
    """

    def __init__(
        self,
        *,
        provider: str,
        settings: NabiaSettings | None = None,
        secret_params: Iterable[str] = (),
        error_parser: ErrorParser | None = None,
        cache: ResponseCache | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._provider = provider
        self._settings = settings or NabiaSettings()
        self._error_parser = error_parser
        self._sleep = sleep
        register_secret_params(secret_params)
        install_log_redaction()
        if cache is None and self._settings.cache_enabled:
            cache = SQLiteResponseCache(self._settings.cache_path)
        self._cache = cache
        self._client = httpx.Client(
            timeout=self._settings.timeout_seconds,
            headers={"User-Agent": self._settings.user_agent},
            follow_redirects=False,
            verify=build_verify(self._settings.ssl_trust),
            transport=transport,
        )

    @property
    def provider(self) -> str:
        """Provider identifier this client is bound to."""
        return self._provider

    def get(
        self,
        url: str,
        *,
        params: Params | None = None,
        headers: Mapping[str, str] | None = None,
        cache_ttl: float | None = None,
    ) -> bytes:
        """Send a GET request and return the raw response body.

        The cache key covers the URL and non-secret query parameters
        only. Providers whose responses depend on headers must disable
        caching for that call with ``cache_ttl=0``.

        Args:
            url: Absolute HTTPS URL.
            params: Query parameters.
            headers: Extra headers (e.g. credentials).
            cache_ttl: Seconds to cache the response; ``None`` uses the
                configured default and ``0`` disables caching.

        Raises:
            ProviderConnectionError: Network failure after retries.
            ProviderHTTPError: Non-success HTTP status (or a subclass).
        """
        query = dict(params or {})
        if cache_ttl is None:
            cache_ttl = self._settings.cache_ttl_seconds
        key: str | None = None
        if self._cache is not None and cache_ttl > 0:
            key = make_cache_key("GET", url, query)
            cached = self._cache.get(key)
            if cached is not None:
                logger.debug("%s: cache hit", self._provider)
                return cached
        response = self._send("GET", url, params=query, headers=headers)
        if key is not None and self._cache is not None:
            self._cache.set(key, response.content, cache_ttl)
        return response.content

    def get_model[ModelT: BaseModel](
        self,
        model: type[ModelT],
        url: str,
        *,
        params: Params | None = None,
        headers: Mapping[str, str] | None = None,
        cache_ttl: float | None = None,
    ) -> ModelT:
        """Send a GET request and validate the JSON body as ``model``.

        Raises:
            ProviderContractError: The body does not match ``model``.
        """
        body = self.get(
            url, params=params, headers=headers, cache_ttl=cache_ttl
        )
        return parse_json(model, body, provider=self._provider)

    def close(self) -> None:
        """Release pooled connections."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- internals --------------------------------------

    def _send(
        self,
        method: str,
        url: str,
        *,
        params: Params,
        headers: Mapping[str, str] | None,
    ) -> httpx.Response:
        safe_url = redact_url(httpx.URL(url, params=dict(params)))
        max_retries = self._settings.max_retries
        for attempt in range(max_retries + 1):
            last_attempt = attempt == max_retries
            try:
                response = self._client.request(
                    method, url, params=params, headers=headers
                )
            except httpx.TransportError as exc:
                if last_attempt:
                    # "from None" keeps the original exception, which
                    # holds the unredacted request, out of tracebacks.
                    raise ProviderConnectionError(
                        f"{self._provider}: {type(exc).__name__} after "
                        f"{attempt + 1} attempt(s): "
                        f"{redact_text(str(exc))}",
                        provider=self._provider,
                        url=safe_url,
                    ) from None
                delay = _backoff_delay(attempt)
                logger.warning(
                    "%s: %s, retrying in %.1fs",
                    self._provider,
                    type(exc).__name__,
                    delay,
                )
                self._sleep(delay)
                continue

            if response.status_code in RETRYABLE_STATUS and not last_attempt:
                delay = _retry_after(response) or _backoff_delay(attempt)
                logger.warning(
                    "%s: HTTP %d, retrying in %.1fs",
                    self._provider,
                    response.status_code,
                    delay,
                )
                self._sleep(delay)
                continue

            logger.debug(
                "%s %s -> HTTP %d", method, safe_url, response.status_code
            )
            self._raise_for_status(response, safe_url)
            return response
        raise AssertionError("unreachable")  # pragma: no cover

    def _raise_for_status(
        self, response: httpx.Response, safe_url: str
    ) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        message = f"{self._provider}: HTTP {status} - "
        message += self._error_detail(response)
        provider, url = self._provider, safe_url
        if status in (401, 403):
            raise AuthenticationError(
                message, provider=provider, status_code=status, url=url
            )
        if status == 429:
            raise RateLimitError(
                message,
                provider=provider,
                url=url,
                retry_after=_retry_after(response),
            )
        if status >= 500:
            raise ProviderServerError(
                message, provider=provider, status_code=status, url=url
            )
        raise ProviderHTTPError(
            message, provider=provider, status_code=status, url=url
        )

    def _error_detail(self, response: httpx.Response) -> str:
        detail: str | None = None
        if self._error_parser is not None:
            try:
                detail = self._error_parser(response)
            except Exception:  # a broken parser must not hide the error
                logger.debug("error parser failed", exc_info=True)
        detail = detail or response.reason_phrase or "unknown error"
        return redact_text(detail)[:_MAX_DETAIL_CHARS]


def parse_json[ModelT: BaseModel](
    model: type[ModelT], body: bytes, *, provider: str
) -> ModelT:
    """Validate a JSON body against ``model``.

    Raises:
        ProviderContractError: Invalid JSON or unexpected structure,
            which usually means the upstream API changed.
    """
    try:
        return model.model_validate_json(body)
    except ValidationError as exc:
        issues = "; ".join(
            f"{'.'.join(map(str, err['loc'])) or '<root>'}: {err['msg']}"
            for err in exc.errors()[:5]
        )
        raise ProviderContractError(
            f"{provider}: unexpected response structure for "
            f"{model.__name__} ({exc.error_count()} issue(s)): {issues}",
            provider=provider,
        ) from None


def _backoff_delay(attempt: int) -> float:
    base = min(_BACKOFF_CAP_SECONDS, _BACKOFF_BASE_SECONDS * 2.0**attempt)
    # Jitter spreads retries from concurrent clients; not security
    # sensitive, so the standard PRNG is fine.
    return base + random.uniform(0, _BACKOFF_BASE_SECONDS)  # noqa: S311


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:  # HTTP-date form is rare for APIs; use backoff
        return None
    return max(0.0, min(seconds, _BACKOFF_CAP_SECONDS))
