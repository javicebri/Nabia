"""Golden conformance cases: same call and response, same result.

Each case describes a client call in neutral terms, the HTTP response
the provider returns and what Nabia does with it: the request it sends
(or that it sends none) and the series or error it produces. The
Python client is run against a mocked transport to record them, so
the cases always state what the reference implementation does. Ports
replay them in their own test-suite (see ``contract/README.md``).
"""

import copy
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import respx

from nabia.core.config import NabiaSettings
from nabia.core.errors import (
    NabiaError,
    NoDataError,
    ProviderContractError,
    ProviderHTTPError,
    UnitMismatchError,
    UnsupportedVariableError,
)
from nabia.core.models import TimeSeries

#: Root of the repository.
ROOT = Path(__file__).resolve().parent.parent

#: A JSON object.
Json = dict[str, Any]

#: Error kinds, most specific first. ``ValueError`` covers argument
#: validation (pydantic's ``ValidationError`` derives from it).
ERROR_KINDS: tuple[tuple[type[Exception], str], ...] = (
    (UnitMismatchError, "unit_mismatch"),
    (NoDataError, "no_data"),
    (ProviderContractError, "provider_contract"),
    (ProviderHTTPError, "provider_http"),
    (UnsupportedVariableError, "unsupported_variable"),
    (ValueError, "invalid_argument"),
)


@dataclass(frozen=True)
class Case:
    """One conformance case.

    Attributes:
        name: Unique identifier.
        description: What the case checks.
        operation: Client method (e.g. ``"historical_daily"``).
        variables: Canonical variable names requested.
        options: Keyword arguments as JSON values.
        location: Requested point.
        fixture: Response body, from the provider's test fixtures.
        edit: Change applied to a copy of the fixture body.
        body: Response body when there is no fixture.
        status: HTTP status of the response.
        message_contains: Text the error message must include.
    """

    name: str
    description: str
    operation: str
    variables: Sequence[str]
    options: Mapping[str, Any] = field(default_factory=dict)
    location: Mapping[str, float] = field(
        default_factory=lambda: {"latitude": 40.42, "longitude": -3.7}
    )
    fixture: str | None = None
    edit: Callable[[Json], None] | None = None
    body: Json | None = None
    status: int = 200
    message_contains: str | None = None


def error_kind(exc: Exception) -> str:
    """Return the neutral kind of ``exc``.

    Raises:
        Exception: ``exc`` itself when it is not an expected outcome.
    """
    for error_type, kind in ERROR_KINDS:
        if isinstance(exc, error_type):
            return kind
    raise exc


def _response_body(case: Case, fixtures: Path) -> Json | None:
    if case.fixture is None:
        return case.body
    body: Json = json.loads(
        (fixtures / case.fixture).read_text(encoding="utf-8")
    )
    if case.edit is not None:
        body = copy.deepcopy(body)
        case.edit(body)
    return body


def _request(router: respx.MockRouter) -> Json | None:
    if not router.calls:
        return None
    if len(router.calls) > 1:
        raise RuntimeError("a conformance case must send one request")
    url = router.calls.last.request.url
    items = url.params.multi_items()
    params = dict(items)
    if len(params) != len(items):
        raise RuntimeError(f"repeated query parameter in {url}")
    return {"url": str(url.copy_with(query=None)), "params": params}


def record(
    case: Case,
    client: Any,
    fixtures: Path,
) -> Json:
    """Run ``case`` against ``client`` and describe the outcome.

    Args:
        case: Case to run.
        client: Provider client; every request is mocked.
        fixtures: Directory holding the provider's fixtures.
    """
    body = _response_body(case, fixtures)
    with respx.mock(assert_all_mocked=True) as router:
        if body is not None:
            router.get(url__regex=".*").respond(case.status, json=body)
        expected: Json
        try:
            series = getattr(client, case.operation)(
                dict(case.location), list(case.variables), **case.options
            )
        except NabiaError as exc:
            expected = {"error": error_kind(exc)}
            if isinstance(exc, ProviderHTTPError):
                expected["status_code"] = exc.status_code
            if case.message_contains is not None:
                if case.message_contains not in str(exc):
                    raise RuntimeError(
                        f"{case.name}: {case.message_contains!r} not in {exc}"
                    ) from exc
                expected["message_contains"] = case.message_contains
        except ValueError as exc:
            expected = {"error": error_kind(exc)}
        else:
            if not isinstance(series, TimeSeries):
                raise TypeError(f"{case.name}: unexpected {series!r}")
            expected = {"series": series.model_dump(mode="json")}
        request = _request(router)
    return {
        "name": case.name,
        "description": case.description,
        "call": {
            "operation": case.operation,
            "location": dict(case.location),
            "variables": list(case.variables),
            "options": dict(case.options),
        },
        "response": (
            None if request is None else {"status": case.status, "body": body}
        ),
        "request": request,
        "expected": expected,
    }


