"""Canonical vocabulary (variables, units) and provider equivalences.

Run ``python -m nabia.catalog`` to print the cross-provider table.
"""

from nabia.catalog.table import NativeVariable, Values, VariableTable
from nabia.catalog.units import Unit, can_convert, convert
from nabia.catalog.variables import (
    VARIABLES,
    Aggregation,
    Resolution,
    Variable,
    VariableSpec,
)

__all__ = [
    "VARIABLES",
    "Aggregation",
    "NativeVariable",
    "Resolution",
    "Unit",
    "Values",
    "Variable",
    "VariableSpec",
    "VariableTable",
    "can_convert",
    "convert",
]
