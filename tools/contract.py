"""Export Nabia's language-neutral contract to ``contract/``.

Python is the reference implementation. Ports to other languages (the
Dart package) generate their code from these JSON files instead of
copying the Python sources, so the vocabulary, the unit conversions and
the provider tables are maintained in one place. Run it after changing
the catalog, the output models or a provider mapping::

    uv run python -m tools.contract

``tests/test_contract.py`` fails while the committed files are stale.
Bump :data:`CONTRACT_VERSION` when the structure of a file changes in
a way existing generators cannot read.
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic.json_schema import models_json_schema

from nabia.catalog import (
    CONVERSIONS,
    VARIABLES,
    Aggregation,
    Resolution,
    Unit,
    VariableTable,
)
from nabia.core.models import DailySeries, HourlySeries, SourceKind
from tools import conformance

#: Version of the structure of the exported files.
CONTRACT_VERSION = 1

#: Directory holding the committed contract.
CONTRACT_DIR = Path(__file__).resolve().parent.parent / "contract"

#: A JSON document.
Document = dict[str, Any]


def unit_key(unit: Unit) -> str:
    """Return the identifier that references ``unit`` in the contract.

    The unit value is a symbol (``"°C"``); the key is a stable
    identifier (``"celsius"``) suitable for generated code.
    """
    return unit.name.lower()


def catalog() -> Document:
    """Return the canonical vocabulary and the unit conversions."""
    return {
        "contract_version": CONTRACT_VERSION,
        "units": {unit_key(unit): unit.value for unit in Unit},
        "conversions": [
            {
                "from": unit_key(source),
                "to": unit_key(target),
                "offset": conversion.offset,
                "divisor": conversion.divisor,
            }
            for (source, target), conversion in CONVERSIONS.items()
        ],
        "resolutions": [resolution.value for resolution in Resolution],
        "aggregations": [aggregation.value for aggregation in Aggregation],
        "source_kinds": [kind.value for kind in SourceKind],
        "variables": {
            variable.value: {
                "unit": unit_key(spec.unit),
                "aggregation": spec.aggregation.value,
                "resolutions": [
                    resolution.value
                    for resolution in Resolution
                    if resolution in spec.resolutions
                ],
                "description": spec.description,
            }
            for variable, spec in VARIABLES.items()
        },
    }


def models_schema() -> Document:
    """Return the JSON Schema of the serialized output models.

    The schema describes the shape only; the cross-field rules of the
    models are listed in ``contract/README.md``.
    """
    _, schema = models_json_schema(
        [(HourlySeries, "serialization"), (DailySeries, "serialization")],
        title="Nabia output models",
    )
    return schema


def _table(table: VariableTable) -> Document:
    """Return one dataset table, native names and units included."""
    document: Document = {
        "reference_url": table.reference_url,
        "verified_on": table.verified_on.isoformat(),
    }
    for resolution in Resolution:
        document[resolution.value] = {
            variable.value: {
                "name": native.name,
                "unit": unit_key(native.unit),
                "notes": native.notes,
            }
            for variable, native in table.entries(resolution).items()
        }
    return document


def open_meteo() -> Document:
    """Return the Open-Meteo provider contract.

    It holds the provider's ``mapping.py`` and its default endpoints.
    """
    from nabia.providers.open_meteo import OpenMeteoSettings, mapping

    defaults = OpenMeteoSettings.model_construct()
    return {
        "contract_version": CONTRACT_VERSION,
        "provider": "open_meteo",
        "endpoints": {
            mapping.FORECAST.dataset: defaults.forecast_url,
            mapping.ARCHIVE.dataset: defaults.archive_url,
        },
        "attribution": mapping.ATTRIBUTION,
        "default_model": mapping.DEFAULT_MODEL,
        "unit_params": dict(mapping.UNIT_PARAMS),
        "archive_sources": {
            source: kind.value
            for source, kind in mapping.ARCHIVE_SOURCES.items()
        },
        "datasets": {
            table.dataset: _table(table)
            for table in (mapping.FORECAST, mapping.ARCHIVE)
        },
    }


def documents() -> dict[str, Document]:
    """Return every contract file, keyed by its path in the contract."""
    return {
        "catalog.json": catalog(),
        "models.schema.json": models_schema(),
        "providers/open_meteo.json": open_meteo(),
        "conformance/open_meteo.json": conformance.open_meteo(
            CONTRACT_VERSION
        ),
    }


def render(document: Document) -> str:
    """Serialize a document exactly as it is committed."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def write(directory: Path = CONTRACT_DIR) -> list[Path]:
    """Write every contract file under ``directory``.

    Returns:
        The written paths.
    """
    written: list[Path] = []
    for name, document in documents().items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(document), encoding="utf-8", newline="\n")
        written.append(path)
    return written


def main() -> None:
    """Regenerate ``contract/`` and list the written files."""
    for path in write():
        sys.stdout.write(f"{path.relative_to(CONTRACT_DIR.parent)}\n")


if __name__ == "__main__":
    main()
