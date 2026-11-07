"""Base for raw provider schemas (mirrors of upstream JSON).

Raw schemas must never guess: pydantic's default (lax) mode would turn
``"1.5"`` into ``1.5``, ``true`` into ``1.0`` and ``3600.0`` into
``3600``, silently accepting data that the provider no longer sends as
documented. Strict mode rejects them, so a changed upstream format
raises ``ProviderContractError`` instead. JSON integers are still
accepted where floats are expected, and ISO 8601 strings where dates
are.
"""

from pydantic import BaseModel, ConfigDict


class RawModel(BaseModel):
    """Strict base class for every provider's ``schemas.py`` model."""

    model_config = ConfigDict(strict=True)
