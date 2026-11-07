"""Convert raw Open-Meteo responses into normalized Nabia series."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, ValidationError

from nabia.catalog import Resolution, Variable, VariableTable
from nabia.core.errors import ProviderContractError
from nabia.core.models import (
    DailySeries,
    GeoPoint,
    HourlySeries,
    SourceKind,
    Surface,
)
from nabia.providers.open_meteo.mapping import ATTRIBUTION
from nabia.providers.open_meteo.schemas import OpenMeteoResponse

PROVIDER = "open_meteo"


class Provenance(BaseModel):
    """What is known about where a response's data come from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str | None = None
    source_kind: SourceKind | None = None


def parse_hourly(
    raw: OpenMeteoResponse,
    table: VariableTable,
    variables: Sequence[Variable],
    provenance: Provenance,
    surface: Surface | None = None,
) -> HourlySeries:
    """Build an :class:`HourlySeries` from a ``unixtime`` response.

    Unix timestamps are unambiguous UTC instants; they are expressed in
    the response time zone so local wall-clock time is preserved,
    including daylight saving transitions.
    """
    if raw.hourly is None:
        raise _missing_block("hourly")
    zone = _zone(raw)
    values = table.extract(
        Resolution.HOURLY,
        variables,
        raw.hourly.columns,
        raw.hourly_units,
        source=provenance.source,
    )
    try:
        return HourlySeries(
            provider=PROVIDER,
            dataset=table.dataset,
            location=_location(raw),
            elevation=raw.elevation,
            timezone=raw.timezone,
            time=tuple(
                datetime.fromtimestamp(ts, UTC).astimezone(zone)
                for ts in raw.hourly.time
            ),
            values=values,
            source=provenance.source,
            source_kind=provenance.source_kind,
            attribution=ATTRIBUTION,
            surface=surface,
        )
    except ValidationError as exc:
        raise _invalid_series(exc) from None


def parse_daily(
    raw: OpenMeteoResponse,
    table: VariableTable,
    variables: Sequence[Variable],
    provenance: Provenance,
) -> DailySeries:
    """Build a :class:`DailySeries` from an ``iso8601`` response."""
    if raw.daily is None:
        raise _missing_block("daily")
    values = table.extract(
        Resolution.DAILY,
        variables,
        raw.daily.columns,
        raw.daily_units,
        source=provenance.source,
    )
    try:
        return DailySeries(
            provider=PROVIDER,
            dataset=table.dataset,
            location=_location(raw),
            elevation=raw.elevation,
            timezone=raw.timezone,
            time=tuple(raw.daily.time),
            values=values,
            source=provenance.source,
            source_kind=provenance.source_kind,
            attribution=ATTRIBUTION,
        )
    except ValidationError as exc:
        raise _invalid_series(exc) from None


def _location(raw: OpenMeteoResponse) -> GeoPoint:
    return GeoPoint(latitude=raw.latitude, longitude=raw.longitude)


def _zone(raw: OpenMeteoResponse) -> tzinfo:
    try:
        return ZoneInfo(raw.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        # Unknown zone name: fall back to the fixed offset reported.
        offset = timedelta(seconds=raw.utc_offset_seconds)
        return timezone(offset, raw.timezone)


def _missing_block(name: str) -> ProviderContractError:
    return ProviderContractError(
        f"{PROVIDER}: response has no {name!r} block",
        provider=PROVIDER,
    )


def _invalid_series(exc: ValidationError) -> ProviderContractError:
    return ProviderContractError(
        f"{PROVIDER}: response cannot form a valid series: "
        f"{exc.errors()[0]['msg']}",
        provider=PROVIDER,
    )
