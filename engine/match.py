"""
TrucoMatch: a full match of hands — chicos, malas/buenas, mano rotation and the
6-player redondilla / pico-a-pico alternation (``docs/rules.md`` §8–9).

  - Mano moves one seat to the right every round (S3 L60–64).
  - Until either side reaches half the chico (the buenas), rounds alternate: a
    general 3v3 round (redondilla), then a mano-a-mano round in which each player
    plays the rival facing them, one pair after the other, off the same deal
    (S2 Art 83–85; S3 L66–68). The first round of every chico is general.
  - In mano-a-mano hands the falta and the resto are capped (S2 Art 86,
    ``Rules.pico_falta_cap``); scores carry over between the pairs (S2 Art 87).
  - A side that reaches ``chico_points`` wins the chico; the first to
    ``chicos_to_win`` chicos wins the match (S2 Art 4; S3 L56).

The match exposes the same turn interface as ``TrucoGame`` — ``legal_actions``,
``apply_action``, ``is_terminal`` — with ``MatchState.hand`` as the state agents see.
"""

import random
from dataclasses import dataclass

from .actions import Action
from .game import TrucoGame, deal_from_seed
from .game_state import Deal, GameState
from .phases import Phase
from .rules import N_SEATS, Rules

PICO_FACING = 3  # the rival facing seat i is seat i + 3 (teams alternate around the table)


@dataclass(slots=True)
class MatchState:
    hand: GameState  # the hand in progress (what agents act on)
    scores: list[int]  # points in the current chico, [team A, team B]
    chicos: list[int]  # chicos won
    round_mano: int  # mano of the current round
    rounds_in_chico: int  # rounds started in the current chico
    pico: bool  # the current round is mano-a-mano
    pico_pairs: list[tuple[int, int]]  # mano-a-mano pairs still to play this round
    deal: Deal  # the current round's deal
    rng: random.Random  # deals every round
    hands_played: int
    winner: int  # team that won the match, -1 while in progress


class TrucoMatch:
    def __init__(self, rules: Rules | None = None):
        self.rules = rules if rules is not None else Rules()
        self.game = TrucoGame(rules=self.rules)

    def reset(self, seed: int | None = None, mano: int = 0) -> MatchState:
        rng = random.Random(seed)
        deal = deal_from_seed(rng.getrandbits(64))
        ms = MatchState(
            hand=self.game.reset(deal=deal, mano=mano),
            scores=[0, 0],
            chicos=[0, 0],
            round_mano=mano,
            rounds_in_chico=1,
            pico=False,
            pico_pairs=[],
            deal=deal,
            rng=rng,
            hands_played=0,
            winner=-1,
        )
        return ms

    def legal_actions(self, ms: MatchState) -> list[Action]:
        return self.game.legal_actions(ms.hand)

    def apply_action(self, ms: MatchState, action: Action) -> MatchState:
        self.game.apply_action(ms.hand, action)
        if ms.hand.phase == Phase.DONE:
            self._after_hand(ms)
        return ms

    def is_terminal(self, ms: MatchState) -> bool:
        return ms.winner != -1

    # ------------------------------------------------------------------

    def _after_hand(self, ms: MatchState) -> None:
        ms.hands_played += 1
        ms.scores = list(ms.hand.scores)
        chico = self.rules.chico_points
        if max(ms.scores) >= chico:
            team = 0 if ms.scores[0] >= ms.scores[1] else 1
            ms.chicos[team] += 1
            if ms.chicos[team] >= self.rules.chicos_to_win:
                ms.winner = team
                return
            ms.scores = [0, 0]
            ms.rounds_in_chico = 0
            ms.pico_pairs = []
            ms.pico = False
            self._next_round(ms)
            return
        if ms.pico_pairs:
            self._next_pico_hand(ms)
            return
        self._next_round(ms)

    def _next_round(self, ms: MatchState) -> None:
        ms.round_mano = (ms.round_mano + 1) % N_SEATS
        ms.deal = deal_from_seed(ms.rng.getrandbits(64))
        pico = (
            self.rules.pico_a_pico
            and ms.rounds_in_chico > 0  # the first round of a chico is general
            and not ms.pico  # rounds alternate
            and max(ms.scores) < self.rules.half
        )
        ms.rounds_in_chico += 1
        ms.pico = pico
        if pico:
            m = ms.round_mano
            ms.pico_pairs = [
                ((m + i) % N_SEATS, (m + i + PICO_FACING) % N_SEATS) for i in range(PICO_FACING)
            ]
            self._next_pico_hand(ms)
            return
        self._set_hand(ms, self.game.reset(scores=ms.scores, mano=ms.round_mano, deal=ms.deal))

    def _next_pico_hand(self, ms: MatchState) -> None:
        mano, rival = ms.pico_pairs.pop(0)
        hand = self.game.reset(
            scores=ms.scores,
            mano=mano,
            seats=[mano, rival],
            deal=ms.deal,
            falta_cap=self.rules.pico_falta_cap,
        )
        self._set_hand(ms, hand)

    def _set_hand(self, ms: MatchState, hand: GameState) -> None:
        """Install the next hand; one can end at the deal (a one-sided flor that
        reaches the chico), so keep dealing until somebody has to act."""
        ms.hand = hand
        if hand.phase == Phase.DONE:
            self._after_hand(ms)
