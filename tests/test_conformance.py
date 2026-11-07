"""Replay the committed conformance cases against the Python client.

This follows the procedure every port implements (see
``contract/README.md``): mock the response, make the call, then check
the request sent and the series or error returned against the
committed expectations.
"""

import json
from typing import Any

import pytest
import respx

from tools.conformance import capture_request, invoke, mock_response
from tools.contract import CONTRACT_DIR
from tools.providers import provider_client


def _cases() -> list[Any]:
    params = []
    for path in sorted((CONTRACT_DIR / "conformance").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        provider = document["provider"]
        params += [
            pytest.param(provider, case, id=f"{provider}:{case['name']}")
            for case in document["cases"]
        ]
    return params


def same_param(expected: str, actual: str) -> bool:
    """Compare query values; numbers by value ("30" equals "30.0")."""
    if expected == actual:
        return True
    try:
        return float(expected) == float(actual)
    except ValueError:
        return False


@pytest.mark.parametrize(
    ("expected", "actual", "same"),
    [
        ("30.0", "30", True),
        ("-3.7", "-3.70", True),
        ("ms", "ms", True),
        ("30.0", "30.5", False),
        ("ms", "kmh", False),
    ],
)
def test_same_param(expected: str, actual: str, same: bool) -> None:
    assert same_param(expected, actual) is same


@pytest.mark.parametrize(("provider", "case"), _cases())
def test_case(provider: str, case: dict[str, Any]) -> None:
    response = case["response"]
    with (
        provider_client(provider) as client,
        respx.mock(assert_all_mocked=True, assert_all_called=False) as mock,
    ):
        if response is not None:
            mock_response(mock, response)
        result = invoke(client, case["call"])
        request = capture_request(mock)

    expected_request = case["request"]
    if expected_request is None:
        assert request is None, "no request may be sent"
    else:
        assert request is not None, "a request must be sent"
        assert request["url"] == expected_request["url"]
        sent, wanted = request["params"], expected_request["params"]
        assert sent.keys() == wanted.keys()
        for name, value in wanted.items():
            assert same_param(value, sent[name]), name

    expected = case["expected"]
    if "series" in expected:
        assert result == {"series": expected["series"]}
    else:
        assert result.get("error") == expected["error"], result
        assert result.get("status_code") == expected.get("status_code")
        assert result.get("retry_after") == expected.get("retry_after")
        if "message_contains" in expected:
            assert expected["message_contains"] in result["message"]
