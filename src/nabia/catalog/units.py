"""Units understood by Nabia and conversions between them.

Enum values are the exact symbols used in Nabia output. Providers that
report units as strings are compared against these values, so a silent
unit change upstream is detected instead of corrupting data.
"""

from collections.abc import Callable, Iterable
from enum import StrEnum
from types import MappingProxyType

from nabia.core.errors import UnitConversionError


class Unit(StrEnum):
    """Physical units (value = symbol used in output)."""

    CELSIUS = "°C"
    KELVIN = "K"
    PERCENT = "%"
    MILLIMETRE = "mm"
    METRE_PER_SECOND = "m/s"
    KILOMETRE_PER_HOUR = "km/h"
    DEGREE = "°"
    PASCAL = "Pa"
    HECTOPASCAL = "hPa"
    KILOPASCAL = "kPa"
    WATT_PER_SQUARE_METRE = "W/m²"
    JOULE_PER_SQUARE_METRE = "J/m²"
    MEGAJOULE_PER_SQUARE_METRE = "MJ/m²"
    SECOND = "s"
    HOUR = "h"


#: A single-value unit conversion.
Converter = Callable[[float], float]

_CONVERSIONS: MappingProxyType[tuple[Unit, Unit], Converter] = (
    MappingProxyType(
        {
            (Unit.KELVIN, Unit.CELSIUS): lambda v: v - 273.15,
            (Unit.KILOMETRE_PER_HOUR, Unit.METRE_PER_SECOND): (
                lambda v: v / 3.6
            ),
            (Unit.PASCAL, Unit.HECTOPASCAL): lambda v: v / 100.0,
            (Unit.JOULE_PER_SQUARE_METRE, Unit.MEGAJOULE_PER_SQUARE_METRE): (
                lambda v: v / 1_000_000.0
            ),
            (Unit.SECOND, Unit.HOUR): lambda v: v / 3600.0,
        }
    )
)


def can_convert(source: Unit, target: Unit) -> bool:
    """Return whether ``source`` converts to ``target``."""
    return source == target or (source, target) in _CONVERSIONS


def convert(
    values: Iterable[float | None], source: Unit, target: Unit
) -> tuple[float | None, ...]:
    """Convert values between units, preserving missing values.

    Raises:
        UnitConversionError: No conversion is defined for the pair.
    """
    if source == target:
        return tuple(values)
    try:
        converter = _CONVERSIONS[(source, target)]
    except KeyError:
        raise UnitConversionError(
            f"No conversion defined from {source.value!r} to {target.value!r}"
        ) from None
    return tuple(None if v is None else converter(v) for v in values)
