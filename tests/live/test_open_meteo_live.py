"""Contract tests against the real Open-Meteo API.

They request every variable in the equivalence tables, so a renamed
variable, a changed unit or a new response structure fails here.
Run with ``uv run pytest -m live`` and, when green, bump
``VERIFIED_ON`` in ``nabia/providers/open_meteo/mapping.py``.
"""

from collections.abc import Iterator
from datetime import date

import pytest

from nabia import GeoPoint, NoDataError, SourceKind, Surface, Variable
from nabia.providers.open_meteo import ARCHIVE, FORECAST, OpenMeteoClient

pytestmark = pytest.mark.live

MADRID = GeoPoint(latitude=40.42, longitude=-3.70)
START, END = date(2024, 3, 30), date(2024, 3, 31)
SLOPE = Surface(tilt=30, aspect=180)
TILTED = Variable.SHORTWAVE_RADIATION_TILTED


@pytest.fixture
def client() -> Iterator[OpenMeteoClient]:
    with OpenMeteoClient() as c:
        yield c


def test_forecast_hourly_contract(client: OpenMeteoClient) -> None:
    series = client.forecast_hourly(
        MADRID, list(FORECAST.hourly), days=1, surface=SLOPE
    )
    assert len(series.time) == 24
    assert set(series.values) == set(FORECAST.hourly)


def test_forecast_daily_contract(client: OpenMeteoClient) -> None:
    series = client.forecast_daily(MADRID, list(FORECAST.daily), days=2)
    assert len(series.time) == 2
    assert set(series.values) == set(FORECAST.daily)


def test_archive_hourly_contract(client: OpenMeteoClient) -> None:
    series = client.historical_hourly(
        MADRID, list(ARCHIVE.hourly), start=START, end=END, surface=SLOPE
    )
    assert len(series.time) == 48
    assert set(series.values) == set(ARCHIVE.hourly)


def test_archive_daily_contract(client: OpenMeteoClient) -> None:
    series = client.historical_daily(
        MADRID, list(ARCHIVE.daily), start=START, end=END
    )
    assert series.time == (START, END)
    assert set(series.values) == set(ARCHIVE.daily)


def test_explicit_archive_source(client: OpenMeteoClient) -> None:
    series = client.historical_daily(
        MADRID, [Variable.PRECIPITATION], start=START, end=END, model="era5"
    )
    assert series.source == "era5"
    assert series.source_kind is SourceKind.REANALYSIS
    assert all(v is not None for v in series.values[Variable.PRECIPITATION])


def test_source_without_the_variable_raises(client: OpenMeteoClient) -> None:
    # Documents upstream behaviour seen on 2026-11-07: ERA5-Land returns
    # no precipitation. If this starts passing data, update the README.
    with pytest.raises(NoDataError):
        client.historical_daily(
            MADRID,
            [Variable.PRECIPITATION],
            start=START,
            end=END,
            model="era5_land",
        )


def _tilted(client: OpenMeteoClient, aspect: float) -> tuple[float, float]:
    """Morning and afternoon radiation (Wh/m2) on a 30 degree slope."""
    day = date(2024, 7, 15)  # clear summer day in Madrid
    series = client.historical_hourly(
        MADRID,
        [TILTED],
        start=day,
        end=day,
        timezone="UTC",
        surface=Surface(tilt=30, aspect=aspect),
    )
    morning = afternoon = 0.0
    for moment, value in zip(series.time, series.values[TILTED], strict=True):
        # Solar noon in Madrid is around 12:15 UTC.
        if moment.hour <= 12:
            morning += value or 0.0
        else:
            afternoon += value or 0.0
    return morning, afternoon


def test_orientation_convention(client: OpenMeteoClient) -> None:
    # Guards the compass translation: Open-Meteo's published spec
    # contradicts its actual azimuth convention (checked 2026-11-07).
    south, north = sum(_tilted(client, 180)), sum(_tilted(client, 0))
    east_am, east_pm = _tilted(client, 90)
    west_am, west_pm = _tilted(client, 270)
    assert south > north
    assert east_am > west_am
    assert west_pm > east_pm
