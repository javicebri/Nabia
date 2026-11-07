"""Open-Meteo client: weather forecast and historical reanalysis."""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Annotated, ClassVar

import httpx
from pydantic import Field, ValidationError, validate_call

from nabia.catalog import Resolution, Variable, VariableTable
from nabia.core.config import NabiaSettings
from nabia.core.http import HttpClient, Params
from nabia.core.models import DailySeries, GeoPoint, HourlySeries
from nabia.providers.base import BaseClient
from nabia.providers.open_meteo.config import OpenMeteoSettings
from nabia.providers.open_meteo.mapping import ARCHIVE, FORECAST, UNIT_PARAMS
from nabia.providers.open_meteo.parser import parse_daily, parse_hourly
from nabia.providers.open_meteo.schemas import ErrorResponse, OpenMeteoResponse

#: First day covered by the historical (ERA5) archive.
ARCHIVE_START = date(1940, 1, 1)

ForecastDays = Annotated[int, Field(ge=1, le=16)]
PastDays = Annotated[int, Field(ge=0, le=92)]
Variables = Annotated[Sequence[Variable], Field(min_length=1)]
TimeZone = Annotated[str, Field(min_length=1)]


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
    ) -> HourlySeries:
        """Return an hourly forecast.

        Args:
            location: Point to query; Open-Meteo snaps it to its grid.
            variables: Canonical variables to retrieve.
            days: Forecast horizon in days, including today (1-16).
            past_days: Days before today to include (0-92).
            timezone: IANA zone name, or ``"auto"`` for the zone of
                ``location``.
        """
        extra = {"forecast_days": days, "past_days": past_days}
        return self._hourly(
            FORECAST,
            self._settings.forecast_url,
            location,
            variables,
            timezone,
            extra,
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
    ) -> DailySeries:
        """Daily variant of :meth:`forecast_hourly`."""
        extra = {"forecast_days": days, "past_days": past_days}
        return self._daily(
            FORECAST,
            self._settings.forecast_url,
            location,
            variables,
            timezone,
            extra,
        )

    @validate_call
    def historical_hourly(
        self,
        location: GeoPoint,
        variables: Variables,
        *,
        start: date,
        end: date,
        timezone: TimeZone = "auto",
    ) -> HourlySeries:
        """Return hourly historical data (ERA5-based reanalysis).

        Args:
            location: Point to query; Open-Meteo snaps it to its grid.
            variables: Canonical variables to retrieve.
            start: First day, inclusive (from 1940-01-01).
            end: Last day, inclusive. Recent days may be unavailable
                for a few days after real time.
            timezone: IANA zone name, or ``"auto"``.
        """
        return self._hourly(
            ARCHIVE,
            self._settings.archive_url,
            location,
            variables,
            timezone,
            _date_range(start, end),
        )

    @validate_call
    def historical_daily(
        self,
        location: GeoPoint,
        variables: Variables,
        *,
        start: date,
        end: date,
        timezone: TimeZone = "auto",
    ) -> DailySeries:
        """Daily variant of :meth:`historical_hourly`."""
        return self._daily(
            ARCHIVE,
            self._settings.archive_url,
            location,
            variables,
            timezone,
            _date_range(start, end),
        )

    # -- internals --------------------------------------

    def _hourly(
        self,
        table: VariableTable,
        url: str,
        location: GeoPoint,
        variables: Sequence[Variable],
        timezone: str,
        extra: Params,
    ) -> HourlySeries:
        unique = _unique(variables)
        names = table.native_names(Resolution.HOURLY, unique)
        params = {
            **_base_params(location, timezone),
            **extra,
            "hourly": ",".join(names),
            "timeformat": "unixtime",
        }
        raw = self._http.get_model(OpenMeteoResponse, url, params=params)
        return parse_hourly(raw, table, unique)

    def _daily(
        self,
        table: VariableTable,
        url: str,
        location: GeoPoint,
        variables: Sequence[Variable],
        timezone: str,
        extra: Params,
    ) -> DailySeries:
        unique = _unique(variables)
        names = table.native_names(Resolution.DAILY, unique)
        params = {
            **_base_params(location, timezone),
            **extra,
            "daily": ",".join(names),
            "timeformat": "iso8601",
        }
        raw = self._http.get_model(OpenMeteoResponse, url, params=params)
        return parse_daily(raw, table, unique)


def _base_params(location: GeoPoint, timezone: str) -> dict[str, str]:
    return {
        "latitude": str(location.latitude),
        "longitude": str(location.longitude),
        "timezone": timezone,
        **UNIT_PARAMS,
    }


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
