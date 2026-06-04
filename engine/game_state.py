from dataclasses import dataclass

from .phases import Phase

# Team membership (same as truco.py but local to avoid circular deps)
TEAM_A = [0, 2, 4]
TEAM_B = [1, 3, 5]


def team_of(player: int) -> int:
    """Return 0 (team A) or 1 (team B) for a player index."""
    return 0 if player in TEAM_A else 1


@dataclass(frozen=True, slots=True)
class Deal:
    """
    Immutable deal-time data set once at the start of each hand.
    Separated from mutable play state to make immutability explicit.
    """

    manos: tuple[tuple[tuple[int, int], ...], ...]  # original 3 cards per player
    muestra: tuple[int, int]  # (palo_idx, numero)
    has_flor: tuple[bool, ...]  # one flag per player
    envido: tuple[int, ...]  # envido score per player
    flor_score: tuple[int, ...]  # flor score per player (0 if no flor)


@dataclass(slots=True)
class GameState:
    # ------------------------------------------------------------------
    # Per-hand static (set once at deal, stored in Deal for immutability)
    # ------------------------------------------------------------------
    manos: list[list[tuple[int, int]]]  # manos[i] = [(palo, num), ...]
    muestra: tuple[int, int]  # (palo_idx, numero)
    has_flor: list[bool]  # [bool] * 6
    envido: list[int]  # envido score per player
    flor_score: list[int]  # flor score per player (0 if no flor)

    # ------------------------------------------------------------------
    # Mutable per-hand state
    # ------------------------------------------------------------------
    cards_in_hand: list[list[tuple[int, int]]]  # remaining cards per player

    # Cumulative game scores
    scores: list[int]  # [pts_A, pts_B]
    target: int  # winning score (default 40)

    # Current phase and whose turn it is
    phase: Phase
    current_player: int

    # ------------------------------------------------------------------
    # Flor bidding
    # ------------------------------------------------------------------
    # Two players interact: flor_bidder (first) and flor_responder (second).
    # If only one team has flor, this phase is auto-resolved.
    flor_bidder: int  # player who acts first in flor (-1 if no flor)
    flor_responder: int  # opposing player (-1 if one-sided flor)
    flor_stake: int  # current pts at stake: 0 (initial), 3, 5, or game_pts
    flor_prev_stake: int  # stake before last raise (fold pays this; init=3)
    flor_bid_team: int  # team that last raised (-1 = no bid yet)

    # ------------------------------------------------------------------
    # Envido bidding
    # ------------------------------------------------------------------
    # All 6 players get one turn to initiate. Once a bid is made, only
    # envido_active_bidder and envido_active_responder interact.
    envido_bid_queue: list[int]  # players still to take their initiation turn
    envido_active_bidder: int  # player who last raised (-1 if no active bid)
    envido_active_responder: int  # player who must respond (-1 if no active bid)
    envido_stake: int  # accumulated pts at stake (2 per envido, 3 per real)
    envido_prev_stake: int  # for fold resolution (init=1: base fold value)
    envido_bid_team: int  # team with active bid (-1 if none)
    envido_is_falta: bool  # True if falta envido was bid (pays game pts)

    # ------------------------------------------------------------------
    # Truco bidding
    # ------------------------------------------------------------------
    # Same two-layer model as envido.
    truco_bid_queue: list[int]
    truco_active_bidder: int
    truco_active_responder: int
    truco_stake: int  # 0 (no bid/base=1pt), 2, 3, 4
    truco_bid_team: int  # -1 if no bid
    truco_folded: bool  # True if someone folded (no need to play cards)
    truco_fold_winner: int  # team that won by fold (-1 if not folded)

    # ------------------------------------------------------------------
    # Card play
    # ------------------------------------------------------------------
    trick_num: int  # current trick index: 0, 1, 2
    tricks: list[dict[int, tuple[int, int]]]  # tricks[t] = {player_idx: (palo, num)}
    trick_winners: list[int]  # team that won each trick: 0, 1, or -1 (tie)
    lead_player: int  # player who leads current trick
    trick_play_order: list[int]  # 6-player order for current trick
    trick_play_idx: int  # index into trick_play_order

    # ------------------------------------------------------------------
    # Accumulated hand pts (awarded throughout the hand)
    # ------------------------------------------------------------------
    hand_pts: list[int]  # [pts_A, pts_B]
