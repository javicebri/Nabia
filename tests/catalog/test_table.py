from datetime import date

import pytest
from pydantic import ValidationError

from nabia.catalog import (
    VARIABLES,
    NativeVariable,
    Resolution,
    Unit,
    Variable,
    VariableTable,
)
from nabia.catalog.__main__ import render
from nabia.core.errors import (
    NoDataError,
    ProviderContractError,
    UnitMismatchError,
    UnsupportedVariableError,
)
from nabia.providers.registry import all_tables

TODAY = date(2026, 1, 1)


def table(**hourly: NativeVariable) -> VariableTable:
    return VariableTable(
        provider="p",
        dataset="d",
        reference_url="https://example.org",
        verified_on=TODAY,
        hourly={Variable(name): native for name, native in hourly.items()},
    )


SUNSHINE = table(
    sunshine_duration=NativeVariable(name="sun", unit=Unit.SECOND)
)


def test_every_variable_has_a_spec() -> None:
    assert set(VARIABLES) == set(Variable)


@pytest.mark.parametrize("tbl", all_tables(), ids=lambda t: t.dataset)
def test_registered_tables_are_consistent(tbl: VariableTable) -> None:
    assert tbl.hourly or tbl.daily
    assert tbl.verified_on <= date.today()  # noqa: DTZ011
    assert tbl.reference_url.startswith("https://")


def test_resolution_must_be_allowed() -> None:
    with pytest.raises(ValidationError, match="not defined for hourly"):
        table(air_temperature_max=NativeVariable(name="x", unit=Unit.CELSIUS))


def test_unit_must_be_convertible() -> None:
    with pytest.raises(ValidationError, match="cannot convert"):
        table(air_temperature=NativeVariable(name="x", unit=Unit.PERCENT))


def test_native_names_reports_unsupported() -> None:
    with pytest.raises(UnsupportedVariableError, match="Available: sunshine"):
        SUNSHINE.native_names(Resolution.HOURLY, [Variable.AIR_TEMPERATURE])


def test_extract_converts_units() -> None:
    values = SUNSHINE.extract(
        Resolution.HOURLY,
        [Variable.SUNSHINE_DURATION],
        {"sun": [3600.0, None]},
        {"sun": "s"},
    )
    assert values == {Variable.SUNSHINE_DURATION: (1.0, None)}


def test_extract_detects_unit_drift() -> None:
    with pytest.raises(UnitMismatchError, match="'min'"):
        SUNSHINE.extract(
            Resolution.HOURLY,
            [Variable.SUNSHINE_DURATION],
            {"sun": [60.0]},
            {"sun": "min"},
        )


def test_extract_detects_missing_column() -> None:
    with pytest.raises(ProviderContractError, match="'sun' missing"):
        SUNSHINE.extract(
            Resolution.HOURLY, [Variable.SUNSHINE_DURATION], {}, None
        )


def test_render_cross_provider_table() -> None:
    output = render(all_tables())
    assert "## hourly" in output
    assert "| air_temperature | °C | `temperature_2m` (°C)" in output
    assert "Last verified:" in output


def test_extract_rejects_an_entirely_empty_column() -> None:
    with pytest.raises(NoDataError, match="with source 'x'"):
        SUNSHINE.extract(
            Resolution.HOURLY,
            [Variable.SUNSHINE_DURATION],
            {"sun": [None, None]},
            {"sun": "s"},
            source="x",
        )


def test_extract_accepts_an_empty_time_axis() -> None:
    values = SUNSHINE.extract(
        Resolution.HOURLY, [Variable.SUNSHINE_DURATION], {"sun": []}, None
    )
    assert values == {Variable.SUNSHINE_DURATION: ()}
