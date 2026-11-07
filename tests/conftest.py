"""Shared test fixtures."""

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep tests independent from the developer's environment.

    Settings read ``NABIA_*`` variables and a ``.env`` file in the
    working directory, which may hold real credentials. Every test runs
    in an empty directory with those variables removed.
    """
    for name in list(os.environ):
        if name.upper().startswith("NABIA_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
