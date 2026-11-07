"""Package metadata resolved from the installed distribution."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("nabia")
except PackageNotFoundError:  # pragma: no cover - source tree without install
    __version__ = "0.0.0+unknown"
