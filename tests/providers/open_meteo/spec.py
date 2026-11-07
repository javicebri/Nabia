"""Open-Meteo OpenAPI watcher.

Open-Meteo publishes one OpenAPI file per API in its repository. Only
the parameters and the allowed values Nabia depends on are tracked;
volatile lists such as weather models are ignored to avoid noise.

The snapshot is a local baseline (git-ignored, never published).
Create it, or refresh it after reviewing an upstream change, with::

    uv run python -m tests.providers.open_meteo.spec
"""

import json
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import respx

from nabia import GeoPoint, NabiaSettings
from nabia.providers.open_meteo import ARCHIVE, FORECAST, OpenMeteoClient
from tests.specs import Contract, Snapshot, fetch_yaml, save_snapshot

_RAW = "https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi"

#: Snapshot id -> upstream specification URL.
SOURCES = {
    "forecast": f"{_RAW}/forecast.yml",
    "archive": f"{_RAW}/historical-weather.yml",
}

SNAPSHOT = Path(__file__).parent / "spec_snapshot.json"
REFRESH_COMMAND = "uv run python -m tests.providers.open_meteo.spec"
FIXTURES = Path(__file__).parent / "fixtures"

#: Values the live API accepts (verified by ``tests/live``) that the
#: upstream specification does not list yet. The offline suite fails
#: when a gap is closed upstream, so this list never goes stale.
KNOWN_SPEC_GAPS: Snapshot = {
    "forecast": {
        "daily": ["relative_humidity_2m_mean", "temperature_2m_mean"],
    },
}

#: Enumerated parameters whose allowed values are tracked.
TRACKED_ENUMS = (
    "hourly",
    "daily",
    "temperature_unit",
    "wind_speed_unit",
    "precipitation_unit",
    "timeformat",
)


#: Enums tracked for one specification only. The archive source list is
#: short and stable, and it backs ``ARCHIVE_SOURCES``; the forecast
#: model list (about 50 entries) changes too often to be useful.
EXTRA_ENUMS: dict[str, tuple[str, ...]] = {"archive": ("models",)}


def extract(
    spec: Mapping[str, Any], extra_enums: tuple[str, ...] = ()
) -> Contract:
    """Reduce an Open-Meteo OpenAPI document to the tracked contract."""
    (operation,) = spec["paths"].values()  # one endpoint per file
    parameters = operation["get"]["parameters"]
    contract: Contract = {"parameters": sorted(p["name"] for p in parameters)}
    for parameter in parameters:
        if parameter["name"] not in TRACKED_ENUMS + extra_enums:
            continue
        schema = parameter.get("schema", {})
        values = schema.get("enum") or schema.get("items", {}).get("enum")
        if values:
            contract[parameter["name"]] = sorted(map(str, values))
    return contract


def current() -> Snapshot:
    """Download the current upstream specifications."""
    return {
        sid: extract(fetch_yaml(url), EXTRA_ENUMS.get(sid, ()))
        for sid, url in SOURCES.items()
    }


def used() -> Snapshot:
    """Capture what the client actually sends, using mocked requests.

    Every mapped variable is requested once per dataset/resolution, so
    the result covers all parameter names and values Nabia relies on.
    """
    point = GeoPoint(latitude=0.0, longitude=0.0)
    day = date(2024, 3, 31)
    hourly = _fixture("archive_hourly.json")
    daily = _fixture("archive_daily.json")
    sent: dict[str, list[dict[str, str]]] = {"forecast": [], "archive": []}
    with (
        respx.mock(assert_all_called=False) as router,
        OpenMeteoClient(nabia_settings=NabiaSettings(max_retries=0)) as c,
    ):
        for spec_id, url in (
            ("forecast", "https://api.open-meteo.com/v1/forecast"),
            ("archive", "https://archive-api.open-meteo.com/v1/archive"),
        ):
            route = router.get(url).respond(200, json=hourly)
            if spec_id == "forecast":
                c.forecast_hourly(point, list(FORECAST.hourly))
                route.respond(200, json=daily)
                c.forecast_daily(point, list(FORECAST.daily))
            else:
                c.historical_hourly(
                    point, list(ARCHIVE.hourly), start=day, end=day
                )
                route.respond(200, json=daily)
                c.historical_daily(
                    point, list(ARCHIVE.daily), start=day, end=day
                )
            sent[spec_id] = [
                dict(call.request.url.params) for call in route.calls
            ]
    return {spec_id: _contract(calls) for spec_id, calls in sent.items()}


def _contract(calls: list[dict[str, str]]) -> Contract:
    contract: dict[str, set[str]] = {"parameters": set()}
    for params in calls:
        contract["parameters"].update(params)
        for name in TRACKED_ENUMS:
            if name in params:
                values = params[name].split(",")
                contract.setdefault(name, set()).update(values)
    return {name: sorted(values) for name, values in contract.items()}


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    save_snapshot(SNAPSHOT, current())
    sys.stdout.write(f"Snapshot written to {SNAPSHOT}\n")
