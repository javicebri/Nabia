import functools
import json
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from nabia.catalog import CONVERSIONS, Unit, convert
from nabia.core.models import DailySeries, HourlySeries, SourceKind
from nabia.providers.registry import all_tables
from tools.conformance import SERIES, Case, ConformanceError
from tools.contract import (
    documents,
    main,
    render,
    stale,
    to_json,
    unit_key,
    write,
)
from tools.providers import providers

#: Recorded once per session; it runs every conformance case.
contract_documents = functools.cache(documents)


def test_committed_contract_is_current() -> None:
    outdated = stale()
    assert not outdated, (
        f"contract/ is stale ({', '.join(outdated)}): "
        "run uv run python -m tools.contract"
    )


def test_write_then_check(tmp_path: Path) -> None:
    extra = tmp_path / "providers" / "removed.json"
    extra.parent.mkdir()
    extra.write_text("{}", encoding="utf-8")
    written = write(tmp_path)
    assert "providers/removed.json" in written
    assert not extra.exists()
    assert stale(tmp_path) == []
    assert write(tmp_path) == []  # unchanged files are not rewritten


def test_check_reports_stale_contract(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("tools.contract.stale", lambda: ["catalog.json"])
    assert main(["--check"]) == 1
    assert "catalog.json" in capsys.readouterr().err
    monkeypatch.setattr("tools.contract.stale", list)
    assert main(["--check"]) == 0


def test_every_registered_table_is_exported() -> None:
    exported = {
        (doc["provider"], dataset)
        for name, doc in contract_documents().items()
        if name.startswith("providers/")
        for dataset in doc["datasets"]
    }
    assert exported == {(t.provider, t.dataset) for t in all_tables()}


def test_every_provider_has_conformance_cases() -> None:
    docs = contract_documents()
    for provider in providers():
        assert docs[f"conformance/{provider}.json"]["cases"], provider


def test_provider_constants_are_exported() -> None:
    open_meteo = contract_documents()["providers/open_meteo.json"]
    assert open_meteo["endpoints"] == {
        "forecast_url": "https://api.open-meteo.com/v1/forecast",
        "archive_url": "https://archive-api.open-meteo.com/v1/archive",
    }
    assert set(open_meteo["constants"]) == {
        "verified_on",
        "attribution",
        "default_model",
        "archive_sources",
        "unit_params",
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (SourceKind.REANALYSIS, "reanalysis"),
        (date(2026, 11, 7), "2026-11-07"),
        (MappingProxyType({Unit.HOUR: (1, None)}), {"h": [1, None]}),
    ],
)
def test_to_json(value: object, expected: Any) -> None:
    assert to_json(value) == expected


@pytest.mark.parametrize("value", [frozenset({1}), object()])
def test_to_json_rejects_undefined_forms(value: object) -> None:
    with pytest.raises(TypeError):
        to_json(value)


def test_conformance_series_load_back_unchanged() -> None:
    models: dict[str, type[HourlySeries] | type[DailySeries]] = {
        "hourly": HourlySeries,
        "daily": DailySeries,
    }
    for name, doc in contract_documents().items():
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


@pytest.mark.parametrize(
    ("kwargs", "problem"),
    [
        ({"outcome": "boom"}, "unknown outcome"),
        ({"message_contains": "x"}, "needs an error outcome"),
        ({"fixture": "a.json", "body": {}}, "not both"),
        ({"edit": lambda body: None}, "edit needs a fixture"),
        ({"failure": "dns"}, "unknown failure"),
        ({"failure": "connection", "body": {}}, "has no HTTP response"),
    ],
)
def test_ill_defined_case_is_rejected(
    kwargs: dict[str, Any], problem: str
) -> None:
    fields: dict[str, Any] = {
        "name": "case",
        "description": "",
        "operation": "forecast_daily",
        "location": {"latitude": 0.0, "longitude": 0.0},
        "variables": ["rain"],
        "outcome": SERIES,
        **kwargs,
    }
    with pytest.raises(ConformanceError, match=problem):
        Case(**fields)


def test_unit_keys_are_unique_identifiers() -> None:
    keys = [unit_key(unit) for unit in Unit]
    assert len(set(keys)) == len(keys)
    assert all(key.isidentifier() for key in keys)


def test_exported_conversions_reproduce_convert() -> None:
    # Read back from JSON: the serialized numbers must be exact.
    catalog = json.loads(render(contract_documents()["catalog.json"]))
    by_key = {unit_key(unit): unit for unit in Unit}
    assert len(catalog["conversions"]) == len(CONVERSIONS)
    for entry in catalog["conversions"]:
        source, target = by_key[entry["from"]], by_key[entry["to"]]
        for value in (-40.5, 0.0, 1.0, 273.15, 101_325.0, 86_400.0):
            result = (value - entry["offset"]) / entry["divisor"]
            assert (result,) == convert([value], source, target)
