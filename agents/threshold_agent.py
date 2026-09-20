"""
ThresholdAgent: rule-based policy derived from the Monte Carlo analysis.

Decision rules:
  Flor:
    - 1v1: raise if flor_score >= 35
    - 1v2: raise if flor_score >= 37 (aggressive) / 38 (passive EV)
  Envido:
    - 1v1: bid if own envido >= 28
    - Team (pie): bid if team best envido >= 33
  Truco:
    - Bid truco if holding a strong card (3, 2, 1E, 1B, or a pieza).
  Card play:
    - Play the strongest card in hand (greedy).
"""

import random

from engine.actions import Action, is_card_action
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

        if phase == Phase.FLOR:
            return self._flor_action(state, legal_actions, player_idx)
        if phase == Phase.ENVIDO:
            return self._envido_action(state, legal_actions, player_idx)
        if phase == Phase.TRUCO:
            return self._truco_action(state, legal_actions, player_idx)
        if phase == Phase.PLAY:
            return self._play_action(state, legal_actions, player_idx)

        return self._rng.choice(legal_actions)

    # ------------------------------------------------------------------

    def _flor_action(
        self,
        state: GameState,
        legal: list[Action],
        p: int,
    ) -> Action:
        my_score = state.flor_score[p]
        my_team = team_of(p)

        # Count opponent flor players
        opp_team_members = TEAM_B if my_team == 0 else TEAM_A
        opp_flors = sum(1 for i in opp_team_members if state.has_flor[i])

        # Determine threshold
        if opp_flors >= 2:
            threshold = MC_THRESHOLDS["flor_1v2_aggressive"]
        else:
            threshold = MC_THRESHOLDS["flor_1v1"]

        if my_score >= threshold:
            # Raise if possible
            for a in [Action.FLOR_CON_ENVIDO, Action.FLOR_CHICO, Action.FLOR_PASS]:
                if a in legal:
                    return a
        # Fold or accept (passive)
        for a in [Action.FLOR_PASS, Action.FOLD]:
            if a in legal:
                return a
        return self._rng.choice(legal)

    def _envido_action(
        self,
        state: GameState,
        legal: list[Action],
        p: int,
    ) -> Action:
        my_envido = state.envido[p]
        my_team = team_of(p)
        team_members = TEAM_A if my_team == 0 else TEAM_B
        team_best = max(state.envido[i] for i in team_members)

        # Use team threshold when deciding to initiate
        should_bid = team_best >= MC_THRESHOLDS["envido_team"]
        # Fallback to individual threshold
        if not should_bid:
            should_bid = my_envido >= MC_THRESHOLDS["envido_1v1"]

        if state.envido_bid_team == -1:
            # Initiation turn
            if should_bid:
                for a in [Action.REAL_ENVIDO, Action.ENVIDO]:
                    if a in legal:
                        return a
            return Action.ENVIDO_PASS if Action.ENVIDO_PASS in legal else self._rng.choice(legal)

        # Responding to opponent
        if state.envido_bid_team != my_team:
            if should_bid:
                return (
                    Action.ENVIDO_PASS if Action.ENVIDO_PASS in legal else self._rng.choice(legal)
                )
            return Action.FOLD if Action.FOLD in legal else self._rng.choice(legal)

        return self._rng.choice(legal)

    def _truco_action(
        self,
        state: GameState,
        legal: list[Action],
        p: int,
    ) -> Action:
        pm, nm = state.muestra
        hand = state.cards_in_hand[p]
        max_str = max(card_strength(*c, pm, nm) for c in hand) if hand else 0

        # Bid truco if holding a strong card (strength >= 8 = non-pieza 2 or better)
        should_bid = max_str >= 8

        if state.truco_bid_team == -1:
            # Initiation
            if should_bid and Action.TRUCO in legal:
                return Action.TRUCO
            return Action.TRUCO_PASS if Action.TRUCO_PASS in legal else self._rng.choice(legal)

        # Responding
        if state.truco_bid_team != team_of(p):
            if should_bid:
                # Accept and potentially raise
                for a in [Action.RETRUCO, Action.TRUCO_PASS]:
                    if a in legal:
                        return a
            return Action.FOLD if Action.FOLD in legal else self._rng.choice(legal)

        return self._rng.choice(legal)

    def _play_action(
        self,
        state: GameState,
        legal: list[Action],
        p: int,
    ) -> Action:
        """Play the strongest available card."""
        from engine.actions import action_to_card

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

        return best_action if best_action is not None else self._rng.choice(legal)
