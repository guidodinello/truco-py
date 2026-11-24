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


# ── layer 2 (hand-level) ───────────────────────────────────────────────────

_ENVITE_EVENTS = ("ENVIDO", "REAL_ENVIDO", "FALTA_ENVIDO")


def _gain(m: Mismatch) -> tuple[list[int], list[int]]:
    return m["ours"], m["theirs"]


def _extra_for_one_team(m: Mismatch, extra: int) -> bool:
    """pytruco pays exactly ``extra`` more than we do, to one team only."""
    ours, theirs = _gain(m)
    return sorted(t - o for t, o in zip(theirs, ours, strict=True)) == [0, extra]


KNOWN_DIFFS += [
    KnownDiff(
        id="D-03",
        layer="hand_points",
        matches=lambda m: (
            m["event"] == "QUIERO"
            and m.get("pre_envite_kind") == 1
            and m["pre_accepted"] > 0
            and _extra_for_one_team(m, m["pre_accepted"])
        ),
        summary=(
            "falta envido after earlier envites: pytruco pays the falta plus the tantos "
            "accumulated before it; we pay the falta alone (the raise replaces them, S2 Art 36)"
        ),
    ),
    KnownDiff(
        id="D-04",
        layer="hand_points",
        matches=lambda m: (
            m["event"] == "FOLD"
            and m.get("pre_envite_kind") == 1
            and m["pre_calls"] > 1
            and _extra_for_one_team(m, 1)
        ),
        summary=(
            "«no quiero» to an envido raise: pytruco pays the accepted tantos + 1, we pay the "
            "accepted tantos (rules.md §7, S3 L111 «el punto del toque querido más el punto del "
            "toque no querido»)"
        ),
    ),
    KnownDiff(
        id="D-05",
        layer="hand_points",
        matches=lambda m: (
            m["event"] == "flor"
            and any(
                m["ours"][t] == 3 * m["flors"][t]
                and m["theirs"][t] == 3 * sum(m["flors"])
                and m["ours"][1 - t] == m["theirs"][1 - t] == 0
                for t in (0, 1)
            )
        ),
        summary=(
            "contested flor, nobody envites: pytruco's winner collects 3 per flor of BOTH "
            "sides; we pay the winner's own side's flors only (S2 Art 20)"
        ),
    ),
    KnownDiff(
        id="D-06",
        layer="reject",
        matches=lambda m: m["pre_prev_parda"] and m["turn"][0] != m["turn"][1],
        summary=(
            "who leads after a parda: mano (S1 Art 39, rules.md §6) vs pytruco's first of the "
            "tied players in throwing order; any later move by the other player is then "
            "rejected as out of turn"
        ),
    ),
    KnownDiff(
        id="D-07",
        layer="reject",
        matches=lambda m: (
            m["event"] in _ENVITE_EVENTS and m["pre_phase"] == "PLAY" and m["pre_truco_level"] > 1
        ),
        summary=(
            "envido called after a truco was accepted, by a player who has not spoken (S2 Art 22): "
            "we allow it, pytruco forbids any envite once the truco is accepted"
        ),
    ),
    KnownDiff(
        id="D-08",
        layer="reject",
        matches=lambda m: (
            m["event"] in _ENVITE_EVENTS and m["pre_phase"] == "TRUCO" and m["pre_truco_level"] >= 2
        ),
        summary=(
            "«el envido va primero» over a pending retruco / vale cuatro: we allow it (S2 Art 60), "
            "pytruco only over a pending truco"
        ),
    ),
    KnownDiff(
        id="V-05",
        layer="reject",
        matches=lambda m: (
            m["event"] == "REAL_ENVIDO" and m["pre_phase"] == "ENVIDO" and m["pre_last_amount"] >= 3
        ),
        summary=(
            "real envido raised again over a real envido: repeatable in ours (V-05, S2 Art 35), "
            "not in pytruco"
        ),
    ),
]


def _winner_swapped(m: Mismatch) -> bool:
    ours, theirs = _gain(m)
    return (ours[0] > ours[1]) != (theirs[0] > theirs[1])


KNOWN_DIFFS.append(
    KnownDiff(
        id="D-09",
        layer="hand_points",
        matches=lambda m: (
            _winner_swapped(m)
            and (m["envido_tie"] if m["event"] == "QUIERO" else m["flor_tie"])
            and m["event"] in ("QUIERO", "flor")
        ),
        summary=(
            "tie between the two sides' best envido / flor: we follow the declaration procedure "
            "(ties do not beat, so the side that declared the figure first wins; S2 Art 39-44, "
            "rules.md §3.5, A-05/A-06); pytruco gives the tie to the most-mano of the tied players"
        ),
    )
)
