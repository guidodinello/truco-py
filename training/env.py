"""
TrucoEnv: single-agent Gym wrapper around TrucoGame.

Now a thin adapter over ``gamekit.rl.env.SingleAgentEnv`` (gamekit#7). The
generic structure -- turn-advancing until the learner's turn, legal-action
masking, self-play opponent resampling, the reset/step gym protocol -- lives
in ``gamekit.rl``; this module supplies only what's genuinely truco-specific:
the 204-dim state encoder, the flat 53-action codec, reward shaping, and the
V_MC Monte-Carlo win-probability estimate computed once per episode from the
initial deal (Track C -- this one stays here, not in gamekit, since it's
built from truco's own ``hand_pts``/``team_of`` and was never part of
gamekit#7's scope).

Observation: 204-dim float32 vector (see state_encoder.py).
Action:       Discrete(53) with legal action masking.
Reward:       Configurable via reward_shaper (default: sparse ±1 on DONE).
"""

import copy
from typing import Any

import numpy as np
from gamekit.rl.env import SingleAgentEnv
from gamekit.rl.selfplay import OpponentPool
from gymnasium import spaces

from agents.base import TrucoAgent
from agents.random_agent import RandomAgent
from agents.threshold_agent import ThresholdAgent
from engine.actions import N_ACTIONS, Action
from engine.game import TrucoGame
from engine.game_state import GameState, team_of
from training.reward import RewardShaper, SparseReward
from training.self_play import _CheckpointAgent
from training.state_encoder import OBS_DIM, obs_to_vector


class _GameAdapter:
    """Adapts ``TrucoGame`` to ``gamekit.rl.protocols.TurnBasedGame[GameState,
    Action]``. TrucoGame already exposes every method this needs except
    ``acting_player`` -- truco has no out-of-turn decisions (unlike catan's
    robber-discard queue or trade responses), so it's just
    ``state.current_player``. No change to ``engine/game.py`` itself."""

    def __init__(self, target_score: int) -> None:
        self._game = TrucoGame(target=target_score)

    def reset(self, seed: int | None = None) -> GameState:
        return self._game.reset(seed=seed)

    def legal_actions(self, state: GameState) -> list[Action]:
        return self._game.legal_actions(state)

    def apply_action(self, state: GameState, action: Action) -> GameState:
        return self._game.apply_action(state, action)

    def is_terminal(self, state: GameState) -> bool:
        return self._game.is_terminal(state)

    def acting_player(self, state: GameState) -> int:
        return state.current_player


class _ActionCodec:
    """``gamekit.rl.protocols.ActionCodec[Action]``: ``Action`` is already a
    flat ``IntEnum`` over ``N_ACTIONS`` indices, so this is a pass-through."""

    n_actions = N_ACTIONS

    def to_index(self, action: Action) -> int:
        return int(action)

    def from_index(self, index: int) -> Action:
        return Action(index)


