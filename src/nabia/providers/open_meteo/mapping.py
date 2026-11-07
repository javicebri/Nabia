"""Equivalence tables: canonical variables <-> Open-Meteo names.

Units are pinned with :data:`UNIT_PARAMS` so the tables stay valid
regardless of Open-Meteo defaults (e.g. wind speed in km/h).

The forecast and historical (archive) endpoints share these names and
units; both were verified against the live API on ``VERIFIED_ON``.
When an entry changes upstream, update it here, run
``uv run pytest -m live`` and bump ``VERIFIED_ON``.
"""

from datetime import date
from types import MappingProxyType

from nabia.catalog import NativeVariable, Unit, Variable, VariableTable

VERIFIED_ON = date(2026, 11, 7)

#: Query parameters that pin the units reported by Open-Meteo.
UNIT_PARAMS: MappingProxyType[str, str] = MappingProxyType(
    {
        "temperature_unit": "celsius",
        "wind_speed_unit": "ms",
        "precipitation_unit": "mm",
    }
)

_HOURLY = {
    Variable.AIR_TEMPERATURE: NativeVariable(
        name="temperature_2m", unit=Unit.CELSIUS
    ),
    Variable.RELATIVE_HUMIDITY: NativeVariable(
        name="relative_humidity_2m", unit=Unit.PERCENT
    ),
    Variable.DEW_POINT: NativeVariable(name="dew_point_2m", unit=Unit.CELSIUS),
    Variable.VAPOUR_PRESSURE_DEFICIT: NativeVariable(
        name="vapour_pressure_deficit", unit=Unit.KILOPASCAL
    ),
    Variable.PRECIPITATION: NativeVariable(
        name="precipitation",
        unit=Unit.MILLIMETRE,
        notes="Sum of the preceding hour.",
    ),
    Variable.RAIN: NativeVariable(
        name="rain",
        unit=Unit.MILLIMETRE,
        notes="Sum of the preceding hour.",
    ),
    Variable.SURFACE_PRESSURE: NativeVariable(
        name="surface_pressure", unit=Unit.HECTOPASCAL
    ),
    Variable.SEA_LEVEL_PRESSURE: NativeVariable(
        name="pressure_msl", unit=Unit.HECTOPASCAL
    ),
    Variable.CLOUD_COVER: NativeVariable(
        name="cloud_cover", unit=Unit.PERCENT
    ),
    Variable.WIND_SPEED: NativeVariable(
        name="wind_speed_10m", unit=Unit.METRE_PER_SECOND
    ),
    Variable.WIND_GUSTS: NativeVariable(
        name="wind_gusts_10m",
        unit=Unit.METRE_PER_SECOND,
        notes="Maximum of the preceding hour.",
    ),
    Variable.WIND_DIRECTION: NativeVariable(
        name="wind_direction_10m", unit=Unit.DEGREE
    ),
    Variable.SHORTWAVE_RADIATION: NativeVariable(
        name="shortwave_radiation",
        unit=Unit.WATT_PER_SQUARE_METRE,
        notes="Mean of the preceding hour.",
    ),
    Variable.SUNSHINE_DURATION: NativeVariable(
        name="sunshine_duration",
        unit=Unit.SECOND,
        notes="Seconds per hour upstream; converted to hours.",
    ),
    Variable.REFERENCE_EVAPOTRANSPIRATION: NativeVariable(
        name="et0_fao_evapotranspiration", unit=Unit.MILLIMETRE
    ),
}

_DAILY = {
    Variable.AIR_TEMPERATURE_MEAN: NativeVariable(
        name="temperature_2m_mean", unit=Unit.CELSIUS
    ),
    Variable.AIR_TEMPERATURE_MAX: NativeVariable(
        name="temperature_2m_max", unit=Unit.CELSIUS
    ),
    Variable.AIR_TEMPERATURE_MIN: NativeVariable(
        name="temperature_2m_min", unit=Unit.CELSIUS
    ),
    Variable.RELATIVE_HUMIDITY_MEAN: NativeVariable(
        name="relative_humidity_2m_mean", unit=Unit.PERCENT
    ),
    Variable.PRECIPITATION: NativeVariable(
        name="precipitation_sum", unit=Unit.MILLIMETRE
    ),
    Variable.RAIN: NativeVariable(name="rain_sum", unit=Unit.MILLIMETRE),
    Variable.WIND_SPEED_MAX: NativeVariable(
        name="wind_speed_10m_max", unit=Unit.METRE_PER_SECOND
    ),
    Variable.WIND_GUSTS_MAX: NativeVariable(
        name="wind_gusts_10m_max", unit=Unit.METRE_PER_SECOND
    ),
    Variable.WIND_DIRECTION_DOMINANT: NativeVariable(
        name="wind_direction_10m_dominant", unit=Unit.DEGREE
    ),
    Variable.SHORTWAVE_RADIATION_SUM: NativeVariable(
        name="shortwave_radiation_sum", unit=Unit.MEGAJOULE_PER_SQUARE_METRE
    ),
    Variable.SUNSHINE_DURATION: NativeVariable(
        name="sunshine_duration",
        unit=Unit.SECOND,
        notes="Seconds per day upstream; converted to hours.",
    ),
    Variable.REFERENCE_EVAPOTRANSPIRATION: NativeVariable(
        name="et0_fao_evapotranspiration", unit=Unit.MILLIMETRE
    ),
}

FORECAST = VariableTable(
    provider="open_meteo",
    dataset="forecast",
    reference_url="https://open-meteo.com/en/docs",
    verified_on=VERIFIED_ON,
    hourly=_HOURLY,
    daily=_DAILY,
)

ARCHIVE = VariableTable(
    provider="open_meteo",
    dataset="archive",
    reference_url="https://open-meteo.com/en/docs/historical-weather-api",
    verified_on=VERIFIED_ON,
    hourly=_HOURLY,
    daily=_DAILY,
)
