"""Raw Open-Meteo response schemas (mirror of the upstream JSON).

Only the fields Nabia relies on are declared. Unknown top-level fields
are ignored, so additive upstream changes do not break parsing, while
missing or retyped fields raise a contract error.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class _Block(BaseModel):
    """Time axis plus one column per requested variable."""

    model_config = ConfigDict(extra="allow")

    __pydantic_extra__: dict[str, list[float | None]] = Field(init=False)

    @property
    def columns(self) -> dict[str, list[float | None]]:
        """Variable columns keyed by native name."""
        return dict(self.__pydantic_extra__)


class HourlyBlock(_Block):
    """Hourly block requested with ``timeformat=unixtime``."""

    time: list[int]


class DailyBlock(_Block):
    """Daily block requested with ``timeformat=iso8601``."""

    time: list[date]


class OpenMeteoResponse(BaseModel):
    """Successful forecast or archive response."""

    model_config = ConfigDict(extra="ignore")

    latitude: float
    longitude: float
    elevation: float | None = None
    timezone: str
    utc_offset_seconds: int
    hourly_units: dict[str, str] | None = None
    hourly: HourlyBlock | None = None
    daily_units: dict[str, str] | None = None
    daily: DailyBlock | None = None


class ErrorResponse(BaseModel):
    """Error payload returned with HTTP 400."""

    error: bool
    reason: str
