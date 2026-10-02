"""
Rule configuration and the pure rule functions the hand engine is built on.

Every rule cites ``docs/rules.md`` (sources S1–S7, variants V-xx). Where the
sources disagree the engine follows **S2** (GranAventura reglamento), the most
complete rulebook; the variant knobs that change benchmark numbers live in
``Rules`` so a different variant is a constructor argument, not a code change.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .game_state import team_of

N_SEATS = 6
NO_TEAM = -1  # parda (tied trick) / no winner yet
OVER_FALTA_CALL = 2  # a first call above the falta counts as «simple de dos tantos» (S2 Art 36)


@dataclass(frozen=True, slots=True)
class Rules:
    """Variant knobs (``docs/rules.md`` §10)."""

    chico_points: int = 40  # V-04: one game of 40 (S3); S1 plays 20, S5 30
    chicos_to_win: int = 1  # V-04: 1 = a single chico (S3); S2 Art 4 = 2 (best of three)
    pico_a_pico: bool = True  # S2 Art 83–84 / S3 L66–68: 3v3 alternation below half
    pico_falta_cap: int = 10  # V-03: S2 Art 86 caps falta/resto at 10 (S3 L66: 6)
    ley_de_juego: bool = False  # V-09: «a ley de juego» / echar los perros (S2 Art 70–82)

    @property
    def half(self) -> int:
        """Malas/buenas boundary (S2 Art 4; S3 L56)."""
        return self.chico_points // 2


def turn_order(mano: int, seats: Sequence[int]) -> list[int]:
    """Seats in play order: mano first, then to the right (S3 L64), i.e. ascending
    seat index modulo 6, restricted to ``seats``."""
    return [s for s in ((mano + i) % N_SEATS for i in range(N_SEATS)) if s in seats]


def falta(scores: Sequence[int], chico_points: int, cap: int | None = None) -> int:
    """Points the **leading** side still needs (S2 Art 23, 25; S3 L109). The resto
    is the same number (S2 Art 33). In mano-a-mano rounds it is capped (S2 Art 86)."""
    value = chico_points - max(scores)
    return min(value, cap) if cap is not None else value


def hand_winner(results: Sequence[int], mano_team: int) -> int | None:
    """Winner of the hand from the trick results so far (0/1 = team, -1 = parda),
    or None while undecided. S1 Art 40–41, S2 Art 58–59, S3 L70–81:

    - two tricks won; a side that won the first and then wins or ties the second;
    - after a parda, whoever wins the next trick (``[parda, parda, B]`` → B, A-07);
    - ``[A, B, parda]`` → the winner of the first; three pardas → mano's side.
    """
    for team in (0, 1):
        if results.count(team) >= 2:
            return team
    if len(results) >= 2:
        r0, r1 = results[0], results[1]
        if r0 != NO_TEAM and r1 == NO_TEAM:
            return r0
        if r0 == NO_TEAM and r1 != NO_TEAM:
            return r1
    if len(results) == 3:
        if results[2] != NO_TEAM:
            return results[2]
        if results[0] != NO_TEAM:
            return results[0]
        return mano_team
    return None


def declaration_winner(values: Mapping[int, int], order: Sequence[int]) -> int:
    """Team that wins an accepted envido (or flor) by the declaration procedure.

    S2 Art 39–41, 44: mano declares first; afterwards the rival of the last
    declarer who **beats** the figure declares, taking first the most-mano such
    rival (reading (b) of V-14: «más mano a la izquierda de aquél si lo hubiere y
    en caso contrario el primero de la derecha»). Equal never beats, so a tie on
    the best figure goes to the side that declared it first — not always mano's
    side (A-05, A-06). Only seats in ``values`` declare (players with flor for a
    flor contest, players still in play for envido); ``order`` is the hand's turn
    order and its first declarer speaks first.
    """
    declarers = [s for s in order if s in values]
    last = declarers[0]
    best = values[last]
    while True:
        challenger = next(
            (s for s in declarers if team_of(s) != team_of(last) and values[s] > best),
            None,
        )
        if challenger is None:
            return team_of(last)
        last, best = challenger, values[challenger]


def capped_total(old_total: int, amount: int, prev_amount: int, limit: int, first: bool) -> int:
    """New accumulated envite total after a call (S2 Art 35–36).

    - a first call above the falta «se tomará como simple de dos tantos»;
    - a raise that would exceed the falta «será siempre válido por el importe del
      envite o reenvite que le precede o por la falta si fuera ésta menor».
    """
    if first:
        return amount if amount <= limit else OVER_FALTA_CALL
    if old_total + amount <= limit:
        return old_total + amount
    return min(old_total + prev_amount, limit)
