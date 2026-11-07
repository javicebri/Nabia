"""Open-Meteo: global weather forecast and historical reanalysis.

See ``README.md`` in this folder for endpoints, terms and quirks.
"""

from nabia.providers.open_meteo.client import OpenMeteoClient
from nabia.providers.open_meteo.config import OpenMeteoSettings
from nabia.providers.open_meteo.mapping import ARCHIVE, FORECAST

__all__ = ["ARCHIVE", "FORECAST", "OpenMeteoClient", "OpenMeteoSettings"]
