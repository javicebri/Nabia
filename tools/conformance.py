"""Golden conformance cases shared by every implementation.

A case describes a client call in neutral terms, the provider's answer
(an HTTP response or a network failure) and the outcome the call must
have: a series or an error kind. Recording runs the Python client
against a mocked transport, checks that the declared outcome happened
and stores the details (the request sent, the serialized series). Every
implementation replays the committed cases: Python in
``tests/test_conformance.py``, ports in their own test-suite (see
``contract/README.md``).

Each provider defines ``CASES`` in ``tests/providers/<name>/
conformance.py``, next to the fixtures they use.
"""

import copy
import importlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import respx

from nabia.core.errors import (
    AuthenticationError,
    NoDataError,
    ProviderConnectionError,
    ProviderContractError,
    ProviderHTTPError,
    ProviderServerError,
    RateLimitError,
    UnitMismatchError,
    UnsupportedVariableError,
)
from nabia.core.models import TimeSeries
from nabia.providers.base import BaseClient
from tools.providers import provider_client

#: A JSON object.
Json = dict[str, Any]

#: Outcome of a call that returns data.
SERIES = "series"

#: The only network failure cases can simulate.
CONNECTION_FAILURE = "connection"

#: Error kinds, most specific first. ``ValueError`` covers argument
#: validation (pydantic's ``ValidationError`` derives from it).
ERROR_KINDS: tuple[tuple[type[Exception], str], ...] = (
    (UnitMismatchError, "unit_mismatch"),
    (NoDataError, "no_data"),
    (ProviderContractError, "provider_contract"),
    (AuthenticationError, "authentication"),
    (RateLimitError, "rate_limit"),
    (ProviderServerError, "provider_server"),
    (ProviderHTTPError, "provider_http"),
    (ProviderConnectionError, "provider_connection"),
    (UnsupportedVariableError, "unsupported_variable"),
    (ValueError, "invalid_argument"),
)

#: Every outcome a case can declare.
OUTCOMES = frozenset({SERIES, *(kind for _, kind in ERROR_KINDS)})


class ConformanceError(Exception):
    """A case is ill-defined or did not have its declared outcome."""


@dataclass(frozen=True, kw_only=True)
class Case:
    """Definition of one conformance case.

    Attributes:
        name: Unique identifier within the provider.
        description: What the case checks.
        operation: Client method (e.g. ``"historical_daily"``).
        location: Requested point (``latitude``, ``longitude``).
        variables: Canonical variable names requested.
        outcome: ``"series"`` or the expected error kind.
        options: Keyword arguments, as JSON values.
        fixture: File in the provider's ``fixtures/`` used as body.
        edit: Change applied to a copy of the fixture body.
        body: Response body when there is no fixture.
        status: HTTP status of the response.
        headers: HTTP headers of the response.
        failure: Network failure instead of a response
            (``"connection"``).
        message_contains: Text the error message must include.
    """

    name: str
    description: str
    operation: str
    location: Mapping[str, float]
    variables: Sequence[str]
    outcome: str
    options: Mapping[str, Any] = field(default_factory=dict)
    fixture: str | None = None
    edit: Callable[[Json], None] | None = None
    body: Json | None = None
    status: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    failure: str | None = None
    message_contains: str | None = None

    def __post_init__(self) -> None:
        problems = []
        if self.outcome not in OUTCOMES:
            problems.append(f"unknown outcome {self.outcome!r}")
        if self.outcome == SERIES and self.message_contains is not None:
            problems.append("message_contains needs an error outcome")
        if self.fixture is not None and self.body is not None:
            problems.append("give a fixture or a body, not both")
        if self.edit is not None and self.fixture is None:
            problems.append("edit needs a fixture")
        if self.failure not in (None, CONNECTION_FAILURE):
            problems.append(f"unknown failure {self.failure!r}")
        if self.failure is not None and self.answers_with_http:
            problems.append("a failure has no HTTP response")
        if problems:
            raise ConformanceError(f"{self.name}: {'; '.join(problems)}")

    @property
    def answers_with_http(self) -> bool:
        """Whether the case defines an HTTP response."""
        return self.fixture is not None or self.body is not None

    def call(self) -> Json:
        """Return the call in neutral, JSON form."""
        return {
            "operation": self.operation,
            "location": dict(self.location),
            "variables": list(self.variables),
            "options": dict(self.options),
        }

    def response(self, fixtures: Path) -> Json | None:
        """Return the provider's answer in JSON form, if any."""
        if self.failure is not None:
            return {"failure": self.failure}
        if not self.answers_with_http:
            return None
        body = self.body
        if self.fixture is not None:
            path = fixtures / self.fixture
            body = json.loads(path.read_text(encoding="utf-8"))
            if self.edit is not None:
                body = copy.deepcopy(body)
                self.edit(body)
        return {
            "status": self.status,
            "headers": dict(self.headers),
            "body": body,
        }


