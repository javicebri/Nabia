"""Canonical variable vocabulary shared by every provider.

Each :class:`Variable` has exactly one definition (unit, aggregation,
allowed resolutions) in :data:`VARIABLES`. Provider tables map these
canonical variables to native names; output always uses the canonical
name and unit, so switching providers does not change consumer code.

Conventions:

* Air temperature and humidity are measured at 2 m above ground.
* Wind is measured at 10 m above ground.
* ``SUM`` variables are accumulated over the series interval (one hour
  for hourly series, one day for daily series).
* ``MEAN``/``MAXIMUM``/``MINIMUM`` aggregate over the same interval.

Adding a variable: add the enum member and its spec here, then map it
in each provider table that supports it.
"""

from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from nabia.catalog.units import Unit


class Resolution(StrEnum):
    """Temporal resolution of a series."""

    HOURLY = "hourly"
    DAILY = "daily"


class Aggregation(StrEnum):
    """How a value relates to its time interval."""

    INSTANT = "instant"
    MEAN = "mean"
    SUM = "sum"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    DOMINANT = "dominant"


class Variable(StrEnum):
    """Canonical variable names (value = name used in output)."""

    AIR_TEMPERATURE = "air_temperature"
    AIR_TEMPERATURE_MEAN = "air_temperature_mean"
    AIR_TEMPERATURE_MAX = "air_temperature_max"
    AIR_TEMPERATURE_MIN = "air_temperature_min"
    RELATIVE_HUMIDITY = "relative_humidity"
    RELATIVE_HUMIDITY_MEAN = "relative_humidity_mean"
    DEW_POINT = "dew_point"
    VAPOUR_PRESSURE_DEFICIT = "vapour_pressure_deficit"
    PRECIPITATION = "precipitation"
    RAIN = "rain"
    SURFACE_PRESSURE = "surface_pressure"
    SEA_LEVEL_PRESSURE = "sea_level_pressure"
    CLOUD_COVER = "cloud_cover"
    WIND_SPEED = "wind_speed"
    WIND_SPEED_MAX = "wind_speed_max"
    WIND_GUSTS = "wind_gusts"
    WIND_GUSTS_MAX = "wind_gusts_max"
    WIND_DIRECTION = "wind_direction"
    WIND_DIRECTION_DOMINANT = "wind_direction_dominant"
    SHORTWAVE_RADIATION = "shortwave_radiation"
    SHORTWAVE_RADIATION_SUM = "shortwave_radiation_sum"
    SUNSHINE_DURATION = "sunshine_duration"
    REFERENCE_EVAPOTRANSPIRATION = "reference_evapotranspiration"


