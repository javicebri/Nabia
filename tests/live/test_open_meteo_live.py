"""Contract tests against the real Open-Meteo API.

They request every variable in the equivalence tables, so a renamed
variable, a changed unit or a new response structure fails here.
Run with ``uv run pytest -m live`` and, when green, bump
``VERIFIED_ON`` in ``nabia/providers/open_meteo/mapping.py``.
"""

from collections.abc import Iterator
from datetime import date

import pytest

from nabia import GeoPoint
from nabia.providers.open_meteo import ARCHIVE, FORECAST, OpenMeteoClient

pytestmark = pytest.mark.live

MADRID = GeoPoint(latitude=40.42, longitude=-3.70)
START, END = date(2024, 3, 30), date(2024, 3, 31)


@pytest.fixture
def client() -> Iterator[OpenMeteoClient]:
    with OpenMeteoClient() as c:
        yield c


def test_forecast_hourly_contract(client: OpenMeteoClient) -> None:
    series = client.forecast_hourly(MADRID, list(FORECAST.hourly), days=1)
    assert len(series.time) == 24
    assert set(series.values) == set(FORECAST.hourly)


def test_forecast_daily_contract(client: OpenMeteoClient) -> None:
    series = client.forecast_daily(MADRID, list(FORECAST.daily), days=2)
    assert len(series.time) == 2
    assert set(series.values) == set(FORECAST.daily)


def test_archive_hourly_contract(client: OpenMeteoClient) -> None:
    series = client.historical_hourly(
        MADRID, list(ARCHIVE.hourly), start=START, end=END
    )
    assert len(series.time) == 48
    assert set(series.values) == set(ARCHIVE.hourly)


def test_archive_daily_contract(client: OpenMeteoClient) -> None:
    series = client.historical_daily(
        MADRID, list(ARCHIVE.daily), start=START, end=END
    )
    assert series.time == (START, END)
    assert set(series.values) == set(ARCHIVE.daily)
