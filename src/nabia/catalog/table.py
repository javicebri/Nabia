"""Equivalence tables between canonical variables and provider names.

A :class:`VariableTable` declares, for one provider dataset, the native
name and the unit the provider reports for each canonical variable.
Tables protect consumers from upstream drift in three ways:

1. At import time, the table is validated against :data:`VARIABLES`
   (allowed resolutions, convertible units). A bad edit fails fast.
2. At runtime, :meth:`VariableTable.extract` checks that every native
   column is present and that the unit reported by the provider still
   matches the table, raising instead of returning wrong data.
3. Live tests (``pytest -m live``) exercise every mapped variable
   against the real API; ``verified_on`` records the last successful
   check.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nabia.catalog.units import Unit, can_convert, convert
from nabia.catalog.variables import VARIABLES, Resolution, Variable
from nabia.core.errors import (
    ProviderContractError,
    UnitMismatchError,
    UnsupportedVariableError,
)

#: Column of raw values as delivered by a provider.
RawColumn = Sequence[float | None]

#: Converted values of one variable, aligned with the series time axis.
Values = tuple[float | None, ...]


class NativeVariable(BaseModel):
    """How a provider names and measures one canonical variable.

    Attributes:
        name: Identifier used by the provider API.
        unit: Unit the provider reports for that identifier.
        notes: Caveats on the provider definition, if any.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    unit: Unit
    notes: str = ""


class VariableTable(BaseModel):
    """Equivalence table for one provider dataset.

    Attributes:
        provider: Provider identifier (e.g. ``"open_meteo"``).
        dataset: Dataset or endpoint within the provider.
        reference_url: Documentation the table was built from.
        verified_on: Last date the table was checked against the API.
        hourly: Canonical to native mapping for hourly series.
        daily: Canonical to native mapping for daily series.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    dataset: str
    reference_url: str
    verified_on: date
    hourly: dict[Variable, NativeVariable] = Field(default_factory=dict)
    daily: dict[Variable, NativeVariable] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_against_catalog(self) -> Self:
        problems: list[str] = []
        for resolution in Resolution:
            for variable, native in self.entries(resolution).items():
                spec = VARIABLES[variable]
                if resolution not in spec.resolutions:
                    problems.append(
                        f"{variable.value} is not defined for {resolution}"
                    )
                if not can_convert(native.unit, spec.unit):
                    problems.append(
                        f"{variable.value}: cannot convert "
                        f"{native.unit.value} to {spec.unit.value}"
                    )
        if problems:
            raise ValueError(
                f"Invalid table {self.provider}/{self.dataset}: "
                + "; ".join(problems)
            )
        return self

    def entries(
        self, resolution: Resolution
    ) -> Mapping[Variable, NativeVariable]:
        """Return the mapping for ``resolution``."""
        if resolution is Resolution.HOURLY:
            return self.hourly
        return self.daily

    def supported(self, resolution: Resolution) -> frozenset[Variable]:
        """Return the canonical variables offered at ``resolution``."""
        return frozenset(self.entries(resolution))

    def native_names(
        self, resolution: Resolution, variables: Sequence[Variable]
    ) -> tuple[str, ...]:
        """Translate canonical variables into native names.

        Raises:
            UnsupportedVariableError: A variable is not in the table.
        """
        entries = self.entries(resolution)
        missing = [v.value for v in variables if v not in entries]
        if missing:
            available = ", ".join(sorted(v.value for v in entries))
            raise UnsupportedVariableError(
                f"{self.provider}/{self.dataset} does not provide "
                f"{', '.join(missing)} at {resolution} resolution. "
                f"Available: {available}"
            )
        return tuple(entries[v].name for v in variables)

    def extract(
        self,
        resolution: Resolution,
        variables: Sequence[Variable],
        columns: Mapping[str, RawColumn],
        reported_units: Mapping[str, str] | None,
    ) -> dict[Variable, Values]:
        """Pick, verify and convert native columns to canonical values.

        Args:
            resolution: Resolution of the response.
            variables: Canonical variables that were requested.
            columns: Native name to raw values, as returned upstream.
            reported_units: Native name to unit string, when the
                provider reports units; ``None`` skips the unit check.

        Raises:
            ProviderContractError: A requested column is missing.
            UnitMismatchError: The reported unit differs from the table.
        """
        entries = self.entries(resolution)
        result: dict[Variable, Values] = {}
        for variable in variables:
            native = entries[variable]
            if native.name not in columns:
                raise ProviderContractError(
                    f"{self.provider}/{self.dataset}: column "
                    f"{native.name!r} missing from response "
                    f"(canonical: {variable.value})",
                    provider=self.provider,
                )
            if reported_units is not None:
                reported = reported_units.get(native.name)
                if reported != native.unit.value:
                    raise UnitMismatchError(
                        f"{self.provider}/{self.dataset}: {native.name!r}"
                        f" reported in {reported!r}, table expects "
                        f"{native.unit.value!r}. Review the table.",
                        provider=self.provider,
                    )
            result[variable] = convert(
                columns[native.name], native.unit, VARIABLES[variable].unit
            )
        return result