class VariableSpec(BaseModel):
    """Definition of a canonical variable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    unit: Unit
    aggregation: Aggregation
    resolutions: frozenset[Resolution]
    description: str


_H = frozenset({Resolution.HOURLY})
_D = frozenset({Resolution.DAILY})
_HD = frozenset({Resolution.HOURLY, Resolution.DAILY})


def _spec(
    unit: Unit,
    aggregation: Aggregation,
    resolutions: frozenset[Resolution],
    description: str,
) -> VariableSpec:
    return VariableSpec(
        unit=unit,
        aggregation=aggregation,
        resolutions=resolutions,
        description=description,
    )


#: Single source of truth for canonical variable definitions.
VARIABLES: MappingProxyType[Variable, VariableSpec] = MappingProxyType(
    {
        Variable.AIR_TEMPERATURE: _spec(
            Unit.CELSIUS,
            Aggregation.INSTANT,
            _H,
            "Air temperature at 2 m.",
        ),
        Variable.AIR_TEMPERATURE_MEAN: _spec(
            Unit.CELSIUS,
            Aggregation.MEAN,
            _D,
            "Mean air temperature at 2 m over the interval.",
        ),
        Variable.AIR_TEMPERATURE_MAX: _spec(
            Unit.CELSIUS,
            Aggregation.MAXIMUM,
            _D,
            "Maximum air temperature at 2 m over the interval.",
        ),
        Variable.AIR_TEMPERATURE_MIN: _spec(
            Unit.CELSIUS,
            Aggregation.MINIMUM,
            _D,
            "Minimum air temperature at 2 m over the interval.",
        ),
        Variable.RELATIVE_HUMIDITY: _spec(
            Unit.PERCENT,
            Aggregation.INSTANT,
            _H,
            "Relative humidity at 2 m.",
        ),
        Variable.RELATIVE_HUMIDITY_MEAN: _spec(
            Unit.PERCENT,
            Aggregation.MEAN,
            _D,
            "Mean relative humidity at 2 m over the interval.",
        ),
        Variable.DEW_POINT: _spec(
            Unit.CELSIUS,
            Aggregation.INSTANT,
            _H,
            "Dew point temperature at 2 m.",
        ),
        Variable.VAPOUR_PRESSURE_DEFICIT: _spec(
            Unit.KILOPASCAL,
            Aggregation.INSTANT,
            _H,
            "Vapour pressure deficit at 2 m.",
        ),
        Variable.PRECIPITATION: _spec(
            Unit.MILLIMETRE,
            Aggregation.SUM,
            _HD,
            "Total precipitation (rain, showers, snow water equivalent)"
            " accumulated over the interval.",
        ),
        Variable.RAIN: _spec(
            Unit.MILLIMETRE,
            Aggregation.SUM,
            _HD,
            "Liquid precipitation accumulated over the interval.",
        ),
        Variable.SURFACE_PRESSURE: _spec(
            Unit.HECTOPASCAL,
            Aggregation.INSTANT,
            _H,
            "Atmospheric pressure at the surface.",
        ),
        Variable.SEA_LEVEL_PRESSURE: _spec(
            Unit.HECTOPASCAL,
            Aggregation.INSTANT,
            _H,
            "Atmospheric pressure reduced to mean sea level.",
        ),
        Variable.CLOUD_COVER: _spec(
            Unit.PERCENT,
            Aggregation.INSTANT,
            _H,
            "Total cloud cover fraction.",
        ),
        Variable.WIND_SPEED: _spec(
            Unit.METRE_PER_SECOND,
            Aggregation.INSTANT,
            _H,
            "Wind speed at 10 m.",
        ),
        Variable.WIND_SPEED_MAX: _spec(
            Unit.METRE_PER_SECOND,
            Aggregation.MAXIMUM,
            _D,
            "Maximum wind speed at 10 m over the interval.",
        ),
        Variable.WIND_GUSTS: _spec(
            Unit.METRE_PER_SECOND,
            Aggregation.MAXIMUM,
            _H,
            "Maximum wind gust at 10 m over the interval.",
        ),
        Variable.WIND_GUSTS_MAX: _spec(
            Unit.METRE_PER_SECOND,
            Aggregation.MAXIMUM,
            _D,
            "Maximum wind gust at 10 m over the interval.",
        ),
        Variable.WIND_DIRECTION: _spec(
            Unit.DEGREE,
            Aggregation.INSTANT,
            _H,
            "Direction the wind blows from at 10 m (0 = north).",
        ),
        Variable.WIND_DIRECTION_DOMINANT: _spec(
            Unit.DEGREE,
            Aggregation.DOMINANT,
            _D,
            "Dominant wind direction at 10 m over the interval.",
        ),
        Variable.SHORTWAVE_RADIATION: _spec(
            Unit.WATT_PER_SQUARE_METRE,
            Aggregation.MEAN,
            _H,
            "Global horizontal irradiance, mean over the interval.",
        ),
        Variable.SHORTWAVE_RADIATION_SUM: _spec(
            Unit.MEGAJOULE_PER_SQUARE_METRE,
            Aggregation.SUM,
            _D,
            "Global horizontal irradiation accumulated over the interval.",
        ),
        Variable.SUNSHINE_DURATION: _spec(
            Unit.HOUR,
            Aggregation.SUM,
            _HD,
            "Sunshine duration (direct irradiance above 120 W/m²)"
            " accumulated over the interval.",
        ),
        Variable.REFERENCE_EVAPOTRANSPIRATION: _spec(
            Unit.MILLIMETRE,
            Aggregation.SUM,
            _HD,
            "FAO-56 Penman-Monteith reference evapotranspiration (ET0)"
            " of a well-watered grass surface, accumulated over the"
            " interval.",
        ),
    }
)
