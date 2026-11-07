import pytest

from nabia.catalog import Unit, can_convert, convert
from nabia.core.errors import UnitConversionError


@pytest.mark.parametrize(
    ("source", "target", "value", "expected"),
    [
        (Unit.CELSIUS, Unit.CELSIUS, 12.5, 12.5),
        (Unit.KELVIN, Unit.CELSIUS, 273.15, 0.0),
        (Unit.KILOMETRE_PER_HOUR, Unit.METRE_PER_SECOND, 36.0, 10.0),
        (Unit.PASCAL, Unit.HECTOPASCAL, 101_325.0, 1013.25),
        (Unit.JOULE_PER_SQUARE_METRE, Unit.MEGAJOULE_PER_SQUARE_METRE, 2e6, 2),
        (Unit.SECOND, Unit.HOUR, 5400.0, 1.5),
    ],
)
def test_conversions(
    source: Unit, target: Unit, value: float, expected: float
) -> None:
    assert can_convert(source, target)
    (result,) = convert([value], source, target)
    assert result == pytest.approx(expected)


def test_missing_values_are_preserved() -> None:
    assert convert([3600.0, None], Unit.SECOND, Unit.HOUR) == (1.0, None)


def test_undefined_conversion_raises() -> None:
    assert not can_convert(Unit.CELSIUS, Unit.PERCENT)
    with pytest.raises(UnitConversionError):
        convert([1.0], Unit.CELSIUS, Unit.PERCENT)
