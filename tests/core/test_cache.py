from pathlib import Path

import pytest

from nabia.core.cache import SQLiteResponseCache, make_cache_key


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def test_roundtrip_and_expiry(tmp_path: Path) -> None:
    clock = FakeClock()
    cache = SQLiteResponseCache(tmp_path / "sub" / "c.sqlite3", clock=clock)
    cache.set("k", b"body", ttl_seconds=10)
    assert cache.get("k") == b"body"
    clock.now += 11
    assert cache.get("k") is None


def test_zero_ttl_is_not_stored(tmp_path: Path) -> None:
    cache = SQLiteResponseCache(tmp_path / "c.sqlite3")
    cache.set("k", b"body", ttl_seconds=0)
    assert cache.get("k") is None


def test_purge_and_clear(tmp_path: Path) -> None:
    clock = FakeClock()
    cache = SQLiteResponseCache(tmp_path / "c.sqlite3", clock=clock)
    cache.set("old", b"1", ttl_seconds=1)
    cache.set("new", b"2", ttl_seconds=100)
    clock.now += 5
    assert cache.purge_expired() == 1
    assert cache.get("new") == b"2"
    cache.clear()
    assert cache.get("new") is None


def test_file_is_private_on_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    modes: list[int] = []
    monkeypatch.setattr("nabia.core.cache.os.name", "posix")
    monkeypatch.setattr(Path, "chmod", lambda _self, mode: modes.append(mode))
    path = tmp_path / "c.sqlite3"
    cache = SQLiteResponseCache(path)
    assert cache.path == path
    cache.set("k", b"body", ttl_seconds=10)
    cache.set("k2", b"body", ttl_seconds=10)
    assert modes == [0o600]  # once, when the file is created


def test_cache_key_ignores_secrets() -> None:
    url = "https://api.test/data"
    first = make_cache_key("GET", url, {"lat": 1, "apikey": "A"})
    second = make_cache_key("get", url, {"apikey": "B", "lat": 1})
    assert first == second
    assert first != make_cache_key("GET", url, {"lat": 2})
