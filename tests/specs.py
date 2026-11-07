"""Helpers to watch upstream API specifications for drift.

Each provider can keep a small JSON snapshot with the parts of its
upstream specification that Nabia depends on (parameter names and
allowed values), instead of the full document. Snapshots are local
maintenance baselines: they are git-ignored and never published.

* Offline tests check that every name Nabia sends exists in the
  snapshot.
* Live tests compare the snapshot with the current upstream
  specification and report what was added or removed.

Specifications are untrusted input: YAML is always parsed with
``yaml.safe_load``.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from nabia.core.http import HttpClient

#: Section name (e.g. ``"hourly"``) to sorted allowed values.
Contract = dict[str, list[str]]

#: Specification id (e.g. ``"forecast"``) to its contract.
Snapshot = dict[str, Contract]


def fetch_yaml(url: str) -> Any:
    """Download and safely parse a YAML specification."""
    with HttpClient(provider="spec-watch") as http:
        body = http.get(url, cache_ttl=0)
    return yaml.safe_load(body)


def load_snapshot(path: Path) -> Snapshot:
    """Read a stored snapshot."""
    data: Snapshot = json.loads(path.read_text(encoding="utf-8"))
    return data


def snapshot_or_skip(path: Path, refresh_command: str) -> Snapshot:
    """Load a snapshot, or skip the test when it does not exist.

    Snapshots are local-only (git-ignored), so a fresh clone has none
    until the refresh command is run.
    """
    if not path.exists():
        pytest.skip(f"No spec snapshot yet; create it with: {refresh_command}")
    return load_snapshot(path)


def save_snapshot(path: Path, snapshot: Snapshot) -> None:
    """Write a snapshot in a stable, diff-friendly format."""
    text = json.dumps(snapshot, ensure_ascii=False, indent=1, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def combine(*snapshots: Snapshot) -> Snapshot:
    """Merge snapshots section by section (union of values)."""
    merged: dict[str, dict[str, set[str]]] = {}
    for snapshot in snapshots:
        for spec_id, contract in snapshot.items():
            target = merged.setdefault(spec_id, {})
            for section, values in contract.items():
                target.setdefault(section, set()).update(values)
    return {
        spec_id: {section: sorted(vals) for section, vals in sections.items()}
        for spec_id, sections in merged.items()
    }


def missing(used: Snapshot, reference: Snapshot) -> list[str]:
    """List values Nabia uses that are absent from ``reference``."""
    problems: list[str] = []
    for spec_id, contract in sorted(used.items()):
        available = reference.get(spec_id, {})
        for section, values in sorted(contract.items()):
            absent = sorted(set(values) - set(available.get(section, [])))
            if absent:
                problems.append(f"{spec_id}.{section}: {', '.join(absent)}")
    return problems


def describe_drift(old: Mapping[str, Contract], new: Snapshot) -> list[str]:
    """Describe added and removed values between two snapshots."""
    changes: list[str] = []
    for spec_id in sorted(old.keys() | new.keys()):
        before_spec = old.get(spec_id, {})
        after_spec = new.get(spec_id, {})
        for section in sorted(before_spec.keys() | after_spec.keys()):
            before = set(before_spec.get(section, []))
            after = set(after_spec.get(section, []))
            if added := sorted(after - before):
                changes.append(
                    f"{spec_id}.{section} added: {', '.join(added)}"
                )
            if removed := sorted(before - after):
                changes.append(
                    f"{spec_id}.{section} removed: {', '.join(removed)}"
                )
    return changes
