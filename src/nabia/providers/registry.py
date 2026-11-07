"""Registry of every provider equivalence table.

Used by ``python -m nabia.catalog`` and by the test-suite. Imports are
local so that loading one provider never imports the others.
"""

from nabia.catalog import VariableTable


def all_tables() -> tuple[VariableTable, ...]:
    """Return every registered provider table."""
    from nabia.providers.open_meteo.mapping import ARCHIVE, FORECAST

    return (FORECAST, ARCHIVE)