# -- Open-Meteo ------------------------------------------------------

_DAY = date(2024, 3, 31).isoformat()
_ARCHIVE_DAY = {"start": _DAY, "end": _DAY}
_SOUTH_SLOPE = {"tilt": 30.0, "aspect": 180.0}


def _set(block: str, name: str, value: Any) -> Callable[[Json], None]:
    def edit(body: Json) -> None:
        body[block][name] = value

    return edit


def _rename_rain_sum(body: Json) -> None:
    body["daily"]["rain_total"] = body["daily"].pop("rain_sum")


def _drop_daily(body: Json) -> None:
    del body["daily"]


def _open_meteo_cases() -> list[Case]:
    from nabia.providers.open_meteo import ARCHIVE, FORECAST

    forecast_hourly = [v.value for v in FORECAST.hourly]
    forecast_daily = [v.value for v in FORECAST.daily]
    archive_hourly = [v.value for v in ARCHIVE.hourly]
    archive_daily = [v.value for v in ARCHIVE.daily]
    cases = [
        # -- successful calls -----------------------------------------
        Case(
            "historical_daily",
            "Daily archive request; sunshine converted from s to h.",
            "historical_daily",
            ["precipitation", "sunshine_duration"],
            {"start": "2024-03-30", "end": _DAY},
            fixture="archive_daily.json",
        ),
        Case(
            "historical_hourly_dst",
            "Unix timestamps expressed in the response zone across the"
            " 2024-03-31 daylight saving change (offset +01:00 -> +02:00).",
            "historical_hourly",
            ["air_temperature"],
            _ARCHIVE_DAY,
            fixture="archive_hourly.json",
        ),
        Case(
            "forecast_hourly_options",
            "Duplicated variables are sent once; forecast options are"
            " passed through. Timestamps follow the zone the response"
            " reports.",
            "forecast_hourly",
            ["air_temperature", "air_temperature"],
            {"days": 3, "past_days": 1, "timezone": "UTC"},
            fixture="archive_hourly.json",
        ),
        Case(
            "forecast_hourly_all_variables",
            "Every hourly forecast variable, tilted irradiance on a"
            " south-facing slope.",
            "forecast_hourly",
            forecast_hourly,
            {"surface": _SOUTH_SLOPE},
            fixture="forecast_hourly.json",
        ),
        Case(
            "forecast_daily_all_variables",
            "Every daily forecast variable.",
            "forecast_daily",
            forecast_daily,
            fixture="forecast_daily.json",
        ),
        Case(
            "historical_hourly_all_variables",
            "Every hourly archive variable, tilted irradiance on a"
            " south-facing slope.",
            "historical_hourly",
            archive_hourly,
            {**_ARCHIVE_DAY, "surface": _SOUTH_SLOPE},
            fixture="archive_hourly.json",
        ),
        Case(
            "historical_daily_all_variables",
            "Every daily archive variable.",
            "historical_daily",
            archive_daily,
            _ARCHIVE_DAY,
            fixture="archive_daily.json",
        ),
        Case(
            "historical_daily_explicit_best_match",
            "The default model hides the source: nothing is claimed.",
            "historical_daily",
            ["rain"],
            {**_ARCHIVE_DAY, "model": "best_match"},
            fixture="archive_daily.json",
        ),
        Case(
            "forecast_daily_elevation",
            "Elevation is sent; the forecast is always forecast kind.",
            "forecast_daily",
            ["rain"],
            {"elevation": 1667},
            fixture="archive_daily.json",
        ),
        Case(
            "historical_daily_partial_values",
            "Partially missing values are kept as null.",
            "historical_daily",
            ["precipitation"],
            _ARCHIVE_DAY,
            fixture="archive_daily.json",
            edit=_set("daily", "precipitation_sum", [None, 2.5]),
        ),
        Case(
            "forecast_hourly_surface_ignored",
            "A surface without a tilted variable is neither sent nor"
            " recorded.",
            "forecast_hourly",
            ["air_temperature"],
            {"surface": _SOUTH_SLOPE},
            fixture="forecast_hourly.json",
        ),
    ]
    for model in ("era5", "ecmwf_ifs", "brand_new_model"):
        cases.append(
            Case(
                f"historical_daily_model_{model}",
                "An explicit archive model is sent and recorded; its"
                " kind comes from the source table (unknown: null).",
                "historical_daily",
                ["rain"],
                {**_ARCHIVE_DAY, "model": model},
                fixture="archive_daily.json",
            )
        )
    for aspect in (0.0, 90.0, 270.0):
        cases.append(
            Case(
                f"forecast_hourly_aspect_{aspect:g}",
                "Compass aspect translated to Open-Meteo's south-based"
                " azimuth.",
                "forecast_hourly",
                ["shortwave_radiation_tilted"],
                {"surface": {"tilt": 30.0, "aspect": aspect}},
                fixture="forecast_hourly.json",
            )
        )
    # -- errors after a response --------------------------------------
    cases += [
        Case(
            "unit_drift",
            "A unit reported upstream that differs from the table.",
            "historical_hourly",
            ["air_temperature"],
            _ARCHIVE_DAY,
            fixture="archive_hourly.json",
            edit=_set("hourly_units", "temperature_2m", "°F"),
            message_contains="temperature_2m",
        ),
        Case(
            "renamed_column",
            "A requested column missing from the response.",
            "historical_daily",
            ["rain"],
            _ARCHIVE_DAY,
            fixture="archive_daily.json",
            edit=_rename_rain_sum,
            message_contains="rain_sum",
        ),
        Case(
            "missing_block",
            "The requested resolution block is absent.",
            "historical_daily",
            ["rain"],
            _ARCHIVE_DAY,
            fixture="archive_daily.json",
            edit=_drop_daily,
            message_contains="daily",
        ),
        Case(
            "empty_column",
            "A requested variable with no value at all names the source.",
            "historical_daily",
            ["precipitation"],
            {**_ARCHIVE_DAY, "model": "era5_land"},
            fixture="archive_daily.json",
            edit=_set("daily", "precipitation_sum", [None, None]),
            message_contains="era5_land",
        ),
        Case(
            "api_error_reason",
            "The reason of an HTTP 400 error payload is surfaced.",
            "historical_daily",
            ["rain"],
            _ARCHIVE_DAY,
            body={"error": True, "reason": "Parameter 'end_date' is out"},
            status=400,
            message_contains="end_date",
        ),
    ]
    # -- errors before any request ------------------------------------
    unsupported: list[tuple[str, Sequence[str], Mapping[str, Any]]] = [
        ("forecast_hourly", ["air_temperature_max"], {}),
        ("historical_hourly", ["precipitation_probability"], _ARCHIVE_DAY),
        ("forecast_daily", ["shortwave_radiation_tilted"], {}),
    ]
    for operation, variables, options in unsupported:
        cases.append(
            Case(
                f"unsupported_{operation}_{variables[0]}",
                "Variable not offered at this resolution or dataset.",
                operation,
                variables,
                options,
            )
        )
    tilted = ["shortwave_radiation_tilted"]
    rain = ["rain"]
    invalid: list[tuple[str, str, Sequence[str], Mapping[str, Any]]] = [
        ("tilted_without_surface", "forecast_hourly", tilted, {}),
        ("no_variables", "forecast_daily", [], {}),
        ("days_0", "forecast_daily", rain, {"days": 0}),
        ("days_17", "forecast_daily", rain, {"days": 17}),
        ("past_days_-1", "forecast_daily", rain, {"past_days": -1}),
        ("past_days_93", "forecast_daily", rain, {"past_days": 93}),
        ("empty_timezone", "forecast_daily", rain, {"timezone": ""}),
        ("model_list", "forecast_daily", rain, {"model": "era5,ecmwf_ifs"}),
        ("model_uppercase", "forecast_daily", rain, {"model": "ERA5"}),
        ("elevation_-501", "forecast_daily", rain, {"elevation": -501}),
        ("elevation_9001", "forecast_daily", rain, {"elevation": 9001}),
        (
            "tilt_91",
            "forecast_hourly",
            tilted,
            {"surface": {"tilt": 91.0, "aspect": 0.0}},
        ),
        (
            "aspect_360",
            "forecast_hourly",
            tilted,
            {"surface": {"tilt": 30.0, "aspect": 360.0}},
        ),
        (
            "end_before_start",
            "historical_daily",
            rain,
            {"start": "2024-02-01", "end": "2024-01-01"},
        ),
        (
            "start_before_1940",
            "historical_daily",
            rain,
            {"start": "1939-12-31", "end": _DAY},
        ),
    ]
    for name, operation, variables, options in invalid:
        cases.append(
            Case(
                f"invalid_{name}",
                "Invalid argument rejected before any request.",
                operation,
                variables,
                options,
            )
        )
    return cases


def open_meteo(contract_version: int) -> Json:
    """Return the Open-Meteo conformance cases."""
    from nabia.providers.open_meteo import (
        OpenMeteoClient,
        OpenMeteoSettings,
    )

    # model_construct() takes the defaults without reading the
    # environment or .env: the cases must not depend on the machine.
    with OpenMeteoClient(
        OpenMeteoSettings.model_construct(),
        nabia_settings=NabiaSettings.model_construct(max_retries=0),
    ) as client:
        fixtures = ROOT / "tests" / "providers" / "open_meteo" / "fixtures"
        cases = [
            record(case, client, fixtures) for case in _open_meteo_cases()
        ]
    names = [case["name"] for case in cases]
    if len(set(names)) != len(names):
        raise RuntimeError("duplicate conformance case names")
    return {
        "contract_version": contract_version,
        "provider": "open_meteo",
        "cases": cases,
    }
