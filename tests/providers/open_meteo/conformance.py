"""Open-Meteo conformance cases, shared with every implementation.

Recorded into ``contract/conformance/open_meteo.json`` by
``uv run python -m tools.contract`` and replayed by
``tests/test_conformance.py``. Responses come from ``fixtures/``:
trimmed real responses for Madrid, the archive ones around the
2024-03-31 daylight saving change.
"""

from collections.abc import Callable
from typing import Any

from nabia.providers.open_meteo import ARCHIVE, FORECAST
from tools.conformance import SERIES, Case, Json

MADRID = {"latitude": 40.42, "longitude": -3.7}
DAY = "2024-03-31"
ONE_DAY = {"start": DAY, "end": DAY}
SOUTH_SLOPE = {"tilt": 30.0, "aspect": 180.0}
TILTED = ["shortwave_radiation_tilted"]
RAIN = ["rain"]


def _set(block: str, name: str, value: Any) -> Callable[[Json], None]:
    def edit(body: Json) -> None:
        body[block][name] = value

    return edit


def _rename_rain_sum(body: Json) -> None:
    body["daily"]["rain_total"] = body["daily"].pop("rain_sum")


def _drop(name: str) -> Callable[[Json], None]:
    def edit(body: Json) -> None:
        del body[name]

    return edit


def _repeat_first_timestamp(body: Json) -> None:
    times = body["hourly"]["time"]
    times[1] = times[0]


def _unknown_zone(body: Json) -> None:
    body["timezone"] = "Unknown/Zone"


def _top(name: str, value: Any) -> Callable[[Json], None]:
    def edit(body: Json) -> None:
        body[name] = value

    return edit


def _float_timestamps(body: Json) -> None:
    body["hourly"]["time"] = [float(t) for t in body["hourly"]["time"]]


def _malformed(
    name: str,
    description: str,
    edit: Callable[[Json], None],
    *,
    hourly: bool = False,
) -> Case:
    # Upstream format changes must fail loudly, never be coerced.
    return Case(
        name=name,
        description=description,
        operation="historical_hourly" if hourly else "historical_daily",
        location=MADRID,
        variables=["air_temperature"] if hourly else ["precipitation"],
        outcome="provider_contract",
        options=ONE_DAY,
        fixture="archive_hourly.json" if hourly else "archive_daily.json",
        edit=edit,
    )


_HTML = "<html><body><h1>502 Bad Gateway</h1></body></html>"


def _series(
    name: str,
    description: str,
    operation: str,
    variables: list[str],
    fixture: str,
    **kwargs: Any,
) -> Case:
    return Case(
        name=name,
        description=description,
        operation=operation,
        location=MADRID,
        variables=variables,
        outcome=SERIES,
        fixture=fixture,
        **kwargs,
    )


def _rejected(
    name: str,
    description: str,
    operation: str,
    variables: list[str],
    outcome: str,
    **kwargs: Any,
) -> Case:
    # No response: the call must fail before sending any request.
    return Case(
        name=name,
        description=description,
        operation=operation,
        location=MADRID,
        variables=variables,
        outcome=outcome,
        **kwargs,
    )


