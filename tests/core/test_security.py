import logging

import pytest

from nabia.core.security import (
    install_log_redaction,
    redact_text,
    redact_url,
    register_secret_params,
)


def test_redact_url_masks_secret_params_only() -> None:
    url = "https://api.test/v1?lat=40.4&apikey=SECRET&lon=-3.7"
    assert (
        redact_url(url) == "https://api.test/v1?lat=40.4&apikey=***&lon=-3.7"
    )


def test_redact_url_is_case_insensitive() -> None:
    assert "SECRET" not in redact_url("https://api.test/?API_KEY=SECRET")


def test_redact_url_masks_userinfo() -> None:
    redacted = redact_url("https://user:pass@api.test/path")
    assert "user" not in redacted
    assert "pass" not in redacted


def test_registered_params_are_redacted() -> None:
    assert "XYZ" in redact_text("custom_cred=XYZ")
    register_secret_params(["custom_cred"])
    assert redact_text("GET /x?custom_cred=XYZ") == "GET /x?custom_cred=***"


def test_httpx_log_records_are_redacted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    install_log_redaction()
    install_log_redaction()  # idempotent
    logger = logging.getLogger("httpx")
    assert len(logger.filters) == 1
    with caplog.at_level(logging.INFO, logger="httpx"):
        logger.info(
            'HTTP Request: %s %s "%s"',
            "GET",
            "https://api.test/?token=SECRET",
            "HTTP/1.1 200 OK",
        )
    assert "SECRET" not in caplog.text
    assert "token=***" in caplog.text
