"""Offline tests for the Open-Meteo client.

Fixtures are trimmed real responses from the archive endpoint for
Madrid around the 2024-03-31 daylight saving transition.
"""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError

from nabia import (
    GeoPoint,
    NabiaSettings,
    ProviderContractError,
    ProviderHTTPError,
    UnitMismatchError,
    UnsupportedVariableError,
    Variable,
)
from nabia.providers.open_meteo import (
    FORECAST,
    OpenMeteoClient,
    OpenMeteoSettings,
)
from nabia.providers.protocols import (
    ForecastDailyProvider,
    ForecastHourlyProvider,
    HistoricalDailyProvider,
    HistoricalHourlyProvider,
)

FIXTURES = Path(__file__).parent / "fixtures"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MADRID = GeoPoint(latitude=40.42, longitude=-3.70)
DAY = date(2024, 3, 31)


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (FIXTURES / name).read_text(encoding="utf-8")
    )
    return data


@pytest.fixture
def client() -> Iterator[OpenMeteoClient]:
    with OpenMeteoClient(nabia_settings=NabiaSettings(max_retries=0)) as c:
        yield c


def params_of(route: respx.Route) -> httpx.QueryParams:
    return route.calls.last.request.url.params


def test_historical_daily(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(ARCHIVE_URL).respond(
        200, json=load("archive_daily.json")
    )
    series = client.historical_daily(
        MADRID,
        [Variable.PRECIPITATION, Variable.SUNSHINE_DURATION],
        start=date(2024, 3, 30),
        end=DAY,
    )
    params = params_of(route)
    assert params["daily"] == "precipitation_sum,sunshine_duration"
    assert params["start_date"] == "2024-03-30"
    assert params["end_date"] == "2024-03-31"
    assert params["timeformat"] == "iso8601"
    assert params["wind_speed_unit"] == "ms"
    assert series.provider == "open_meteo"
    assert series.dataset == "archive"
    assert series.timezone == "Europe/Madrid"
    assert series.elevation == 667.0
    assert series.time == (date(2024, 3, 30), DAY)
    assert series.values[Variable.PRECIPITATION] == (10.1, 9.6)
    sunshine = series.values[Variable.SUNSHINE_DURATION]
    assert sunshine == pytest.approx((12623.88 / 3600, 18786.74 / 3600))


def test_historical_hourly_handles_dst(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(ARCHIVE_URL).respond(
        200, json=load("archive_hourly.json")
    )
    series = client.historical_hourly(
        MADRID, [Variable.AIR_TEMPERATURE], start=DAY, end=DAY
    )
    assert params_of(route)["timeformat"] == "unixtime"
    assert [t.isoformat() for t in series.time] == [
        "2024-03-31T00:00:00+01:00",
        "2024-03-31T01:00:00+01:00",
        "2024-03-31T03:00:00+02:00",
        "2024-03-31T04:00:00+02:00",
    ]


def test_forecast_hourly_params(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(FORECAST_URL).respond(
        200, json=load("archive_hourly.json")
    )
    client.forecast_hourly(
        MADRID,
        [Variable.AIR_TEMPERATURE, Variable.AIR_TEMPERATURE],
        days=3,
        past_days=1,
        timezone="UTC",
    )
    params = params_of(route)
    assert params["hourly"] == "temperature_2m"  # duplicates dropped
    assert params["forecast_days"] == "3"
    assert params["past_days"] == "1"
    assert params["timezone"] == "UTC"


def test_forecast_daily_accepts_variable_names(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(FORECAST_URL).respond(200, json=load("archive_daily.json"))
    series = client.forecast_daily(
        MADRID,
        ["air_temperature_max"],  # type: ignore[list-item]
    )
    assert series.variables == (Variable.AIR_TEMPERATURE_MAX,)


def test_every_mapped_variable_parses_from_fixture(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(FORECAST_URL).mock(
        side_effect=[
            httpx.Response(200, json=load("archive_hourly.json")),
            httpx.Response(200, json=load("archive_daily.json")),
        ]
    )
    hourly = client.forecast_hourly(MADRID, list(FORECAST.hourly))
    daily = client.forecast_daily(MADRID, list(FORECAST.daily))
    assert set(hourly.values) == set(FORECAST.hourly)
    assert set(daily.values) == set(FORECAST.daily)


def test_custom_endpoint(respx_mock: respx.MockRouter) -> None:
    url = "https://weather.internal/v1/forecast"
    route = respx_mock.get(url).respond(200, json=load("archive_daily.json"))
    settings = OpenMeteoSettings(forecast_url=url)
    with OpenMeteoClient(settings) as client:
        client.forecast_daily(MADRID, [Variable.RAIN])
    assert route.called


def test_unsupported_variable_fails_before_request(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    with pytest.raises(UnsupportedVariableError):
        client.forecast_hourly(MADRID, [Variable.AIR_TEMPERATURE_MAX])
    assert not respx_mock.calls


def test_unit_drift_is_detected(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    payload = load("archive_hourly.json")
    payload["hourly_units"]["temperature_2m"] = "°F"
    respx_mock.get(ARCHIVE_URL).respond(200, json=payload)
    with pytest.raises(UnitMismatchError, match="temperature_2m"):
        client.historical_hourly(
            MADRID, [Variable.AIR_TEMPERATURE], start=DAY, end=DAY
        )


def test_renamed_column_is_detected(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    payload = load("archive_daily.json")
    payload["daily"]["rain_total"] = payload["daily"].pop("rain_sum")
    respx_mock.get(ARCHIVE_URL).respond(200, json=payload)
    with pytest.raises(ProviderContractError, match="rain_sum"):
        client.historical_daily(MADRID, [Variable.RAIN], start=DAY, end=DAY)


def test_missing_block_is_detected(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    payload = load("archive_daily.json")
    del payload["daily"]
    respx_mock.get(ARCHIVE_URL).respond(200, json=payload)
    with pytest.raises(ProviderContractError, match="'daily'"):
        client.historical_daily(MADRID, [Variable.RAIN], start=DAY, end=DAY)


def test_api_error_reason_is_surfaced(
    client: OpenMeteoClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(ARCHIVE_URL).respond(
        400, json={"error": True, "reason": "Parameter 'end_date' is out"}
    )
    with pytest.raises(ProviderHTTPError, match="end_date"):
        client.historical_daily(MADRID, [Variable.RAIN], start=DAY, end=DAY)


@pytest.mark.parametrize(
    "kwargs",
    [{"days": 0}, {"days": 17}, {"past_days": -1}, {"timezone": ""}],
)
def test_forecast_arguments_are_validated(
    client: OpenMeteoClient, kwargs: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        client.forecast_daily(MADRID, [Variable.RAIN], **kwargs)


def test_empty_variable_list_rejected(client: OpenMeteoClient) -> None:
    with pytest.raises(ValidationError):
        client.forecast_daily(MADRID, [])


@pytest.mark.parametrize(
    ("start", "end"),
    [(date(2024, 2, 1), date(2024, 1, 1)), (date(1939, 12, 31), DAY)],
)
def test_historical_range_is_validated(
    client: OpenMeteoClient, start: date, end: date
) -> None:
    with pytest.raises(ValueError, match="start"):
        client.historical_daily(MADRID, [Variable.RAIN], start=start, end=end)


def test_client_implements_capability_protocols(
    client: OpenMeteoClient,
) -> None:
    assert isinstance(client, ForecastHourlyProvider)
    assert isinstance(client, ForecastDailyProvider)
    assert isinstance(client, HistoricalHourlyProvider)
    assert isinstance(client, HistoricalDailyProvider)