_SUCCESS = [
    _series(
        "historical_daily",
        "Daily archive request; sunshine converted from s to h; the"
        " default model claims no source.",
        "historical_daily",
        ["precipitation", "sunshine_duration"],
        "archive_daily.json",
        options={"start": "2024-03-30", "end": DAY},
    ),
    _series(
        "historical_hourly_dst",
        "Unix timestamps expressed in the response zone across the"
        " daylight saving change (offset +01:00 -> +02:00).",
        "historical_hourly",
        ["air_temperature"],
        "archive_hourly.json",
        options=ONE_DAY,
    ),
    _series(
        "forecast_hourly_options",
        "Duplicated variables are sent once; forecast options are passed"
        " through. Timestamps follow the zone the response reports.",
        "forecast_hourly",
        ["air_temperature", "air_temperature"],
        "archive_hourly.json",
        options={"days": 3, "past_days": 1, "timezone": "UTC"},
    ),
    _series(
        "forecast_hourly_all_variables",
        "Every hourly forecast variable; tilted irradiance on a"
        " south-facing slope.",
        "forecast_hourly",
        [variable.value for variable in FORECAST.hourly],
        "forecast_hourly.json",
        options={"surface": SOUTH_SLOPE},
    ),
    _series(
        "forecast_daily_all_variables",
        "Every daily forecast variable.",
        "forecast_daily",
        [variable.value for variable in FORECAST.daily],
        "forecast_daily.json",
    ),
    _series(
        "historical_hourly_all_variables",
        "Every hourly archive variable; tilted irradiance on a"
        " south-facing slope.",
        "historical_hourly",
        [variable.value for variable in ARCHIVE.hourly],
        "archive_hourly.json",
        options={**ONE_DAY, "surface": SOUTH_SLOPE},
    ),
    _series(
        "historical_daily_all_variables",
        "Every daily archive variable.",
        "historical_daily",
        [variable.value for variable in ARCHIVE.daily],
        "archive_daily.json",
        options=ONE_DAY,
    ),
    _series(
        "historical_daily_explicit_best_match",
        "The default model is sent but hides the source: nothing is claimed.",
        "historical_daily",
        RAIN,
        "archive_daily.json",
        options={**ONE_DAY, "model": "best_match"},
    ),
    _series(
        "forecast_daily_elevation",
        "Elevation is sent; a forecast is always of forecast kind.",
        "forecast_daily",
        RAIN,
        "archive_daily.json",
        options={"elevation": 1667},
    ),
    _series(
        "historical_daily_partial_values",
        "Partially missing values are kept as null.",
        "historical_daily",
        ["precipitation"],
        "archive_daily.json",
        options=ONE_DAY,
        edit=_set("daily", "precipitation_sum", [None, 2.5]),
    ),
    _series(
        "historical_hourly_unknown_zone",
        "A zone name the time zone database lacks falls back to the"
        " fixed UTC offset the response reports (no DST change).",
        "historical_hourly",
        ["air_temperature"],
        "archive_hourly.json",
        options=ONE_DAY,
        edit=_unknown_zone,
    ),
    _series(
        "forecast_hourly_surface_ignored",
        "A surface without a tilted variable is neither sent nor recorded.",
        "forecast_hourly",
        ["air_temperature"],
        "forecast_hourly.json",
        options={"surface": SOUTH_SLOPE},
    ),
    *(
        _series(
            f"historical_daily_model_{model}",
            "An explicit archive model is sent and recorded; its kind"
            " comes from the source table (unknown: null).",
            "historical_daily",
            RAIN,
            "archive_daily.json",
            options={**ONE_DAY, "model": model},
        )
        for model in ("era5", "ecmwf_ifs", "brand_new_model")
    ),
    *(
        _series(
            f"forecast_hourly_aspect_{aspect:g}",
            "Compass aspect translated to Open-Meteo's south-based azimuth.",
            "forecast_hourly",
            TILTED,
            "forecast_hourly.json",
            options={"surface": {"tilt": 30.0, "aspect": aspect}},
        )
        for aspect in (0.0, 90.0, 270.0)
    ),
]