def mock_response(router: respx.MockRouter, response: Json) -> None:
    """Answer every GET with ``response`` (committed JSON form)."""
    route = router.get(url__regex=".*")
    if response.get("failure") == CONNECTION_FAILURE:
        route.side_effect = httpx.ConnectError("simulated failure")
    else:
        route.respond(
            response["status"],
            headers=response["headers"],
            json=response["body"],
        )


def error_kind(exc: Exception) -> str | None:
    """Return the neutral kind of ``exc``, or ``None`` if unexpected."""
    for error_type, kind in ERROR_KINDS:
        if isinstance(exc, error_type):
            return kind
    return None


def invoke(client: BaseClient, call: Json) -> Json:
    """Run a neutral call and describe what happened.

    Returns:
        ``{"series": <serialized series>}`` or ``{"error": <kind>,
        "message": <text>}``, plus ``status_code`` for HTTP errors and
        ``retry_after`` when the provider asked to wait.

    Raises:
        Exception: Any error that is not an expected outcome.
    """
    method = getattr(client, call["operation"])
    try:
        series = method(call["location"], call["variables"], **call["options"])
    except Exception as exc:
        kind = error_kind(exc)
        if kind is None:
            raise
        result: Json = {"error": kind, "message": str(exc)}
        if isinstance(exc, ProviderHTTPError):
            result["status_code"] = exc.status_code
        if isinstance(exc, RateLimitError) and exc.retry_after is not None:
            result["retry_after"] = exc.retry_after
        return result
    if not isinstance(series, TimeSeries):
        raise TypeError(f"{call['operation']} returned {type(series)}")
    return {SERIES: series.model_dump(mode="json")}


def capture_request(router: respx.MockRouter) -> Json | None:
    """Return the only request sent (URL and query), or ``None``.

    Raises:
        ConformanceError: Several requests were sent, or a query
            parameter was repeated.
    """
    if not router.calls:
        return None
    if len(router.calls) > 1:
        raise ConformanceError("a call must send at most one request")
    url = router.calls.last.request.url
    items = url.params.multi_items()
    params = dict(items)
    if len(params) != len(items):
        raise ConformanceError(f"repeated query parameter in {url}")
    return {"url": str(url.copy_with(query=None)), "params": params}


def record(case: Case, client: BaseClient, fixtures: Path) -> Json:
    """Run ``case`` and return its committed form.

    Raises:
        ConformanceError: The outcome differs from the declared one, or
            the case is inconsistent (an answer that is never
            requested, an expected text missing from the message).
    """
    response = case.response(fixtures)
    call = case.call()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        if response is not None:
            mock_response(mock, response)
        result = invoke(client, call)
        request = capture_request(mock)
    actual = result.get("error", SERIES)
    if actual != case.outcome:
        raise ConformanceError(
            f"{case.name}: declared {case.outcome!r}, got {actual!r} "
            f"{result.get('message', '')}"
        )
    if response is not None and request is None:
        raise ConformanceError(f"{case.name}: answer is never requested")
    expected = {key: val for key, val in result.items() if key != "message"}
    if case.message_contains is not None:
        if case.message_contains not in result["message"]:
            raise ConformanceError(
                f"{case.name}: {case.message_contains!r} not in "
                f"{result['message']!r}"
            )
        expected["message_contains"] = case.message_contains
    return {
        "name": case.name,
        "description": case.description,
        "call": call,
        "response": response,
        "request": request,
        "expected": expected,
    }


def document(provider: str, contract_version: int) -> Json:
    """Record every case of ``provider``.

    Raises:
        ConformanceError: Duplicate case names or a failing case.
    """
    module = importlib.import_module(f"tests.providers.{provider}.conformance")
    if module.__file__ is None:
        raise ConformanceError(f"{module.__name__} has no source file")
    cases: Sequence[Case] = module.CASES
    names = [case.name for case in cases]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ConformanceError(f"duplicate case names: {duplicates}")
    fixtures = Path(module.__file__).parent / "fixtures"
    with provider_client(provider) as client:
        recorded = [record(case, client, fixtures) for case in cases]
    return {
        "contract_version": contract_version,
        "provider": provider,
        "cases": recorded,
    }
