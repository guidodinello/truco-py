"""
TrucoEnv: single-agent Gym wrapper around TrucoGame.

The 'training agent' is assigned a random seat at each reset().
The other 5 seats are filled by opponent_agents.
The env handles stepping through opponent turns automatically so that
every call to step() corresponds to ONE action by the training agent.

Observation: 204-dim float32 vector (see state_encoder.py).
Action:       Discrete(53) with legal action masking.
Reward:       Configurable via reward_shaper (default: sparse ±1 on DONE).
"""

import copy
import glob
import random

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from agents.base import Agent
from agents.random_agent import RandomAgent
from agents.threshold_agent import ThresholdAgent
from engine.actions import N_ACTIONS, Action
from engine.game import TrucoGame
from engine.game_state import GameState, team_of
from engine.phases import Phase
from training.reward import RewardShaper, SparseReward
from training.state_encoder import OBS_DIM, obs_to_vector


class TrucoEnv(gym.Env):
    """
    Gymnasium-compatible environment for single-agent Truco training.

    Parameters
    ----------
    opponent_agents : list of Agent, length 5
        Fixed agents for the 5 non-training seats. Used when selfplay_dir is None.
        If both are None, defaults to 5 RandomAgents.
    selfplay_dir : str | None
        When set, opponents are resampled at each reset() by scanning this directory
        for *.zip checkpoint files. Falls back to ThresholdAgent when no checkpoints
        exist. This is the correct way to do self-play across subprocesses — no shared
        state, each env independently reads the latest checkpoints from disk.
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
        Recommended range: 10–50. Adds ~3–15ms per reset in subprocesses.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        opponent_agents: list | None = None,
        selfplay_dir: str | None = None,
        reward_shaper: "RewardShaper | None" = None,
        seed: int | None = None,
        target_score: int = 40,
        randomize_seat: bool = True,
        threshold_mix: float = 0.2,
        mc_rollouts: int = 0,
        inference_handle=None,
    ):
        self._game = TrucoGame(target=target_score)
        self._reward_shaper = reward_shaper or SparseReward()
        self._rng = random.Random(seed)
        self._randomize_seat = randomize_seat
        self._selfplay_dir = selfplay_dir
        self._threshold_mix = threshold_mix
        self._mc_rollouts = mc_rollouts
        self._inference_handle = inference_handle
        self._v_mc: float | None = None  # V_MC computed at each reset(), None if disabled

        if selfplay_dir is None:
            self._opponents: list[Agent] = (
                opponent_agents
                if opponent_agents is not None
                else [RandomAgent() for _ in range(5)]
            )
            assert len(self._opponents) == 5, "Need exactly 5 opponent agents"
        else:
            # Populated at each reset() via _resample_opponents()
            self._opponents = [ThresholdAgent() for _ in range(5)]

        # Gymnasium spaces (required by gym.Env)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Discrete(N_ACTIONS)

        self._state: GameState | None = None
        self._my_seat: int = 0  # which seat the training agent occupies
        self._seat_map: list[int] = []  # seat_map[env_player] = game_player

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(self, seed: int | None = None, options: dict | None = None):
        """Reset the environment and return (obs, info)."""
        if seed is not None:
            self._rng = random.Random(seed)

        # Assign training agent to a random seat
        self._my_seat = self._rng.randint(0, 5) if self._randomize_seat else 0

        # In selfplay mode, resample opponents from disk each episode
        if self._selfplay_dir is not None:
            self._resample_opponents()

        for agent in self._opponents:
            agent.reset()

        # Keep resetting until the training agent has at least one turn
        while True:
            self._state = self._game.reset(seed=self._rng.randint(0, 2**31))

            # Compute V_MC from the initial deal before any player acts (Track C)
            self._v_mc = None
            if self._mc_rollouts > 0:
                self._v_mc = self._compute_v_mc(self._state, self._mc_rollouts)

            # Notify reward shaper of episode start with V_MC estimate (Track D)
            self._reward_shaper.on_episode_start(
                self._state, self._v_mc if self._v_mc is not None else 0.5
            )

            self._run_opponents()
            if self._state.phase != Phase.DONE:
                break

        obs = obs_to_vector(self._state, self._my_seat, v_mc=self._v_mc)
        return obs, {}

    def step(self, action: int):
        """Apply one action for the training agent; run opponents until next turn."""
        assert self._state is not None, "Call reset() first"
        assert self._state.phase != Phase.DONE, "Episode already done"

        legal = self.action_masks()
        if not legal[action]:
            # Illegal action — force a random legal one (penalise in reward)
            legal_indices = np.where(legal)[0]
            action = int(self._rng.choice(legal_indices))

        self._game.apply_action(self._state, Action(action))
        self._run_opponents()

        done = self._state.phase == Phase.DONE
        reward = self._reward_shaper.compute(self._state, self._my_seat, done)

        if done:
            obs = np.zeros(OBS_DIM, dtype=np.float32)
        else:
            obs = obs_to_vector(self._state, self._my_seat, v_mc=self._v_mc)

        return obs, reward, done, False, {"state": self._state}

    def action_masks(self) -> np.ndarray:
        """Return boolean mask (N_ACTIONS,) of legal actions for training agent."""
        mask = np.zeros(N_ACTIONS, dtype=bool)
        if self._state is None or self._state.phase == Phase.DONE:
            return mask
        for a in self._game.legal_actions(self._state):
            mask[a.value] = True
        return mask

    def close(self):
        pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resample_opponents(self):
        """Rescan checkpoint dir and pick 5 fresh opponents (selfplay mode only).

        Only picks from selfplay checkpoints (truco_selfplay_*.zip) to avoid
        loading weak warm-start checkpoints as self-play opponents.
        Falls back to ThresholdAgent when no selfplay checkpoints exist yet,
        or when the threshold_mix dice roll says so.
        """
        from training.self_play import _CheckpointAgent

        checkpoints = sorted(glob.glob(f"{self._selfplay_dir}/truco_selfplay_*.zip"))
        for i in range(5):
            if checkpoints and self._rng.random() > self._threshold_mix:
                path = self._rng.choice(checkpoints)
                self._opponents[i] = _CheckpointAgent(
                    path, inference_handle=self._inference_handle
                )
            else:
                self._opponents[i] = ThresholdAgent()

    def _run_opponents(self):
        """Advance the game by running all opponent turns until it's the training
        agent's turn (or the episode ends)."""
        state = self._state
        while state.phase != Phase.DONE:
            cp = state.current_player
            if cp == self._my_seat:
                break  # training agent's turn
            # Determine which opponent controls this seat
            opp_idx = self._opponent_idx(cp)
            legal = self._game.legal_actions(state)
            if not legal:
                break
            action = self._opponents[opp_idx].choose_action(state, legal, cp)
            self._game.apply_action(state, action)

    def _compute_v_mc(self, state: GameState, n_rollouts: int) -> float:
        """Estimate P(my team wins) via random rollouts from the initial deal.

        Runs `n_rollouts` games from `state` with all players choosing uniformly
        at random. Returns the fraction of games where the training agent's team
        wins. Uses deep copies to leave `state` unmodified.
        """
        my_team = team_of(self._my_seat)
        wins = 0
        for _ in range(n_rollouts):
            s = copy.deepcopy(state)
            while s.phase != Phase.DONE:
                legal = self._game.legal_actions(s)
                if not legal:
                    break
                self._game.apply_action(s, self._rng.choice(legal))
            if s.hand_pts[my_team] > s.hand_pts[1 - my_team]:
                wins += 1
        return wins / n_rollouts

    def _opponent_idx(self, seat: int) -> int:
        """Map a game seat (excluding my_seat) to an opponent agent index [0,4]."""
        seats = [s for s in range(6) if s != self._my_seat]
        return seats.index(seat)
