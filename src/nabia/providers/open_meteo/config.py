"""Open-Meteo settings (environment prefix ``NABIA_OPEN_METEO_``)."""

from pydantic_settings import SettingsConfigDict

from nabia.core.config import EnvSettings, HttpsUrl


class OpenMeteoSettings(EnvSettings):
    """Open-Meteo endpoints.

    The public endpoints need no API key for non-commercial use. URLs
    are configurable to point at a self-hosted Open-Meteo instance.

    Attributes:
        forecast_url: Weather forecast endpoint.
        archive_url: Historical weather (reanalysis) endpoint.
    """

    model_config = SettingsConfigDict(env_prefix="NABIA_OPEN_METEO_")

    forecast_url: HttpsUrl = "https://api.open-meteo.com/v1/forecast"
    archive_url: HttpsUrl = "https://archive-api.open-meteo.com/v1/archive"
