"""Discover registered providers and build isolated clients.

Every provider follows the layout in ``docs/adding-a-provider.md``, so
tools find its pieces by convention instead of per-provider code:

* ``nabia.providers.<name>.config`` defines one ``EnvSettings``
  subclass with the endpoints as defaults.
* ``nabia.providers.<name>`` exports one ``BaseClient`` subclass whose
  ``PROVIDER`` is ``<name>``, built as ``Client(settings, *,
  nabia_settings=...)``.
"""

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol, cast

from nabia.core.config import EnvSettings, NabiaSettings
from nabia.providers.base import BaseClient
from nabia.providers.registry import all_tables


class _ClientFactory(Protocol):
    """Constructor shared by every provider client."""

    def __call__(
        self, settings: EnvSettings, /, *, nabia_settings: NabiaSettings
    ) -> BaseClient: ...


def providers() -> tuple[str, ...]:
    """Return the registered provider identifiers, in registry order."""
    return tuple(dict.fromkeys(table.provider for table in all_tables()))


def settings_class(provider: str) -> type[EnvSettings]:
    """Return the settings class defined in the provider's ``config``.

    Raises:
        LookupError: The module does not define exactly one.
    """
    module = importlib.import_module(f"nabia.providers.{provider}.config")
    found = [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type)
        and issubclass(obj, EnvSettings)
        and obj.__module__ == module.__name__
    ]
    if len(found) != 1:
        raise LookupError(
            f"{module.__name__} must define one EnvSettings subclass, "
            f"found {len(found)}"
        )
    return found[0]


def client_class(provider: str) -> type[BaseClient]:
    """Return the client class exported by the provider package.

    Raises:
        LookupError: The package does not export exactly one.
    """
    package = importlib.import_module(f"nabia.providers.{provider}")
    found = [
        obj
        for obj in vars(package).values()
        if isinstance(obj, type)
        and issubclass(obj, BaseClient)
        and getattr(obj, "PROVIDER", None) == provider
    ]
    if len(found) != 1:
        raise LookupError(
            f"{package.__name__} must export one client for {provider!r}, "
            f"found {len(found)}"
        )
    return found[0]


def default_settings(provider: str) -> EnvSettings:
    """Return the provider settings with their declared defaults.

    ``model_construct()`` skips the settings sources, so neither the
    environment nor a ``.env`` file is read: results must not depend
    on the machine.
    """
    return settings_class(provider).model_construct()


@contextmanager
def provider_client(provider: str) -> Iterator[BaseClient]:
    """Yield a client with default settings and no retries."""
    factory = cast(_ClientFactory, client_class(provider))
    client = factory(
        default_settings(provider),
        nabia_settings=NabiaSettings.model_construct(max_retries=0),
    )
    with client:
        yield client
