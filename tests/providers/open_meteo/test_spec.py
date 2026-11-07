"""Offline checks of the client against the local spec snapshot.

Skipped when the snapshot has not been created on this machine.
"""

from nabia.providers.open_meteo.mapping import ARCHIVE_SOURCES
from tests.providers.open_meteo.spec import (
    KNOWN_SPEC_GAPS,
    REFRESH_COMMAND,
    SNAPSHOT,
    used,
)
from tests.specs import combine, missing, snapshot_or_skip


def test_everything_sent_is_in_the_specification() -> None:
    snapshot = snapshot_or_skip(SNAPSHOT, REFRESH_COMMAND)
    problems = missing(used(), combine(snapshot, KNOWN_SPEC_GAPS))
    assert not problems, "Not in the Open-Meteo spec:\n" + "\n".join(problems)


def test_known_gaps_are_still_gaps() -> None:
    # If upstream documents a gap, it must be removed from the list.
    snapshot = snapshot_or_skip(SNAPSHOT, REFRESH_COMMAND)
    still_missing = missing(KNOWN_SPEC_GAPS, snapshot)
    assert still_missing == missing(KNOWN_SPEC_GAPS, {}), (
        "A known gap is now documented upstream; remove it from "
        "KNOWN_SPEC_GAPS"
    )


def test_archive_source_kinds_cover_documented_sources() -> None:
    # Every source we classify must exist upstream, and every upstream
    # source (except the default) should be classified.
    snapshot = snapshot_or_skip(SNAPSHOT, REFRESH_COMMAND)
    documented = set(snapshot["archive"]["models"]) - {"best_match"}
    assert set(ARCHIVE_SOURCES) == documented
