from pathlib import Path

from tests.specs import (
    Snapshot,
    combine,
    describe_drift,
    load_snapshot,
    missing,
    save_snapshot,
)

OLD: Snapshot = {"forecast": {"hourly": ["rain", "temperature_2m"]}}


def test_missing_reports_values_absent_from_reference() -> None:
    used: Snapshot = {"forecast": {"hourly": ["rain", "snow"]}}
    assert missing(used, OLD) == ["forecast.hourly: snow"]
    assert missing(OLD, OLD) == []


def test_describe_drift_reports_added_and_removed() -> None:
    new: Snapshot = {"forecast": {"hourly": ["rain", "temperature_80m"]}}
    assert describe_drift(OLD, new) == [
        "forecast.hourly added: temperature_80m",
        "forecast.hourly removed: temperature_2m",
    ]
    assert describe_drift(OLD, OLD) == []


def test_combine_merges_sections() -> None:
    extra: Snapshot = {"forecast": {"daily": ["rain_sum"]}}
    assert combine(OLD, extra) == {
        "forecast": {
            "daily": ["rain_sum"],
            "hourly": ["rain", "temperature_2m"],
        }
    }


def test_snapshot_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    save_snapshot(path, OLD)
    assert load_snapshot(path) == OLD
