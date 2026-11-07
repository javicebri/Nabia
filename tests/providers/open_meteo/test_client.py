"""Offline tests specific to the Python Open-Meteo client.

Behaviour shared with every implementation (requests sent, series
returned, errors raised) is defined once in ``conformance.py`` and
replayed by ``tests/test_conformance.py``. These tests cover what only
the Python API has: configuration, accepted argument types and
exception classes.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import respx
from pydantic import ValidationError

from nabia import GeoPoint, NabiaSettings, Variable
from nabia.providers.open_meteo import OpenMeteoClient, OpenMeteoSettings
from nabia.providers.protocols import (
    ForecastDailyProvider,
    ForecastHourlyProvider,
    HistoricalDailyProvider,
    HistoricalHourlyProvider,
)

FIXTURES = Path(__file__).parent / "fixtures"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MADRID = GeoPoint(latitude=40.42, longitude=-3.70)


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (FIXTURES / name).read_text(encoding="utf-8")
    )
    return data


@pytest.fixture
def client() -> Iterator[OpenMeteoClient]:
    with OpenMeteoClient(nabia_settings=NabiaSettings(max_retries=0)) as c:
        yield c


def test_accepts_enum_members_and_names(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(FORECAST_URL).respond(200, json=load("archive_daily.json"))
    by_member = client.forecast_daily(MADRID, [Variable.AIR_TEMPERATURE_MAX])
    by_name = client.forecast_daily(
        MADRID,
        ["air_temperature_max"],  # type: ignore[list-item]
    )
    assert by_member == by_name
    assert by_name.variables == (Variable.AIR_TEMPERATURE_MAX,)


def test_custom_endpoint(respx_mock: respx.MockRouter) -> None:
    url = "https://weather.internal/v1/forecast"
    route = respx_mock.get(url).respond(200, json=load("archive_daily.json"))
    settings = OpenMeteoSettings(forecast_url=url)
    with OpenMeteoClient(settings) as client:
        client.forecast_daily(MADRID, [Variable.RAIN])
    assert route.called


def test_endpoint_must_be_https() -> None:
    with pytest.raises(ValidationError):
        OpenMeteoSettings(forecast_url="http://weather.internal/v1/forecast")


def test_invalid_arguments_raise_validation_error(
    client: OpenMeteoClient,
) -> None:
    # Python callers can rely on pydantic's ValidationError (a
    # ValueError), the class behind the "invalid_argument" kind.
    with pytest.raises(ValidationError):
        client.forecast_daily(MADRID, [Variable.RAIN], days=0)


def test_client_implements_capability_protocols(
    client: OpenMeteoClient,
) -> None:
    assert isinstance(client, ForecastHourlyProvider)
    assert isinstance(client, ForecastDailyProvider)
    assert isinstance(client, HistoricalHourlyProvider)
    assert isinstance(client, HistoricalDailyProvider)
