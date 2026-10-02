"""
ThresholdAgent: rule-based policy derived from the Monte Carlo analysis.

Decision rules:
  Flor (contest between both sides' flor holders):
    - 1v1: envite «con flor envido» if flor_score >= 35, else let flors compare
    - 1v2: raise if flor_score >= 37 (aggressive) / 38 (passive EV)
    - answer a flor envite with «quiero» above the threshold, else «no quiero»
  Envido (on its first turn, before playing a card):
    - 1v1: bid if own envido >= 28
    - Team (pie): bid if team best envido >= 33
  Truco:
    - Call truco once, on its first turn, if holding a strong card
      (3, 2, 1E, 1B, or a pieza); answer a truco with retruco/quiero when strong.
  Card play:
    - Play the strongest card in hand (greedy). Never goes to the mazo.
  A ley de juego: never imposes it; declines it.
"""

import random

from engine.actions import ENVIDO_CALLS, Action, action_to_card, is_card_action
from engine.card import card_strength
from engine.game_state import TEAM_A, TEAM_B, GameState, team_of
from engine.phases import Phase

# Thresholds from Monte Carlo experiments
MC_THRESHOLDS = {
    "envido_1v1": 28,
    "envido_team": 33,
    "flor_1v1": 35,
    "flor_1v2_aggressive": 37,
    "flor_1v2_passive": 38,
}
STRONG_CARD = 8  # card_strength >= 8: a non-pieza 2 or better


class ThresholdAgent:
    """MC-threshold policy. Falls back to random for unknown situations."""

    name = "threshold"

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def reset(self) -> None:
        pass

    def choose_action(
        self,
        state: GameState,
        legal_actions: list[Action],
        player_idx: int,
    ) -> Action:
        phase = state.phase

        if phase == Phase.LEY:
            return self._first_legal(legal_actions, [Action.LEY_PASS, Action.FOLD])
        if phase == Phase.FLOR:
            return self._flor_action(state, legal_actions, player_idx)
        if phase == Phase.ENVIDO:
            return self._envido_answer(state, legal_actions, player_idx)
        if phase == Phase.TRUCO:
            return self._truco_answer(state, legal_actions, player_idx)
        if phase == Phase.PLAY:
            return self._play_action(state, legal_actions, player_idx)

        return self._rng.choice(legal_actions)

    # ------------------------------------------------------------------

    def _first_legal(self, legal: list[Action], preferred: list[Action]) -> Action:
        for a in preferred:
            if a in legal:
                return a
        return self._rng.choice(legal)

    def _flor_action(
        self,
        state: GameState,
        legal: list[Action],
        p: int,
    ) -> Action:
        my_score = state.flor_score[p]
        my_team = team_of(p)

        # Count opponent flor players
        opp_flors = sum(1 for s in state.flor_holders if team_of(s) != my_team)
        threshold = (
            MC_THRESHOLDS["flor_1v2_aggressive"] if opp_flors >= 2 else MC_THRESHOLDS["flor_1v1"]
        )
        strong = my_score >= threshold

        if state.envite_team == -1:  # our turn to open the contest
            preferred = [Action.ENVIDO, Action.FLOR_PASS] if strong else [Action.FLOR_PASS]
            return self._first_legal(legal, preferred)
        return self._first_legal(legal, [Action.QUIERO] if strong else [Action.FOLD])

    def _should_bid_envido(self, state: GameState, p: int) -> bool:
        team_members = TEAM_A if team_of(p) == 0 else TEAM_B
        team_best = max(state.envido[i] for i in team_members)
        return (
            team_best >= MC_THRESHOLDS["envido_team"]
            or state.envido[p] >= MC_THRESHOLDS["envido_1v1"]
        )

    def _envido_answer(
        self,
        state: GameState,
        legal: list[Action],
        p: int,
    ) -> Action:
        if self._should_bid_envido(state, p):
            return self._first_legal(legal, [Action.QUIERO])
        return self._first_legal(legal, [Action.FOLD])

    def _strong_hand(self, state: GameState, p: int) -> bool:
        pm, nm = state.muestra
        hand = state.cards_in_hand[p]
        return bool(hand) and max(card_strength(*c, pm, nm) for c in hand) >= STRONG_CARD

    def _truco_answer(
        self,
        state: GameState,
        legal: list[Action],
        p: int,
    ) -> Action:
        if self._strong_hand(state, p):
            return self._first_legal(legal, [Action.RETRUCO, Action.QUIERO])
        return self._first_legal(legal, [Action.FOLD])

    def _play_action(
        self,
        state: GameState,
        legal: list[Action],
        p: int,
    ) -> Action:
        """Call envido / truco on the first turn if strong, then play the strongest card."""
        first_turn = state.trick_num == 0 and len(state.cards_in_hand[p]) == 3
        if first_turn:
            if self._should_bid_envido(state, p):
                for a in (Action.REAL_ENVIDO, Action.ENVIDO):
                    if a in legal:
                        return a
            if Action.TRUCO in legal and self._strong_hand(state, p):
                return Action.TRUCO

        pm, nm = state.muestra
        best_action = None
        best_strength = -1
        for action in legal:
            if is_card_action(action):
                palo, num = action_to_card(action)
                s = card_strength(palo, num, pm, nm)
                if s > best_strength:
                    best_strength = s
                    best_action = action

        if best_action is not None:
            return best_action
        return self._rng.choice([a for a in legal if a not in ENVIDO_CALLS] or legal)
