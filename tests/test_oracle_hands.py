"""Layer 2 of the pytruco differential oracle (issue #89): random hands in both engines.

Slow: run with ``pytest -m slow tests/test_oracle_hands.py``. Our engine plays random
legal actions; each is replayed in pytruco, comparing acceptance, trick winners and
the points each side gains. Unexplained diffs and stale known diffs both fail.
Triage notes: ``docs/oracle-triage.md``; what the driver leaves out: the
``tests/oracle/hands.py`` docstring.
"""

import pytest

from tests.oracle.hands import run_seeds
from tests.oracle.known_diffs import KNOWN_DIFFS

N_HANDS = 20_000
LAYER2 = {"hand_points", "reject", "trick_winner", "hand_end"}


@pytest.mark.slow
def test_random_hands_match_pytruco_up_to_known_diffs() -> None:
    found, stats = run_seeds(range(N_HANDS))
    assert stats.hands > N_HANDS * 0.8  # the deal skip must stay a small minority
    assert not found, f"{len(found)} unexplained diffs, first: {found[:2]}"
    stale = [d.id for d in KNOWN_DIFFS if d.layer in LAYER2 and not stats.known[d.id]]
    assert not stale, f"known diffs that no longer occur in {N_HANDS} hands: {stale}"