class TrucoEnv(SingleAgentEnv[GameState, Action]):
    """
    Gymnasium-compatible environment for single-agent Truco training.

    Parameters
    ----------
    opponent_agents : list of Agent, length 5
        Fixed agents for the 5 non-training seats. Used when selfplay_dir is None.
        If both are None, defaults to 5 RandomAgents.
    selfplay_dir : str | None
        When set, opponents are resampled at each reset() by scanning this directory
        for *.zip checkpoint files (via ``gamekit.rl.selfplay.OpponentPool``). Falls
        back to ThresholdAgent when no checkpoints exist. This is the correct way to
        do self-play across subprocesses -- no shared state, each env independently
        reads the latest checkpoints from disk.
    reward_shaper : RewardShaper, optional
        Reward function. Defaults to SparseReward.
    seed : int, optional
        RNG seed for reproducibility.
    target_score : int
        Points needed to win a game (default 40).
    randomize_seat : bool
        If True (default), training agent is placed in a random seat each episode.
        Set to False to always use seat 0 (useful for debugging).
    threshold_mix : float
        In selfplay mode, probability [0,1] of using ThresholdAgent instead of a
        checkpoint opponent. Prevents strategy collapse. Default 0.2.
    mc_rollouts : int
        Number of random rollouts to run from the initial deal state at each
        reset() to estimate V_MC (win probability under random play). The result
        is stored in obs[169] throughout the episode. Default 0 (disabled).
        Recommended range: 10-50. Adds ~3-15ms per reset in subprocesses.
    """

    def __init__(
        self,
        opponent_agents: list[TrucoAgent] | None = None,
        selfplay_dir: str | None = None,
        reward_shaper: "RewardShaper | None" = None,
        seed: int | None = None,
        target_score: int = 40,
        randomize_seat: bool = True,
        threshold_mix: float = 0.2,
        mc_rollouts: int = 0,
        inference_handle: Any = None,
    ):
        self._reward_shaper = reward_shaper or SparseReward()
        self._mc_rollouts = mc_rollouts
        self._v_mc: float | None = None  # V_MC computed at each reset(), None if disabled

        game = _GameAdapter(target_score)
        codec = _ActionCodec()
        observation_space = spaces.Box(low=0.0, high=1.0, shape=(OBS_DIM,), dtype=np.float32)

        if selfplay_dir is None:
            agents = (
                opponent_agents
                if opponent_agents is not None
                else [RandomAgent() for _ in range(5)]
            )
            if len(agents) != 5:
                raise ValueError("Need exactly 5 opponent agents")
            super().__init__(
                game=game,
                codec=codec,
                encode=self._encode,
                reward=self._reward_shaper,
                observation_space=observation_space,
                num_seats=6,
                agents=agents,
                randomize_seat=randomize_seat,
                seed=seed,
            )
        else:
            pool: OpponentPool[GameState, Action] = OpponentPool(
                selfplay_dir,
                "truco_selfplay_*.zip",
                load_opponent=lambda path: _CheckpointAgent(
                    str(path), inference_handle=inference_handle
                ),
                baseline_factory=ThresholdAgent,
                baseline_mix=threshold_mix,
            )
            super().__init__(
                game=game,
                codec=codec,
                encode=self._encode,
                reward=self._reward_shaper,
                observation_space=observation_space,
                num_seats=6,
                opponent_pool=pool,
                randomize_seat=randomize_seat,
                seed=seed,
            )

    # ------------------------------------------------------------------
    # Truco-specific hooks
    # ------------------------------------------------------------------

    def _encode(self, state: GameState, seat: int) -> np.ndarray:
        return obs_to_vector(state, seat, v_mc=self._v_mc)

    def on_episode_start(self, state: GameState, seat: int) -> None:
        """Compute V_MC (Track C) from the initial deal, before any opponent
        acts, and notify the reward shaper with *that* -- not with ``seat``,
        which is what the generic base class's default hook would pass.
        Deliberately does not call ``super().on_episode_start()``: this is
        exactly the override case ``SingleAgentEnv.on_episode_start``'s
        docstring describes."""
        self._v_mc = (
            self._compute_v_mc(state, seat, self._mc_rollouts) if self._mc_rollouts > 0 else None
        )
        self._reward_shaper.on_episode_start(state, self._v_mc if self._v_mc is not None else 0.5)

    def _compute_v_mc(self, state: GameState, seat: int, n_rollouts: int) -> float:
        """Estimate P(my team wins) via random rollouts from the initial deal.

        Runs `n_rollouts` games from `state` with all players choosing uniformly
        at random. Returns the fraction of games where the training agent's team
        wins. Uses deep copies to leave `state` unmodified. Draws from this env's
        own RNG (`self._rng`, owned by `SingleAgentEnv`) -- the same stream that
        picks the learner seat and coerces illegal actions, exactly as before
        this class moved onto gamekit.rl.
        """
        my_team = team_of(seat)
        wins = 0
        for _ in range(n_rollouts):
            s = copy.deepcopy(state)
            while not self._game.is_terminal(s):
                legal = self._game.legal_actions(s)
                if not legal:
                    break
                s = self._game.apply_action(s, self._rng.choice(legal))
            if s.hand_pts[my_team] > s.hand_pts[1 - my_team]:
                wins += 1
        return wins / n_rollouts