_FAILED_RESPONSE = [
    Case(
        name="unit_drift",
        description="A unit reported upstream that differs from the table.",
        operation="historical_hourly",
        location=MADRID,
        variables=["air_temperature"],
        outcome="unit_mismatch",
        options=ONE_DAY,
        fixture="archive_hourly.json",
        edit=_set("hourly_units", "temperature_2m", "°F"),
        message_contains="temperature_2m",
    ),
    Case(
        name="renamed_column",
        description="A requested column missing from the response.",
        operation="historical_daily",
        location=MADRID,
        variables=RAIN,
        outcome="provider_contract",
        options=ONE_DAY,
        fixture="archive_daily.json",
        edit=_rename_rain_sum,
        message_contains="rain_sum",
    ),
    Case(
        name="missing_block",
        description="The requested resolution block is absent.",
        operation="historical_daily",
        location=MADRID,
        variables=RAIN,
        outcome="provider_contract",
        options=ONE_DAY,
        fixture="archive_daily.json",
        edit=_drop("daily"),
        message_contains="daily",
    ),
    Case(
        name="missing_hourly_block",
        description="The requested resolution block is absent.",
        operation="historical_hourly",
        location=MADRID,
        variables=["air_temperature"],
        outcome="provider_contract",
        options=ONE_DAY,
        fixture="archive_hourly.json",
        edit=_drop("hourly"),
        message_contains="hourly",
    ),
    Case(
        name="time_not_increasing",
        description="A repeated timestamp cannot form a valid series.",
        operation="historical_hourly",
        location=MADRID,
        variables=["air_temperature"],
        outcome="provider_contract",
        options=ONE_DAY,
        fixture="archive_hourly.json",
        edit=_repeat_first_timestamp,
        message_contains="increasing",
    ),
    Case(
        name="misaligned_column",
        description="A column shorter than the time axis cannot form a"
        " valid series.",
        operation="historical_daily",
        location=MADRID,
        variables=["precipitation"],
        outcome="provider_contract",
        options=ONE_DAY,
        fixture="archive_daily.json",
        edit=_set("daily", "precipitation_sum", [1.0]),
        message_contains="aligned",
    ),
    Case(
        name="empty_column",
        description="A requested variable with no value at all; the"
        " message names the source.",
        operation="historical_daily",
        location=MADRID,
        variables=["precipitation"],
        outcome="no_data",
        options={**ONE_DAY, "model": "era5_land"},
        fixture="archive_daily.json",
        edit=_set("daily", "precipitation_sum", [None, None]),
        message_contains="era5_land",
    ),
    Case(
        name="api_error_reason",
        description="The reason of an HTTP 400 error payload is surfaced.",
        operation="historical_daily",
        location=MADRID,
        variables=RAIN,
        outcome="provider_http",
        options=ONE_DAY,
        body={"error": True, "reason": "Parameter 'end_date' is out"},
        status=400,
        message_contains="end_date",
    ),
    Case(
        name="api_error_without_reason",
        description="An HTTP 400 whose payload has an unknown shape still"
        " raises an HTTP error.",
        operation="historical_daily",
        location=MADRID,
        variables=RAIN,
        outcome="provider_http",
        options=ONE_DAY,
        body={"detail": "unexpected payload"},
        status=400,
    ),
    Case(
        name="rate_limited",
        description="HTTP 429; the requested wait (Retry-After) is kept.",
        operation="forecast_daily",
        location=MADRID,
        variables=RAIN,
        outcome="rate_limit",
        body={"error": True, "reason": "Minutely API request limit"},
        status=429,
        headers={"Retry-After": "60"},
        message_contains="limit",
    ),
    Case(
        name="server_error",
        description="HTTP 5xx is the provider's failure.",
        operation="forecast_daily",
        location=MADRID,
        variables=RAIN,
        outcome="provider_server",
        body={"error": True, "reason": "Service unavailable"},
        status=503,
    ),
    Case(
        name="html_instead_of_json",
        description="A 200 answer that is not JSON (e.g. a captive portal"
        " or proxy page) is a contract error.",
        operation="forecast_daily",
        location=MADRID,
        variables=RAIN,
        outcome="provider_contract",
        text=_HTML,
    ),
    Case(
        name="html_error_page",
        description="An HTML 5xx page: no reason can be read, the status"
        " still classifies the error.",
        operation="forecast_daily",
        location=MADRID,
        variables=RAIN,
        outcome="provider_server",
        text=_HTML,
        status=502,
    ),
    _malformed(
        "boolean_in_column",
        "A boolean is not a number (lax parsing would read true as 1.0).",
        _set("daily", "precipitation_sum", [True, 2.0]),
    ),
    _malformed(
        "numeric_string_in_column",
        "A number sent as text is a format change, not a number.",
        _set("daily", "precipitation_sum", ["1.5", 2.0]),
    ),
    _malformed(
        "column_not_a_list",
        "Every column is a list aligned with the time axis.",
        _set("daily", "precipitation_sum", 10.1),
    ),
    _malformed(
        "invalid_date",
        "A daily date that does not exist.",
        _set("daily", "time", ["2024-02-30", "2024-03-31"]),
    ),
    _malformed(
        "time_not_a_list",
        "The time axis is a list.",
        _set("hourly", "time", "1711839600"),
        hourly=True,
    ),
    _malformed(
        "float_timestamps",
        "Unix timestamps are integers; 1711839600.0 is not coerced.",
        _float_timestamps,
        hourly=True,
    ),
    _malformed(
        "float_utc_offset",
        "The UTC offset is an integer number of seconds.",
        _top("utc_offset_seconds", 3600.0),
        hourly=True,
    ),
    _malformed(
        "latitude_as_string",
        "Coordinates are numbers.",
        _top("latitude", "40.386642"),
    ),
    _malformed(
        "elevation_as_string",
        "The elevation is a number or null.",
        _top("elevation", "667"),
    ),
    _malformed(
        "timezone_as_number",
        "The zone name is a string.",
        _top("timezone", 3600),
    ),
    _malformed(
        "missing_timezone",
        "A required top-level field is absent.",
        _drop("timezone"),
    ),
    _malformed(
        "coordinates_out_of_range",
        "Coordinates outside WGS84 cannot form a valid series.",
        _top("latitude", 95.0),
    ),
    Case(
        name="connection_failure",
        description="The provider cannot be reached.",
        operation="forecast_daily",
        location=MADRID,
        variables=RAIN,
        outcome="provider_connection",
        failure="connection",
    ),
]

