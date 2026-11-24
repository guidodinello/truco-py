"""Registry of known / expected disagreements between our engine and pytruco.

Each entry is a named predicate over a mismatch record. The oracle tests assert
that (a) every mismatch is matched by some entry (so a new diff fails loudly) and
(b) every entry matches at least one mismatch (so a stale entry, e.g. after an
upstream or local fix, fails too). ``xfail`` is deliberately not used: it would
hide new diffs. Triage details live in ``docs/oracle-triage.md``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Mismatch = dict[str, Any]


@dataclass(frozen=True, slots=True)
class KnownDiff:
    id: str  # triage id (D-xx) or variants-register id (V-xx)
    layer: str  # which comparison it applies to: "flor", "envido", "falta", ...
    matches: Callable[[Mismatch], bool]
    summary: str


KNOWN_DIFFS: list[KnownDiff] = []


def _n_piezas(m: Mismatch) -> int:
    from engine.truco import es_pieza

    return sum(es_pieza(*c, *m["muestra"]) for c in m["hand"])


KNOWN_DIFFS += [
    KnownDiff(
        id="D-01",
        layer="flor_score",
        matches=lambda m: _n_piezas(m) == 0 and m["tipo"] == 2 and m["ours"] - m["theirs"] == 20,
        summary=(
            "flor derecha without a pieza: we add 20 (rules.md §4.1, S3 L134: range 20-47), "
            "pytruco returns the bare sum (0-18)"
        ),
    ),
    KnownDiff(
        id="D-02",
        layer="falta",
        matches=lambda m: (
            max(m["scores"]) < m["target"] // 2
            and m["theirs"] == m["target"] // 2 - m["scores"][m["winner"]]
        ),
        summary=(
            "falta / resto while the leader is in malas: pytruco pays half the chico minus "
            "the winner's score; we pay the chico minus the leader's score (S3 L109, S2 Art 25)"
        ),
    ),
]
