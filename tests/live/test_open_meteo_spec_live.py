"""Watch the published Open-Meteo OpenAPI files for changes.

A failure here is an early warning, not necessarily a breakage:
review the reported changes, update the tables if needed, then refresh
the local snapshot (see ``REFRESH_COMMAND``).
"""

import pytest

from tests.providers.open_meteo.spec import (
    KNOWN_SPEC_GAPS,
    REFRESH_COMMAND,
    SNAPSHOT,
    current,
    used,
)
from tests.specs import (
    Snapshot,
    combine,
    describe_drift,
    missing,
    snapshot_or_skip,
)

pytestmark = pytest.mark.live


@pytest.fixture
def upstream() -> Snapshot:
    return current()


def test_values_in_use_still_exist_upstream(upstream: Snapshot) -> None:
    # Needs no local snapshot: compares the client with upstream.
    problems = missing(used(), combine(upstream, KNOWN_SPEC_GAPS))
    assert not problems, "Upstream removed values Nabia uses:\n" + "\n".join(
        problems
    )


def test_snapshot_matches_upstream(upstream: Snapshot) -> None:
    snapshot = snapshot_or_skip(SNAPSHOT, REFRESH_COMMAND)
    changes = describe_drift(snapshot, upstream)
    assert not changes, (
        "The Open-Meteo specification changed. Review, then run "
        f"`{REFRESH_COMMAND}`:\n" + "\n".join(changes)
    )
