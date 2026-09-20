"""
VonNeumannAgent: online Monte Carlo rollout agent.

For each legal action, simulates n_rollouts random completions of the game
and picks the action with the highest expected reward for player_idx.
No hard-coded rules — the optimal play emerges from EV estimation.

EV estimates are cached by observable game state so repeated situations
(common across many games) skip rollouts entirely. The cache can be persisted
to disk and reloaded across runs via cache_path (stored as JSON).
"""

import copy
import json
import random
from dataclasses import dataclass
from pathlib import Path

from engine.actions import Action
from engine.game import TrucoGame
from engine.game_state import GameState

_AUTOSAVE_EVERY = 500  # persist cache after this many new entries


@dataclass(frozen=True, slots=True)
class VonNeumannConfig:
    n_rollouts: int = 20
    seed: int | None = None
    cache_path: Path | None = None


class VonNeumannAgent:
    """MC rollout agent: picks the action with the highest estimated EV."""

    name = "von_neumann"

    def __init__(
        self,
        n_rollouts: int = 20,
        seed: int | None = None,
        cache_path: Path | None = None,
    ):
        self._cfg = VonNeumannConfig(n_rollouts=n_rollouts, seed=seed, cache_path=cache_path)
        self._rng = random.Random(seed)
        self._game = TrucoGame()
        self._rollout_agents = [
            _SimpleRandom(seed=(seed + i) if seed is not None else None) for i in range(6)
        ]
        self._cache: dict[str, float] = self._load_cache()
        self._new_entries: int = 0

    def reset(self) -> None:
        pass

    def choose_action(
        self,
        state: GameState,
        legal_actions: list[Action],
        player_idx: int,
    ) -> Action:
        if len(legal_actions) == 1:
            return legal_actions[0]

        best_action = legal_actions[0]
        best_ev = -float("inf")

        for action in legal_actions:
            ev = self._estimate_ev(state, action, player_idx)
            if ev > best_ev:
                best_ev = ev
                best_action = action

        return best_action

    def save_cache(self) -> None:
        """Persist the EV cache to cache_path as JSON. No-op if cache_path is None."""
        if self._cfg.cache_path is None:
            return
        self._cfg.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cfg.cache_path, "w") as f:
            json.dump(self._cache, f)
        self._new_entries = 0

    # ------------------------------------------------------------------

    def _load_cache(self) -> dict[str, float]:
        p = self._cfg.cache_path
        if p is not None and p.exists():
            with open(p) as f:
                return json.load(f)
        return {}

    def _estimate_ev(
        self,
        state: GameState,
        action: Action,
        player_idx: int,
    ) -> float:
        key = _state_key(state, player_idx, action)
        if key in self._cache:
            return self._cache[key]

        total = 0.0
        for _ in range(self._cfg.n_rollouts):
            s = copy.deepcopy(state)
            self._game.apply_action(s, action)
            total += self._run_rollout(s, player_idx)
        ev = total / self._cfg.n_rollouts

        self._cache[key] = ev
        self._new_entries += 1
        if self._new_entries >= _AUTOSAVE_EVERY:
            self.save_cache()

        return ev

    def _run_rollout(self, state: GameState, player_idx: int) -> float:
        while not self._game.is_terminal(state):
            cp = state.current_player
            legal = self._game.legal_actions(state)
            if not legal:
                break
            action = self._rollout_agents[cp].choose(legal)
            self._game.apply_action(state, action)
        return self._game.get_rewards(state)[player_idx]


class _SimpleRandom:
    """Minimal random chooser used only inside rollouts — avoids overhead of RandomAgent."""

    __slots__ = ("_rng",)

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def choose(self, legal: list[Action]) -> Action:
        return self._rng.choice(legal)


def _state_key(state: GameState, player_idx: int, action: Action) -> str:
    """JSON-serialized key built from observable state for player_idx.

    Only includes information visible to the current player — opponents'
    cards are excluded, which is also game-theoretically correct.
    """
    return json.dumps(
        [
            int(state.phase),
            player_idx,
            sorted(state.cards_in_hand[player_idx]),
            list(state.flor_score),
            list(state.envido),
            list(state.has_flor),
            state.flor_bid_team,
            state.flor_stake,
            state.envido_bid_team,
            state.envido_stake,
            state.truco_bid_team,
            state.truco_stake,
            state.trick_num,
            list(state.trick_winners),
            list(state.scores),
            int(action),
        ],
        separators=(",", ":"),
    )
