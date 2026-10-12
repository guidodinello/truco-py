"""
ThresholdRolloutVonNeumannAgent: the fair VonNeumann with Threshold rollouts (#42, Option 1).

Identical to ``DeterminizedVonNeumannAgent`` (same hidden-card sampling, same EV rule) except for
the rollout policy: every seat in a rollout, the acting seat included, plays
``ThresholdAgent`` instead of choosing uniformly at random. Its EV estimates are therefore
calibrated against rule-based play rather than random play.

Fairness: ``ThresholdAgent`` reads envido / flor scores and hands of every seat on its team. Inside
a rollout those come from the determinized copy (sampled), never from the true deal, so the agent
still cannot see the hidden cards (tests/test_threshold_rollout_von_neumann.py checks it).

It is NOT independent of the Threshold agent: it models Threshold play by construction, so it
cannot serve as a held-out opponent for agents distilled from Threshold (#42).

The EV cache uses its own namespace: EVs under random rollouts and under Threshold rollouts are
different quantities and must never mix.
"""

from pathlib import Path

from engine.actions import Action
from engine.game_state import GameState

from .determinized_von_neumann_agent import DeterminizedVonNeumannAgent
from .threshold_agent import ThresholdAgent

CACHE_FORMAT = "vn-determinized-threshold-v1"  # file header and key namespace
_ROLLOUT_SEED_OFFSET = 2_000_003  # own stream, apart from the sampler (+1_000_003) and base seeds


class ThresholdRolloutVonNeumannAgent(DeterminizedVonNeumannAgent):
    """Fair MC rollout agent whose rollouts are played by ThresholdAgent."""

    name = "von_neumann_threshold_rollout"
    cache_format = CACHE_FORMAT

    def __init__(
        self,
        n_rollouts: int = 20,
        seed: int | None = None,
        cache_path: Path | None = None,
    ):
        super().__init__(n_rollouts=n_rollouts, seed=seed, cache_path=cache_path)
        self._rollout_policies = [
            ThresholdAgent(seed=None if seed is None else seed + _ROLLOUT_SEED_OFFSET + i)
            for i in range(6)
        ]

    def _run_rollout(self, state: GameState, player_idx: int) -> float:
        while not self._game.is_terminal(state):
            cp = state.current_player
            legal: list[Action] = self._game.legal_actions(state)
            if not legal:
                break
            self._game.apply_action(
                state, self._rollout_policies[cp].choose_action(state, legal, cp)
            )
        return self._game.get_rewards(state)[player_idx]
