"""Print the cross-provider equivalence table as Markdown.

Usage::

    python -m nabia.catalog
"""

import sys

from nabia.catalog import VARIABLES, Resolution, VariableTable
from nabia.providers.registry import all_tables


def render(tables: tuple[VariableTable, ...]) -> str:
    """Render one Markdown table per resolution."""
    lines: list[str] = []
    for resolution in Resolution:
        headers = ["variable", "unit"] + [
            f"{t.provider}/{t.dataset}" for t in tables
        ]
        lines += [
            f"## {resolution}",
            "",
            "| " + " | ".join(headers) + " |",
            "|" + "---|" * len(headers),
        ]
        for variable, spec in VARIABLES.items():
            if resolution not in spec.resolutions:
                continue
            cells = []
            for table in tables:
                native = table.entries(resolution).get(variable)
                cells.append(
                    f"`{native.name}` ({native.unit.value})" if native else "-"
                )
            row = [variable.value, spec.unit.value, *cells]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    verified = ", ".join(
        f"{t.provider}/{t.dataset}: {t.verified_on.isoformat()}"
        for t in tables
    )
    lines.append(f"Last verified: {verified}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Write the rendered table to stdout."""
    sys.stdout.write(render(all_tables()))


if __name__ == "__main__":
    main()
