from pathlib import Path

import httpx
import pytest
import respx
from pydantic import BaseModel

from nabia.core.cache import SQLiteResponseCache
from nabia.core.config import NabiaSettings
from nabia.core.errors import (
    AuthenticationError,
    ProviderConnectionError,
    ProviderContractError,
    ProviderHTTPError,
    ProviderServerError,
    RateLimitError,
)
from nabia.core.http import HttpClient

URL = "https://api.test/data"


class Payload(BaseModel):
    value: int


def make_client(
    *,
    retries: int = 2,
    sleeps: list[float] | None = None,
    **kwargs: object,
) -> HttpClient:
    recorded = sleeps if sleeps is not None else []
    return HttpClient(
        provider="test",
        settings=NabiaSettings(max_retries=retries),
        sleep=recorded.append,
        **kwargs,  # type: ignore[arg-type]
    )


def test_success_sends_user_agent(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(URL).respond(200, content=b"ok")
    with make_client() as client:
        assert client.get(URL) == b"ok"
    assert route.calls.last.request.headers["User-Agent"].startswith("nabia/")


def test_retries_transient_status(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, content=b"ok")]
    )
    sleeps: list[float] = []
    with make_client(sleeps=sleeps) as client:
        assert client.get(URL) == b"ok"
    assert len(sleeps) == 1


def test_retry_after_header_is_honoured(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, content=b"ok"),
        ]
    )
    sleeps: list[float] = []
    with make_client(sleeps=sleeps) as client:
        client.get(URL)
    assert sleeps == [2.0]


def test_rate_limit_after_retries(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).respond(429, headers={"Retry-After": "7"})
    with make_client(retries=1) as client, pytest.raises(RateLimitError) as e:
        client.get(URL)
    assert e.value.retry_after == 7.0
    assert e.value.status_code == 429


def test_server_error_after_retries(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(URL).respond(500)
    with (
        make_client(retries=2) as client,
        pytest.raises(ProviderServerError),
    ):
        client.get(URL)
    assert route.call_count == 3


@pytest.mark.parametrize("status", [401, 403])
def test_authentication_errors(
    respx_mock: respx.MockRouter, status: int
) -> None:
    respx_mock.get(URL).respond(status)
    with make_client() as client, pytest.raises(AuthenticationError):
        client.get(URL)


def test_client_error_uses_parser_and_redacts(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(URL).respond(400, json={"reason": "bad apikey=SECRET"})
    fake = {"apikey": "SECRET"}  # pragma: allowlist secret
    with (
        make_client(
            error_parser=lambda r: r.json()["reason"],
        ) as client,
        pytest.raises(ProviderHTTPError) as e,
    ):
        client.get(URL, params=fake)
    assert e.value.status_code == 400
    assert "bad apikey=***" in str(e.value)
    assert "SECRET" not in str(e.value)
    assert e.value.url is not None
    assert "SECRET" not in e.value.url


def test_broken_parser_does_not_hide_error(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(URL).respond(404)

    def broken(response: httpx.Response) -> str:
        raise RuntimeError("boom")

    with (
        make_client(error_parser=broken) as client,
        pytest.raises(ProviderHTTPError, match="404"),
    ):
        client.get(URL)


def test_redirects_are_not_followed(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).respond(302, headers={"Location": "https://evil/"})
    with make_client() as client, pytest.raises(ProviderHTTPError):
        client.get(URL)


def test_network_errors_are_redacted(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).mock(side_effect=httpx.ConnectError("refused"))
    sleeps: list[float] = []
    fake = {"apikey": "SECRET"}  # pragma: allowlist secret
    with (
        make_client(retries=2, sleeps=sleeps) as client,
        pytest.raises(ProviderConnectionError) as e,
    ):
        client.get(URL, params=fake)
    assert len(sleeps) == 2
    assert e.value.__suppress_context__
    assert "SECRET" not in str(e.value)
    assert e.value.url == f"{URL}?apikey=***"


def test_cache_avoids_second_request(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    route = respx_mock.get(URL).respond(200, content=b"cached")
    cache = SQLiteResponseCache(tmp_path / "c.sqlite3")
    with make_client(cache=cache) as client:
        assert client.get(URL, params={"a": 1}) == b"cached"
        assert client.get(URL, params={"a": 1}) == b"cached"
        client.get(URL, params={"a": 1}, cache_ttl=0)
    assert route.call_count == 2


def test_cache_enabled_from_settings(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    route = respx_mock.get(URL).respond(200, content=b"x")
    settings = NabiaSettings(
        cache_enabled=True, cache_path=tmp_path / "c.sqlite3"
    )
    with HttpClient(provider="test", settings=settings) as client:
        client.get(URL)
        client.get(URL)
    assert route.call_count == 1
    assert (tmp_path / "c.sqlite3").exists()


def test_get_model_validates(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).respond(200, json={"value": 3})
    with make_client() as client:
        assert client.get_model(Payload, URL) == Payload(value=3)


def test_get_model_contract_error(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).respond(200, json={"value": "not-int"})
    with (
        make_client() as client,
        pytest.raises(ProviderContractError, match="value"),
    ):
        client.get_model(Payload, URL)
