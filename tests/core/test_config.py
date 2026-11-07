from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsConfigDict

from nabia.core.config import EnvSettings, NabiaSettings, require_secret
from nabia.core.errors import ConfigurationError
from nabia.core.tls import SslTrust
from nabia.providers.open_meteo import OpenMeteoSettings


class _KeySettings(EnvSettings):
    model_config = SettingsConfigDict(env_prefix="NABIA_DUMMY_")

    api_key: SecretStr | None = None


def test_defaults() -> None:
    settings = NabiaSettings()
    assert settings.timeout_seconds == 30.0
    assert settings.max_retries == 3
    assert settings.cache_enabled is False
    assert settings.ssl_trust is SslTrust.SYSTEM
    assert settings.user_agent.startswith("nabia/")


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NABIA_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("NABIA_SSL_TRUST", "certifi")
    settings = NabiaSettings()
    assert settings.timeout_seconds == 5.0
    assert settings.ssl_trust is SslTrust.CERTIFI


def test_dotenv_file_in_working_directory(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("NABIA_MAX_RETRIES=1\n", encoding="utf-8")
    assert NabiaSettings().max_retries == 1


def test_invalid_values_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NABIA_MAX_RETRIES", "-1")
    with pytest.raises(ValidationError):
        NabiaSettings()


def test_urls_must_use_https() -> None:
    with pytest.raises(ValidationError, match="https"):
        OpenMeteoSettings(forecast_url="http://api.open-meteo.com/v1/x")


def test_secret_is_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NABIA_DUMMY_API_KEY", "super-secret-value")
    settings = _KeySettings()
    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings.model_dump())
    assert require_secret(settings.api_key, "X") == "super-secret-value"


@pytest.mark.parametrize("value", [None, SecretStr(""), SecretStr("  ")])
def test_require_secret_missing(value: SecretStr | None) -> None:
    with pytest.raises(ConfigurationError, match="NABIA_DUMMY_API_KEY"):
        require_secret(value, "NABIA_DUMMY_API_KEY")
