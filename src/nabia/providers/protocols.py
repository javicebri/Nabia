"""Capability protocols for provider-agnostic consumer code.

Consumers can type against a capability instead of a concrete client,
so switching providers is a one-line change::

    def rainfall(source: HistoricalDailyProvider) -> DailySeries:
        return source.historical_daily(
            point, [Variable.PRECIPITATION], start=start, end=end
        )
"""

from collections.abc import Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from nabia.catalog import Variable
from nabia.core.models import DailySeries, GeoPoint, HourlySeries


@runtime_checkable
class ForecastHourlyProvider(Protocol):
    """Provides hourly forecasts."""

    def forecast_hourly(
        self,
        location: GeoPoint,
        variables: Sequence[Variable],
        *,
        days: int = ...,
    ) -> HourlySeries:
        """Return an hourly forecast for the next ``days`` days."""
        ...


@runtime_checkable
class ForecastDailyProvider(Protocol):
    """Provides daily forecasts."""

    def forecast_daily(
        self,
        location: GeoPoint,
        variables: Sequence[Variable],
        *,
        days: int = ...,
    ) -> DailySeries:
        """Return a daily forecast for the next ``days`` days."""
        ...


@runtime_checkable
class HistoricalHourlyProvider(Protocol):
    """Provides hourly historical data."""

    def historical_hourly(
        self,
        location: GeoPoint,
        variables: Sequence[Variable],
        *,
        start: date,
        end: date,
    ) -> HourlySeries:
        """Return hourly data from ``start`` to ``end`` inclusive."""
        ...


@runtime_checkable
class HistoricalDailyProvider(Protocol):
    """Provides daily historical data."""

    def historical_daily(
        self,
        location: GeoPoint,
        variables: Sequence[Variable],
        *,
        start: date,
        end: date,
    ) -> DailySeries:
        """Return daily data from ``start`` to ``end`` inclusive."""
        ...
