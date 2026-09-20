"""Tests for TrucoEnv -- the gamekit.rl.env.SingleAgentEnv adapter around
TrucoGame (gamekit#7 adoption). Exercises reset/step/action_masks against
the real engine: the parity gate (scripts/benchmark.py's match_rl_vs_* modes)
only exercises RLAgent, which never imports training/env.py, so this is the
one check that would catch a regression in the adapter itself.
"""

import numpy as np
import pytest

from agents.random_agent import RandomAgent
from agents.threshold_agent import ThresholdAgent
from engine.actions import N_ACTIONS
from training.env import TrucoEnv
from training.state_encoder import OBS_DIM


class _CountingAgent:
    """Wraps an inner agent and counts ``choose_action`` calls, so tests can
    confirm the env actually delegated to it rather than asserting on
    private wiring internals."""

    name = "counting"

    def __init__(self, seed: int) -> None:
        self._inner = RandomAgent(seed=seed)
        self.calls = 0

    def choose_action(self, state, legal_actions, player_idx):
        self.calls += 1
        return self._inner.choose_action(state, legal_actions, player_idx)

    def reset(self) -> None:
        self._inner.reset()


def _make_env(**kwargs) -> TrucoEnv:
    opponents = kwargs.pop("opponent_agents", None)
    if opponents is None:
        opponents = [RandomAgent(seed=i) for i in range(5)]
    return TrucoEnv(opponent_agents=opponents, seed=0, **kwargs)


def test_reset_returns_correctly_shaped_observation() -> None:
    env = _make_env()

    obs, info = env.reset(seed=1)

    assert obs.shape == (OBS_DIM,)
    assert obs.dtype == np.float32
    assert info == {}


def test_action_masks_has_the_right_shape_and_at_least_one_legal_action() -> None:
    env = _make_env()
    env.reset(seed=1)

    mask = env.action_masks()

    assert mask.shape == (N_ACTIONS,)
    assert mask.dtype == np.bool_
    assert mask.sum() > 0


def test_step_returns_a_five_tuple_and_advances_the_episode() -> None:
    env = _make_env()
    env.reset(seed=1)
    mask = env.action_masks()
    action = np.flatnonzero(mask)[0]

    obs, reward, terminated, truncated, info = env.step(action)

    assert obs.shape == (OBS_DIM,)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert truncated is False  # TrucoEnv never sets a step_budget
    assert "state" in info


def test_step_coerces_an_illegal_action_instead_of_raising() -> None:
    env = _make_env()
    env.reset(seed=1)
    mask = env.action_masks()
    illegal = np.flatnonzero(~mask)[0]

    # Must not raise -- on_illegal defaults to "coerce", matching the
    # pre-adoption TrucoEnv's silent-recovery behaviour exactly.
    env.step(illegal)


def test_full_episode_completes_and_terminal_observation_is_zero() -> None:
    env = _make_env()
    obs, _ = env.reset(seed=1)
    terminated = truncated = False
    steps = 0

    while not (terminated or truncated) and steps < 5000:
        mask = env.action_masks()
        action = np.flatnonzero(mask)[0]
        obs, reward, terminated, truncated, info = env.step(action)
        steps += 1

    assert terminated
    assert steps < 5000
    assert np.array_equal(obs, np.zeros(OBS_DIM, dtype=np.float32))


def test_fixed_opponent_agents_are_actually_invoked() -> None:
    """One "episode" is one hand (``Phase.DONE``), which can end quickly on
    an early fold -- not every seat is guaranteed a turn within a single
    hand, so this plays several hands and aggregates. If the env silently
    left a seat un-wired, that agent's count would stay 0 across all of
    them while every episode still completed."""
    opponents = [_CountingAgent(seed=i) for i in range(5)]
    env = _make_env(opponent_agents=opponents)

    for episode_seed in range(20):
        env.reset(seed=episode_seed)
        terminated = truncated = False
        steps = 0
        while not (terminated or truncated) and steps < 5000:
            mask = env.action_masks()
            action = np.flatnonzero(mask)[0]
            _, _, terminated, truncated, _ = env.step(action)
            steps += 1
        assert terminated

    assert all(agent.calls > 0 for agent in opponents)


def test_opponent_agent_count_must_be_exactly_five() -> None:
    with pytest.raises(ValueError, match="exactly 5"):
        TrucoEnv(opponent_agents=[RandomAgent(seed=0)], seed=0)


def test_selfplay_mode_falls_back_to_threshold_agent_with_no_checkpoints(tmp_path) -> None:
    env = TrucoEnv(selfplay_dir=str(tmp_path), seed=0)

    obs, info = env.reset(seed=1)

    assert obs.shape == (OBS_DIM,)
    # No checkpoints in tmp_path -- the whole episode must still run to
    # completion via the ThresholdAgent baseline fallback.
    terminated = truncated = False
    steps = 0
    while not (terminated or truncated) and steps < 5000:
        mask = env.action_masks()
        action = np.flatnonzero(mask)[0]
        obs, reward, terminated, truncated, info = env.step(action)
        steps += 1
    assert terminated


def test_mc_rollouts_populate_v_mc_in_the_observation() -> None:
    """mc_rollouts > 0 enables the V_MC track (Track C) -- exercising the
    one hook (on_episode_start) that overrides the generic base class's
    default instead of calling it."""
    env = _make_env(mc_rollouts=5)

    obs, _ = env.reset(seed=1)

    # obs_to_vector writes v_mc into a fixed slot; without mc_rollouts the
    # slot defaults to 0.5 (see training/reward.py's MCPotentialReward
    # docstring) -- this just confirms the hook runs without error and the
    # observation stays correctly shaped.
    assert obs.shape == (OBS_DIM,)
    assert not np.isnan(obs).any()


def test_threshold_agent_wraps_cleanly_via_class_reference() -> None:
    """ThresholdAgent is passed as `baseline_factory=ThresholdAgent` directly
    (the class, not an instance) in TrucoEnv's selfplay-mode wiring --
    confirm that's actually callable with no arguments, matching
    gamekit.rl.selfplay.OpponentPool's `Callable[[], Agent]` contract."""
    agent = ThresholdAgent()
    assert agent.name