_UNSUPPORTED = [
    _rejected(
        f"unsupported_{operation}_{variable}",
        "Variable not offered for this dataset and resolution.",
        operation,
        [variable],
        "unsupported_variable",
        options=options,
    )
    for operation, variable, options in (
        ("forecast_hourly", "air_temperature_max", {}),
        ("historical_hourly", "precipitation_probability", ONE_DAY),
        ("forecast_daily", "shortwave_radiation_tilted", {}),
    )
]

_INVALID_ARGUMENTS: list[tuple[str, str, list[str], Json]] = [
    ("tilted_without_surface", "forecast_hourly", TILTED, {}),
    ("no_variables", "forecast_daily", [], {}),
    ("days_0", "forecast_daily", RAIN, {"days": 0}),
    ("days_17", "forecast_daily", RAIN, {"days": 17}),
    ("past_days_-1", "forecast_daily", RAIN, {"past_days": -1}),
    ("past_days_93", "forecast_daily", RAIN, {"past_days": 93}),
    ("empty_timezone", "forecast_daily", RAIN, {"timezone": ""}),
    ("model_list", "forecast_daily", RAIN, {"model": "era5,ecmwf_ifs"}),
    ("model_uppercase", "forecast_daily", RAIN, {"model": "ERA5"}),
    ("model_empty", "forecast_daily", RAIN, {"model": ""}),
    ("model_space", "forecast_daily", RAIN, {"model": "a b"}),
    ("elevation_-501", "forecast_daily", RAIN, {"elevation": -501}),
    ("elevation_9001", "forecast_daily", RAIN, {"elevation": 9001}),
    (
        "tilt_91",
        "forecast_hourly",
        TILTED,
        {"surface": {"tilt": 91.0, "aspect": 0.0}},
    ),
    (
        "aspect_360",
        "forecast_hourly",
        TILTED,
        {"surface": {"tilt": 30.0, "aspect": 360.0}},
    ),
]

_INVALID_RANGES = [
    ("end_before_start", {"start": "2024-02-01", "end": "2024-01-01"}),
    ("start_before_1940", {"start": "1939-12-31", "end": DAY}),
]

#: Every Open-Meteo case, in the order they are committed.
CASES: tuple[Case, ...] = (
    *_SUCCESS,
    *_FAILED_RESPONSE,
    *_UNSUPPORTED,
    *(
        _rejected(
            f"invalid_{name}",
            "Invalid argument rejected before any request.",
            operation,
            variables,
            "invalid_argument",
            options=options,
        )
        for name, operation, variables, options in _INVALID_ARGUMENTS
    ),
    *(
        _rejected(
            f"invalid_{name}",
            "Invalid date range rejected before any request.",
            "historical_daily",
            RAIN,
            "invalid_argument",
            options=options,
            message_contains="start",
        )
        for name, options in _INVALID_RANGES
    ),
)
