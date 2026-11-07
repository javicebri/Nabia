"""Export Nabia's language-neutral contract to ``contract/``.

Python is the reference implementation. Ports to other languages (the
Dart package) generate their code from these JSON files and replay the
conformance cases, so the vocabulary, the unit conversions, the
provider tables and the expected behaviour are maintained in one
place. Run it after changing the catalog, the output models, a
provider or its conformance cases::

    uv run python -m tools.contract          # regenerate
    uv run python -m tools.contract --check  # fail if stale

Nothing here is provider-specific: providers are discovered from the
registry (see :mod:`tools.providers`). Bump :data:`CONTRACT_VERSION`
when the structure of a file changes in a way existing generators
cannot read.
"""

import argparse
import ast
import importlib
import inspect
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from enum import Enum
from pathlib import Path
from types import ModuleType
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
from tools.providers import default_settings, providers

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


def to_json(value: object) -> Any:
    """Convert a constant to JSON, preserving order.

    Raises:
        TypeError: The type has no defined JSON form (sets have no
            stable order, objects no agreed shape), so nothing is
            exported by accident.
    """
    if isinstance(value, Enum):
        return to_json(value.value)
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(to_json(k)): to_json(item) for k, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_json(item) for item in value]
    raise TypeError(f"no JSON form defined for {type(value).__name__}")


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


def public_assignments(module: ModuleType) -> list[str]:
    """Return the public names assigned at the top level of ``module``.

    Names come from the source, in order, so imported names are left
    out.
    """
    names: list[str] = []
    for node in ast.parse(inspect.getsource(module)).body:
        targets: Sequence[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        names += [
            target.id
            for target in targets
            if isinstance(target, ast.Name) and not target.id.startswith("_")
        ]
    return names


def provider_document(provider: str) -> Document:
    """Return the contract of one provider.

    It holds the default endpoints of its settings and every public
    constant of its ``mapping.py``: tables under ``datasets``, any other
    value under ``constants``. Functions in ``mapping.py`` are logic,
    covered by the conformance cases.

    Raises:
        ValueError: A table declares another provider.
    """
    settings = default_settings(provider)
    endpoints = {
        name: value
        for name in type(settings).model_fields
        if isinstance(value := getattr(settings, name), str)
        and value.startswith("https://")
    }
    mapping = importlib.import_module(f"nabia.providers.{provider}.mapping")
    constants: Document = {}
    datasets: Document = {}
    for name in public_assignments(mapping):
        value = getattr(mapping, name)
        if isinstance(value, VariableTable):
            if value.provider != provider:
                raise ValueError(f"{name} declares provider {value.provider}")
            datasets[value.dataset] = _table(value)
        else:
            constants[name.lower()] = to_json(value)
    return {
        "contract_version": CONTRACT_VERSION,
        "provider": provider,
        "endpoints": endpoints,
        "constants": constants,
        "datasets": datasets,
    }


def documents() -> dict[str, Document]:
    """Return every contract file, keyed by its path in the contract."""
    result = {
        "catalog.json": catalog(),
        "models.schema.json": models_schema(),
    }
    for provider in providers():
        result[f"providers/{provider}.json"] = provider_document(provider)
        result[f"conformance/{provider}.json"] = conformance.document(
            provider, CONTRACT_VERSION
        )
    return result


def render(document: Document) -> str:
    """Serialize a document exactly as it is committed."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _committed(directory: Path) -> dict[str, Path]:
    return {
        path.relative_to(directory).as_posix(): path
        for path in directory.rglob("*.json")
    }


def stale(directory: Path = CONTRACT_DIR) -> list[str]:
    """Return the contract files that are outdated, missing or extra."""
    expected = {name: render(doc) for name, doc in documents().items()}
    committed = {
        name: path.read_text(encoding="utf-8")
        for name, path in _committed(directory).items()
    }
    return sorted(
        name
        for name in expected.keys() | committed.keys()
        if expected.get(name) != committed.get(name)
    )


def write(directory: Path = CONTRACT_DIR) -> list[str]:
    """Regenerate the contract and remove files no longer produced.

    Returns:
        The files written or removed.
    """
    rendered = {name: render(doc) for name, doc in documents().items()}
    changed: list[str] = []
    for name, path in _committed(directory).items():
        if name not in rendered:
            path.unlink()
            changed.append(name)
    for name, text in rendered.items():
        path = directory / name
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        changed.append(name)
    return sorted(changed)


def main(argv: Sequence[str] | None = None) -> int:
    """Regenerate ``contract/``, or check it with ``--check``.

    Returns:
        The process exit status.
    """
    parser = argparse.ArgumentParser(prog="python -m tools.contract")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit with status 1 if contract/ is stale; change nothing",
    )
    args = parser.parse_args(argv)
    if args.check:
        outdated = stale()
        if outdated:
            sys.stderr.write(
                f"contract/ is stale: {', '.join(outdated)}\n"
                "Run: uv run python -m tools.contract\n"
            )
            return 1
        return 0
    for name in write():
        sys.stdout.write(f"contract/{name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
