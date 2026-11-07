import json

from nabia.catalog import CONVERSIONS, Unit, convert
from nabia.core.models import DailySeries, HourlySeries
from nabia.providers.registry import all_tables
from tools.contract import CONTRACT_DIR, documents, render, unit_key


def test_committed_contract_is_current() -> None:
    expected = {name: render(doc) for name, doc in documents().items()}
    committed = {
        path.relative_to(CONTRACT_DIR).as_posix(): path.read_text(
            encoding="utf-8"
        )
        for path in CONTRACT_DIR.rglob("*.json")
    }
    stale = sorted(
        name
        for name in expected.keys() | committed.keys()
        if expected.get(name) != committed.get(name)
    )
    assert not stale, (
        f"contract/ is stale ({', '.join(stale)}): "
        "run uv run python -m tools.contract"
    )


def test_every_registered_table_is_exported() -> None:
    exported = {
        (doc["provider"], dataset)
        for name, doc in documents().items()
        if name.startswith("providers/")
        for dataset in doc["datasets"]
    }
    assert exported == {(t.provider, t.dataset) for t in all_tables()}


def test_conformance_series_load_back_unchanged() -> None:
    models: dict[str, type[HourlySeries] | type[DailySeries]] = {
        "hourly": HourlySeries,
        "daily": DailySeries,
    }
    for name, doc in documents().items():
        if not name.startswith("conformance/"):
            continue
        for case in doc["cases"]:
            expected = case["expected"]
            if "series" not in expected:
                assert "error" in expected, case["name"]
                continue
            serialized = json.loads(json.dumps(expected["series"]))
            model = models[serialized["resolution"]]
            loaded = model.model_validate(serialized)
            assert loaded.model_dump(mode="json") == serialized, case["name"]


def test_unit_keys_are_unique_identifiers() -> None:
    keys = [unit_key(unit) for unit in Unit]
    assert len(set(keys)) == len(keys)
    assert all(key.isidentifier() for key in keys)


def test_exported_conversions_reproduce_convert() -> None:
    # Read back from JSON: the serialized numbers must be exact.
    catalog = json.loads(render(documents()["catalog.json"]))
    by_key = {unit_key(unit): unit for unit in Unit}
    assert len(catalog["conversions"]) == len(CONVERSIONS)
    for entry in catalog["conversions"]:
        source, target = by_key[entry["from"]], by_key[entry["to"]]
        for value in (-40.5, 0.0, 1.0, 273.15, 101_325.0, 86_400.0):
            result = (value - entry["offset"]) / entry["divisor"]
            assert (result,) == convert([value], source, target)
