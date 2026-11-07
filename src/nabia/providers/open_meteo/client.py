"""Open-Meteo client: weather forecast and historical weather."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated, ClassVar

import httpx
from pydantic import Field, ValidationError, validate_call

from nabia.catalog import Resolution, Variable, VariableTable
from nabia.core.config import NabiaSettings
from nabia.core.http import HttpClient, Params
from nabia.core.models import DailySeries, GeoPoint, HourlySeries, SourceKind
from nabia.providers.base import BaseClient
from nabia.providers.open_meteo.config import OpenMeteoSettings
from nabia.providers.open_meteo.mapping import (
    ARCHIVE,
    ARCHIVE_SOURCES,
    DEFAULT_MODEL,
    FORECAST,
    UNIT_PARAMS,
)
from nabia.providers.open_meteo.parser import (
    Provenance,
    parse_daily,
    parse_hourly,
)
from nabia.providers.open_meteo.schemas import ErrorResponse, OpenMeteoResponse

#: First day covered by the historical archive.
ARCHIVE_START = date(1940, 1, 1)

ForecastDays = Annotated[int, Field(ge=1, le=16)]
PastDays = Annotated[int, Field(ge=0, le=92)]
Variables = Annotated[Sequence[Variable], Field(min_length=1)]
TimeZone = Annotated[str, Field(min_length=1)]

#: A single Open-Meteo model identifier. Comma-separated lists are
#: rejected: several models would rename the response columns.
Model = Annotated[str, Field(pattern=r"^[a-z0-9_]+$", max_length=64)]

#: Altitude in metres, between the lowest and highest land on Earth.
Elevation = Annotated[float, Field(ge=-500, le=9000)]


@dataclass(frozen=True)
class _Query:
    """Options shared by every request."""

    location: GeoPoint
    variables: tuple[Variable, ...]
    timezone: str
    model: str | None
    elevation: float | None


class OpenMeteoClient(BaseClient):
    """Client for the Open-Meteo forecast and historical weather APIs.

    Example:
        >>> from nabia import GeoPoint, Variable
        >>> with OpenMeteoClient() as client:  # doctest: +SKIP
        ...     series = client.forecast_daily(
        ...         GeoPoint(latitude=40.42, longitude=-3.70),
        ...         [Variable.PRECIPITATION, Variable.RAIN],
        ...     )

    Args:
        settings: Open-Meteo settings; read from the environment if
            omitted.
        nabia_settings: Shared HTTP/cache settings.
        http: Pre-built HTTP client (advanced use and tests).
    """

    PROVIDER: ClassVar[str] = "open_meteo"

    def __init__(
        self,
        settings: OpenMeteoSettings | None = None,
        *,
        nabia_settings: NabiaSettings | None = None,
        http: HttpClient | None = None,
    ) -> None:
        super().__init__(
            nabia_settings=nabia_settings,
            error_parser=_parse_error,
            http=http,
        )
        self._settings = settings or OpenMeteoSettings()

    @validate_call
    def forecast_hourly(
        self,
        location: GeoPoint,
        variables: Variables,
        *,
        days: ForecastDays = 7,
        past_days: PastDays = 0,
        timezone: TimeZone = "auto",
        model: Model | None = None,
        elevation: Elevation | None = None,
    ) -> HourlySeries:
        """Return an hourly forecast.

        Args:
            location: Point to query; Open-Meteo picks a grid cell.
            variables: Canonical variables to retrieve.
            days: Forecast horizon in days, including today (1-16).
            past_days: Days before today to include (0-92).
            timezone: IANA zone name, or ``"auto"`` for the zone of
                ``location``.
            model: Forecast model (e.g. ``"icon_eu"``). By default
                Open-Meteo combines the best models per location
                without reporting which ones.
            elevation: Altitude of the point in metres. By default
                Open-Meteo takes it from a 90 m terrain model; it is
                used to pick the grid cell and correct temperatures.
        """
        query = _Query(
            location, _unique(variables), timezone, model, elevation
        )
        extra = {"forecast_days": days, "past_days": past_days}
        return self._hourly(
            FORECAST, self._settings.forecast_url, query, extra
        )

    @validate_call
    def forecast_daily(
        self,
        location: GeoPoint,
        variables: Variables,
        *,
        days: ForecastDays = 7,
        past_days: PastDays = 0,
        timezone: TimeZone = "auto",
        model: Model | None = None,
        elevation: Elevation | None = None,
    ) -> DailySeries:
        """Daily variant of :meth:`forecast_hourly`."""
        query = _Query(
            location, _unique(variables), timezone, model, elevation
        )
        extra = {"forecast_days": days, "past_days": past_days}
        return self._daily(FORECAST, self._settings.forecast_url, query, extra)

    @validate_call
    def historical_hourly(
        self,
        location: GeoPoint,
        variables: Variables,
        *,
        start: date,
        end: date,
        timezone: TimeZone = "auto",
        model: Model | None = None,
        elevation: Elevation | None = None,
    ) -> HourlySeries:
        """Return hourly historical data (reanalysis and analyses).

        Args:
            location: Point to query; Open-Meteo picks a grid cell.
            variables: Canonical variables to retrieve.
            start: First day, inclusive (from 1940-01-01).
            end: Last day, inclusive. Recent days may be unavailable
                for a few days after real time.
            timezone: IANA zone name, or ``"auto"``.
            model: Archive source, e.g. ``"era5"`` for a homogeneous
                series since 1940 or ``"ecmwf_ifs"`` for recent, finer
                data. By default Open-Meteo picks one per date without
                reporting it, so long series may mix sources.
            elevation: Altitude of the point in metres (see
                :meth:`forecast_hourly`).
        """
        query = _Query(
            location, _unique(variables), timezone, model, elevation
        )
        extra = _date_range(start, end)
        return self._hourly(ARCHIVE, self._settings.archive_url, query, extra)

    @validate_call
    def historical_daily(
        self,
        location: GeoPoint,
        variables: Variables,
        *,
        start: date,
        end: date,
        timezone: TimeZone = "auto",
        model: Model | None = None,
        elevation: Elevation | None = None,
    ) -> DailySeries:
        """Daily variant of :meth:`historical_hourly`."""
        query = _Query(
            location, _unique(variables), timezone, model, elevation
        )
        extra = _date_range(start, end)
        return self._daily(ARCHIVE, self._settings.archive_url, query, extra)

    # -- internals --------------------------------------

    def _hourly(
        self,
        table: VariableTable,
        url: str,
        query: _Query,
        extra: Params,
    ) -> HourlySeries:
        names = table.native_names(Resolution.HOURLY, query.variables)
        params = {
            **_base_params(query),
            **extra,
            "hourly": ",".join(names),
            "timeformat": "unixtime",
        }
        raw = self._http.get_model(OpenMeteoResponse, url, params=params)
        provenance = _provenance(table, query.model)
        return parse_hourly(raw, table, query.variables, provenance)

    def _daily(
        self,
        table: VariableTable,
        url: str,
        query: _Query,
        extra: Params,
    ) -> DailySeries:
        names = table.native_names(Resolution.DAILY, query.variables)
        params = {
            **_base_params(query),
            **extra,
            "daily": ",".join(names),
            "timeformat": "iso8601",
        }
        raw = self._http.get_model(OpenMeteoResponse, url, params=params)
        provenance = _provenance(table, query.model)
        return parse_daily(raw, table, query.variables, provenance)


def _base_params(query: _Query) -> dict[str, str]:
    params = {
        "latitude": str(query.location.latitude),
        "longitude": str(query.location.longitude),
        "timezone": query.timezone,
        **UNIT_PARAMS,
    }
    if query.model is not None:
        params["models"] = query.model
    if query.elevation is not None:
        params["elevation"] = str(query.elevation)
    return params


def _provenance(table: VariableTable, model: str | None) -> Provenance:
    # The default model hides which source answered, so nothing is
    # claimed about it beyond what holds for the whole dataset.
    source = None if model in (None, DEFAULT_MODEL) else model
    if table.dataset == FORECAST.dataset:
        return Provenance(source=source, source_kind=SourceKind.FORECAST)
    kind = ARCHIVE_SOURCES.get(source) if source else None
    return Provenance(source=source, source_kind=kind)


def _date_range(start: date, end: date) -> Mapping[str, str]:
    if end < start:
        raise ValueError(f"end ({end}) must not be before start ({start})")
    if start < ARCHIVE_START:
        raise ValueError(f"start must be on or after {ARCHIVE_START}")
    return {"start_date": start.isoformat(), "end_date": end.isoformat()}


def _unique(variables: Sequence[Variable]) -> tuple[Variable, ...]:
    # Preserve request order while dropping duplicates.
    return tuple(dict.fromkeys(variables))


def _parse_error(response: httpx.Response) -> str | None:
    try:
        return ErrorResponse.model_validate_json(response.content).reason
    except ValidationError:
        return None
