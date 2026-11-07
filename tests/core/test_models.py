import sys
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest
from pydantic import ValidationError

from nabia import (
    DailySeries,
    GeoPoint,
    HourlySeries,
    MissingDependencyError,
    Resolution,
    SourceKind,
    Unit,
    Variable,
)

POINT = GeoPoint(latitude=40.4, longitude=-3.7)
T0 = datetime(2024, 1, 1, tzinfo=UTC)


def hourly(**overrides: object) -> HourlySeries:
    data: dict[str, object] = {
        "provider": "test",
        "dataset": "unit",
        "location": POINT,
        "timezone": "UTC",
        "time": (T0, T0 + timedelta(hours=1)),
        "values": {Variable.AIR_TEMPERATURE: (1.5, None)},
    }
    data.update(overrides)
    return HourlySeries.model_validate(data)


@pytest.mark.parametrize(
    ("lat", "lon"), [(91, 0), (-91, 0), (0, 181), (0, -181)]
)
def test_geopoint_bounds(lat: float, lon: float) -> None:
    with pytest.raises(ValidationError):
        GeoPoint(latitude=lat, longitude=lon)


def test_units_are_filled_from_catalog() -> None:
    assert hourly().units == {Variable.AIR_TEMPERATURE: Unit.CELSIUS}


def test_units_must_match_catalog() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        hourly(units={Variable.AIR_TEMPERATURE: Unit.KELVIN})


def test_naive_datetimes_rejected() -> None:
    with pytest.raises(ValidationError):
        hourly(time=(datetime(2024, 1, 1), datetime(2024, 1, 2)))  # noqa: DTZ001


def test_misaligned_columns_rejected() -> None:
    with pytest.raises(ValidationError, match="aligned"):
        hourly(values={Variable.AIR_TEMPERATURE: (1.0,)})


def test_time_must_increase() -> None:
    with pytest.raises(ValidationError, match="increasing"):
        hourly(time=(T0, T0))


def test_series_is_immutable() -> None:
    series = hourly()
    with pytest.raises(ValidationError):
        series.provider = "other"  # type: ignore[misc]


def test_json_roundtrip() -> None:
    series = hourly()
    assert HourlySeries.model_validate_json(series.model_dump_json()) == series


def test_daily_series_uses_dates() -> None:
    series = DailySeries(
        provider="test",
        dataset="unit",
        location=POINT,
        timezone="UTC",
        time=(date(2024, 1, 1), date(2024, 1, 2)),
        values={Variable.PRECIPITATION: (0.0, 2.5)},
    )
    assert series.variables == (Variable.PRECIPITATION,)
    assert series.resolution is Resolution.DAILY


def test_to_dataframe() -> None:
    frame = hourly().to_dataframe()
    assert list(frame.columns) == ["air_temperature"]
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert str(frame.index.tz) == "UTC"
    assert frame["air_temperature"].isna().tolist() == [False, True]
    assert frame.attrs["units"] == {"air_temperature": "°C"}


def test_to_dataframe_without_pandas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", None)
    with pytest.raises(MissingDependencyError, match=r"nabia\[pandas\]"):
        hourly().to_dataframe()


def test_provenance_defaults_to_unknown() -> None:
    series = hourly()
    assert series.source is None
    assert series.source_kind is None
    assert series.attribution is None


def test_series_saved_by_0_1_0_still_load() -> None:
    # 0.1.0 serialized series had no provenance fields.
    data = hourly().model_dump(mode="json")
    for field in ("source", "source_kind", "attribution"):
        del data[field]
    assert HourlySeries.model_validate(data) == hourly()


def test_dataframe_carries_provenance() -> None:
    series = hourly(
        source="era5",
        source_kind=SourceKind.REANALYSIS,
        attribution="Data by X",
    )
    attrs = series.to_dataframe().attrs
    assert attrs["source"] == "era5"
    assert attrs["source_kind"] == "reanalysis"
    assert attrs["attribution"] == "Data by X"
