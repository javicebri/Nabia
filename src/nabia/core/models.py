"""Normalized, provider-independent output models.

These models are the stable contract consumed by other projects:
canonical variable names, canonical units and timezone-aware
timestamps. Breaking changes here require a new major version.
"""

from datetime import date
from enum import StrEnum
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from nabia.catalog import VARIABLES, Resolution, Unit, Values, Variable
from nabia.core.errors import MissingDependencyError

if TYPE_CHECKING:
    import pandas as pd


class SourceKind(StrEnum):
    """Nature of the data in a series.

    Only ``OBSERVATION`` is a direct measurement; the other kinds are
    model or remote-sensing estimates.
    """

    FORECAST = "forecast"
    """Numerical weather prediction output."""

    ANALYSIS = "analysis"
    """Operational model analysis of the past (e.g. ECMWF IFS)."""

    REANALYSIS = "reanalysis"
    """Consistent model reconstruction of the past assimilating
    observations (e.g. ERA5)."""

    OBSERVATION = "observation"
    """In-situ measurement (e.g. a weather station)."""

    SATELLITE = "satellite"
    """Estimate derived from satellite remote sensing."""


class NabiaModel(BaseModel):
    """Base for output models: immutable, no unknown fields.

    Serialization always emits every field, so the serialization JSON
    Schema marks fields with defaults as required too.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_serialization_defaults_required=True,
    )


class GeoPoint(NabiaModel):
    """WGS84 coordinates in decimal degrees."""

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class Surface(NabiaModel):
    """Inclined surface, e.g. a slope, for plane-of-array variables.

    Attributes:
        tilt: Inclination from the horizontal in degrees (0 = flat,
            90 = vertical).
        aspect: Compass direction the surface faces, in degrees
            clockwise from north (0 = north, 90 = east, 180 = south,
            270 = west). Providers' own conventions are translated.
    """

    tilt: float = Field(ge=0.0, le=90.0)
    aspect: float = Field(ge=0.0, lt=360.0)


def _catalog_units(data: dict[str, Any]) -> dict[Variable, Unit]:
    """Canonical units for the variables in already-validated data."""
    values = data.get("values", {})
    return {variable: VARIABLES[variable].unit for variable in values}


class TimeSeries[TimeT: date](NabiaModel):
    """Column-oriented series of canonical variables at one location.

    Attributes:
        provider: Provider identifier (e.g. ``"open_meteo"``).
        dataset: Dataset or endpoint within the provider.
        location: Coordinates the data refer to (grid cell or station).
            They may differ from the requested point.
        elevation: Altitude in metres that the provider associates
            with the data, if known. Its meaning depends on the
            provider (see its README): Open-Meteo returns the terrain
            altitude of the requested point, which it uses to pick
            the grid cell and to correct temperatures, so it is not
            the altitude of ``location``; station data report the
            station altitude.
        timezone: IANA time zone used for timestamps and daily bounds.
        time: Strictly increasing time axis.
        values: Canonical variable to values aligned with ``time``;
            ``None`` marks a missing value.
        units: Canonical unit of each variable. Filled from the
            catalog when omitted; must match it when given (kept as a
            field so serialized series stay self-describing and can be
            loaded back).
        source: Model, product or station that produced the data,
            when known for certain. ``None`` when the provider picks
            the source itself without reporting it.
        source_kind: Nature of the data (forecast, reanalysis,
            observation...); ``None`` when it cannot be stated for
            the whole series.
        attribution: Credit line the provider's licence requires
            applications to display, if any.
        surface: Inclined surface that tilted variables refer to;
            required when the series holds one.
    """

    provider: str
    dataset: str
    location: GeoPoint
    elevation: float | None = None
    timezone: str
    time: tuple[TimeT, ...]
    values: dict[Variable, Values]
    units: dict[Variable, Unit] = Field(default_factory=_catalog_units)
    source: str | None = None
    source_kind: SourceKind | None = None
    attribution: str | None = None
    surface: Surface | None = None

    @model_validator(mode="after")
    def _check_axis(self) -> Self:
        if Variable.SHORTWAVE_RADIATION_TILTED in self.values and (
            self.surface is None
        ):
            raise ValueError("Tilted variables require the surface")
        expected_units = _catalog_units({"values": self.values})
        if self.units != expected_units:
            raise ValueError(
                "Units must match the canonical catalog: "
                f"expected {expected_units}, got {self.units}"
            )
        size = len(self.time)
        misaligned = [
            variable.value
            for variable, column in self.values.items()
            if len(column) != size
        ]
        if misaligned:
            raise ValueError(
                f"Columns not aligned with the time axis ({size}): "
                f"{', '.join(misaligned)}"
            )
        steps = pairwise(self.time)
        if any(later <= earlier for earlier, later in steps):
            raise ValueError("Time axis must be strictly increasing")
        return self

    @property
    def variables(self) -> tuple[Variable, ...]:
        """Variables present in the series, in request order."""
        return tuple(self.values)

    def to_dataframe(self) -> "pd.DataFrame":
        """Return a DataFrame indexed by time, one column per variable.

        Requires the ``pandas`` extra. Units and provenance are stored
        in ``DataFrame.attrs``.

        Raises:
            MissingDependencyError: pandas is not installed.
        """
        try:
            import pandas as pd
        except ImportError as exc:
            raise MissingDependencyError(
                "pandas is required: pip install 'nabia[pandas]'"
            ) from exc
        index = pd.DatetimeIndex(pd.to_datetime(list(self.time)), name="time")
        frame = pd.DataFrame(
            {var.value: list(col) for var, col in self.values.items()},
            index=index,
            dtype="float64",
        )
        frame.attrs.update(
            provider=self.provider,
            dataset=self.dataset,
            timezone=self.timezone,
            latitude=self.location.latitude,
            longitude=self.location.longitude,
            elevation=self.elevation,
            units={var.value: unit.value for var, unit in self.units.items()},
            source=self.source,
            source_kind=self.source_kind.value if self.source_kind else None,
            attribution=self.attribution,
        )
        return frame


class HourlySeries(TimeSeries[AwareDatetime]):
    """Hourly series; timestamps are timezone-aware datetimes."""

    resolution: Literal[Resolution.HOURLY] = Resolution.HOURLY


class DailySeries(TimeSeries[date]):
    """Daily series; each date is a calendar day in ``timezone``."""

    resolution: Literal[Resolution.DAILY] = Resolution.DAILY
