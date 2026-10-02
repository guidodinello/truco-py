from dataclasses import dataclass

from .phases import Phase

# Team membership (same as truco.py but local to avoid circular deps).
# Seats alternate between the teams (S2 Art 3); play runs to the right = ascending seat.
TEAM_A = [0, 2, 4]
TEAM_B = [1, 3, 5]

NO_ENVITE, ENVITE_ENVIDO, ENVITE_FLOR = 0, 1, 2  # GameState.envite_kind


def team_of(player: int) -> int:
    """Return 0 (team A) or 1 (team B) for a player index."""
    return player % 2


Card = tuple[int, int]  # (palo_idx, numero)


@dataclass(frozen=True, slots=True)
class Deal:
    """
    Immutable deal-time data set once at the start of each hand.
    A mano-a-mano (pico a pico) round plays three hands off one deal (S2 Art 85).
    """

    manos: tuple[tuple[Card, ...], ...]  # original 3 cards per seat
    muestra: Card  # (palo_idx, numero)
    has_flor: tuple[bool, ...]  # one flag per seat
    envido: tuple[int, ...]  # envido score per seat
    flor_score: tuple[int, ...]  # flor score per seat (0 if no flor)


@dataclass(slots=True)
class GameState:
    # ------------------------------------------------------------------
    # Per-hand static (copied from the Deal)
    # ------------------------------------------------------------------
    manos: list[list[Card]]  # manos[i] = [(palo, num), ...]
    muestra: Card
    has_flor: list[bool]  # [bool] * 6 — flor is sung, so this is public
    envido: list[int]  # envido score per seat
    flor_score: list[int]  # flor score per seat (0 if no flor)

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------
    seats: list[int]  # seats dealt into this hand: all 6, or a mano-a-mano pair
    mano: int  # first to play and to declare (S3 L60)
    order: list[int]  # seats of this hand in turn order, mano first
    in_play: list[bool]  # per seat; False when not in the hand, or after PASO / MAZO
    cards_in_hand: list[list[Card]]  # remaining cards per seat

    # Cumulative chico scores and limits, fixed at the deal (S2 Art 25)
    scores: list[int]  # [pts_A, pts_B]
    target: int  # points of the chico
    falta: int  # the falta = the resto for this hand (capped in mano-a-mano)

    phase: Phase
    current_player: int

    # ------------------------------------------------------------------
    # «A ley de juego» (S2 Art 70–82)
    # ------------------------------------------------------------------
    ley_offered: list[bool]  # per team: has had the chance to impose the régimen
    ley_team: int  # side that imposed it (-1 = none)
    ley_bundle: int  # the LEY_* action imposed (-1 = none)
    ley_caller: int  # seat that imposed it

    # ------------------------------------------------------------------
    # Envites: envido (no flor in the hand) or «con flor» between flor holders
    # ------------------------------------------------------------------
    flor_holders: list[int]  # seats with flor in this hand, in turn order
    flor_passed: list[bool]  # per team: declined to envite in the flor contest
    envite_kind: int  # NO_ENVITE / ENVITE_ENVIDO / ENVITE_FLOR
    envite_team: int  # team whose call is waiting for an answer (-1 = none pending)
    envite_caller: int  # seat that made the pending call
    envite_total: int  # tantos at stake if the pending call is accepted
    envite_accepted: int  # tantos already accepted (paid if a raise is declined)
    envite_last_amount: int  # amount of the last call; a raise must match it (S2 Art 35)
    envite_calls: int  # number of calls in this exchange (1 = first call)
    envite_contra: bool  # a «contra flor» was called (rival flors are paid too)
    envite_banned_team: int  # side that may not envite (S2 Art 78), -1 = none
    envido_done: bool  # envido / flor settled for this hand
    resume_phase: Phase  # PLAY or TRUCO: where to go once the envite is answered

    # ------------------------------------------------------------------
    # Truco
    # ------------------------------------------------------------------
    truco_level: int  # accepted value of the hand: 1 (no call), 2, 3, 4
    truco_pending: bool  # a call to truco_level + 1 is waiting for an answer
    truco_team: int  # team that made the pending call (-1 = none)
    truco_raise_team: int  # side entitled to the next raise (-1 = either may say truco)
    truco_responder: int  # seat answering the pending truco call
    spoke_truco: list[bool]  # per seat: said truco/retruco/vale cuatro or «quiero» to one
    resume_player: int  # seat whose PLAY turn continues after a call is answered

    # ------------------------------------------------------------------
    # Card play
    # ------------------------------------------------------------------
    trick_num: int  # current trick index: 0, 1, 2
    tricks: list[dict[int, Card]]  # tricks[t] = {player_idx: (palo, num)}
    trick_winners: list[int]  # team that won each trick: 0, 1, or -1 (parda / not played)
    lead_player: int  # player who leads current trick
    trick_play_order: list[int]  # turn order for the current trick
    trick_play_idx: int  # index into trick_play_order

    # ------------------------------------------------------------------
    # Accumulated hand pts (awarded throughout the hand)
    # ------------------------------------------------------------------
    hand_pts: list[int]  # [pts_A, pts_B]
