"""Layer 1 of the pytruco differential oracle (issue #89): exhaustive pure functions.

Every mismatch must be covered by a registered known diff, and every registered
diff must still occur (a stale entry fails, so a fix on either side is noticed).
Triage notes: ``docs/oracle-triage.md``.
"""

from pathlib import Path

import pytest

from tests.oracle import compare
from tests.oracle.known_diffs import KNOWN_DIFFS, Mismatch

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"


def _assert_covered(mismatches: list[Mismatch], layers: set[str]) -> None:
    entries = [d for d in KNOWN_DIFFS if d.layer in layers]
    uncovered = [m for m in mismatches if not any(d.matches(m) for d in entries)]
    assert not uncovered, f"{len(uncovered)} unexplained diffs, first: {uncovered[:3]}"
    stale = [d.id for d in entries if not any(d.matches(m) for m in mismatches)]
    assert not stale, f"known diffs that no longer occur: {stale}"


def test_engine_never_imports_pytruco() -> None:
    offenders = [p.name for p in ENGINE_DIR.rglob("*.py") if "pytruco" in p.read_text()]
    assert offenders == []


def test_pieza_detection_matches_pytruco() -> None:
    assert compare.pieza_mismatches() == []


def test_card_strength_order_matches_pytruco() -> None:
    assert compare.strength_mismatches() == []


@pytest.fixture(scope="module")
def hand_mismatches() -> list[Mismatch]:
    return compare.hand_mismatches()


def test_flor_detection_and_envido_match_pytruco(hand_mismatches: list[Mismatch]) -> None:
    assert [m for m in hand_mismatches if m["layer"] in ("flor_detect", "envido")] == []


def test_flor_score_diffs_are_all_known(hand_mismatches: list[Mismatch]) -> None:
    _assert_covered([m for m in hand_mismatches if m["layer"] == "flor_score"], {"flor_score"})


def test_falta_diffs_are_all_known() -> None:
    _assert_covered(compare.falta_mismatches(), {"falta"})
