"""Units understood by Nabia and conversions between them.

Enum values are the exact symbols used in Nabia output. Providers that
report units as strings are compared against these values, so a silent
unit change upstream is detected instead of corrupting data.
"""

from collections.abc import Iterable
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class Conversion:
    """Affine unit conversion: ``(value - offset) / divisor``.

    Conversions are declared as data rather than code so that ports to
    other languages (generated from ``contract/``) evaluate the same
    expression and reproduce Nabia's results bit for bit.

    Attributes:
        offset: Subtracted from the value first.
        divisor: The difference is then divided by it.
    """

    offset: float = 0.0
    divisor: float = 1.0

    def apply(self, value: float) -> float:
        """Convert one value."""
        return (value - self.offset) / self.divisor


#: Every supported conversion, keyed by ``(source, target)``.
CONVERSIONS: MappingProxyType[tuple[Unit, Unit], Conversion] = (
    MappingProxyType(
        {
            (Unit.KELVIN, Unit.CELSIUS): Conversion(offset=273.15),
            (Unit.KILOMETRE_PER_HOUR, Unit.METRE_PER_SECOND): Conversion(
                divisor=3.6
            ),
            (Unit.PASCAL, Unit.HECTOPASCAL): Conversion(divisor=100.0),
            (Unit.JOULE_PER_SQUARE_METRE, Unit.MEGAJOULE_PER_SQUARE_METRE): (
                Conversion(divisor=1_000_000.0)
            ),
            (Unit.SECOND, Unit.HOUR): Conversion(divisor=3600.0),
        }
    )
)


def can_convert(source: Unit, target: Unit) -> bool:
    """Return whether ``source`` converts to ``target``."""
    return source == target or (source, target) in CONVERSIONS


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
        conversion = CONVERSIONS[(source, target)]
    except KeyError:
        raise UnitConversionError(
            f"No conversion defined from {source.value!r} to {target.value!r}"
        ) from None
    return tuple(None if v is None else conversion.apply(v) for v in values)
