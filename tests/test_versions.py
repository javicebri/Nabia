"""Python and Dart share one version (one tag per release)."""

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_dart_package_shares_the_python_version() -> None:
    pyproject = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    pubspec = yaml.safe_load(
        (ROOT / "dart" / "pubspec.yaml").read_text(encoding="utf-8")
    )
    version_dart = (ROOT / "dart" / "lib" / "src" / "version.dart").read_text(
        encoding="utf-8"
    )
    version = pyproject["project"]["version"]
    assert pubspec["version"] == version
    assert f"packageVersion = '{version}'" in version_dart
