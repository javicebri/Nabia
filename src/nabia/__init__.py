"""Typed access to public weather, climate and agri-environmental APIs.

Output always uses the canonical vocabulary in :mod:`nabia.catalog`,
whatever the provider. Provider clients are imported explicitly so
optional heavy dependencies only load when needed::

    from nabia import GeoPoint, Variable
    from nabia.providers.open_meteo import OpenMeteoClient
"""

from nabia._meta import __version__
from nabia.catalog import Resolution, Unit, Variable
from nabia.core.config import NabiaSettings
from nabia.core.errors import (
    AuthenticationError,
    ConfigurationError,
    MissingDependencyError,
    NabiaError,
    NoDataError,
    ProviderConnectionError,
    ProviderContractError,
    ProviderError,
    ProviderHTTPError,
    ProviderServerError,
    RateLimitError,
    UnitConversionError,
    UnitMismatchError,
    UnsupportedVariableError,
)
from nabia.core.models import (
    DailySeries,
    GeoPoint,
    HourlySeries,
    SourceKind,
    Surface,
    TimeSeries,
)

__all__ = [
    "AuthenticationError",
    "ConfigurationError",
    "DailySeries",
    "GeoPoint",
    "HourlySeries",
    "MissingDependencyError",
    "NabiaError",
    "NabiaSettings",
    "NoDataError",
    "ProviderConnectionError",
    "ProviderContractError",
    "ProviderError",
    "ProviderHTTPError",
    "ProviderServerError",
    "RateLimitError",
    "Resolution",
    "SourceKind",
    "Surface",
    "TimeSeries",
    "Unit",
    "UnitConversionError",
    "UnitMismatchError",
    "UnsupportedVariableError",
    "Variable",
    "__version__",
]
