import ssl
import sys

import pytest

from nabia.core.tls import SslTrust, build_verify, system_store_supported


def test_certifi_uses_httpx_default() -> None:
    assert build_verify(SslTrust.CERTIFI) is True


def test_system_store_on_supported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert isinstance(build_verify(SslTrust.SYSTEM), ssl.SSLContext)


def test_android_falls_back_to_certifi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Android may report "linux"; the API level hook is the tell.
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "getandroidapilevel", lambda: 34, raising=False)
    assert system_store_supported() is False
    assert build_verify(SslTrust.SYSTEM) is True


def test_unknown_platform_falls_back_to_certifi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "emscripten")
    assert build_verify(SslTrust.SYSTEM) is True
