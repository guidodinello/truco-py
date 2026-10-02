"""ContextBank (D4) and PointDiffReward (D5)."""

import random

import numpy as np
import pytest

from agents.random_agent import RandomAgent
from engine.game import TrucoGame
from training.context_bank import ContextBank, build_bank
from training.env import TrucoEnv
from training.reward import PointDiffReward, SparseReward


@pytest.fixture(scope="module")
def bank() -> ContextBank:
    return build_bank(n_matches=6, seed=123, workers=1)


def test_bank_holds_real_general_round_states(bank):
    assert len(bank) > 6
    assert bank.scores.shape == (len(bank), 2) and bank.mano.shape == (len(bank),)
    assert bank.scores.min() >= 0 and bank.scores.max() < 40  # pre-hand, so below the chico
    assert set(np.unique(bank.mano)) <= set(range(6))
    assert (bank.scores == 0).all(axis=1).any(), "every match starts 0-0"
    assert (bank.scores.sum(axis=1) > 0).any(), "later hands carry real scores"


def test_bank_is_deterministic_and_roundtrips(bank, tmp_path):
    again = build_bank(n_matches=6, seed=123, workers=1)
    assert np.array_equal(bank.scores, again.scores) and np.array_equal(bank.mano, again.mano)
    bank.save(tmp_path / "b.npz")
    loaded = ContextBank.load(tmp_path / "b.npz")
    assert np.array_equal(bank.scores, loaded.scores)


def test_env_resets_from_bank_contexts(bank):
    env = TrucoEnv(opponent_agents=[RandomAgent(seed=i) for i in range(5)], context_bank=bank)
    rows = {(int(a), int(b), int(m)) for (a, b), m in zip(bank.scores, bank.mano, strict=True)}
    starts = set()
    for seed in range(40):
        env.reset(seed=seed)
        st = env._state
        starts.add((st.scores[0], st.scores[1]))
        # whoever was mano when the hand started is still recoverable from the order
        assert (st.scores[0], st.scores[1], st.order[0]) in rows
    assert len(starts) > 1, "scores vary across episodes (the point of D4)"


def test_env_without_bank_starts_at_zero():
    env = TrucoEnv(opponent_agents=[RandomAgent(seed=i) for i in range(5)])
    env.reset(seed=1)
    assert env._state.scores == [0, 0]


def test_bank_sampling_is_a_pure_function_of_the_rng(bank):
    assert bank.sample(random.Random("x")) == bank.sample(random.Random("x"))


# ── D5 ────────────────────────────────────────────────────────────────────────


def _done_state(pts: list[int]):
    state = TrucoGame().reset(seed=3)
    state.hand_pts = pts
    return state


@pytest.mark.parametrize(
    ("pts", "player", "expected"),
    [([3, 0], 0, 3 / 15), ([3, 0], 1, -3 / 15), ([1, 4], 0, -3 / 15), ([2, 2], 0, 0.0)],
)
def test_point_diff_reward_is_scaled_difference_from_the_players_team(pts, player, expected):
    assert PointDiffReward(15.0).compute(_done_state(pts), player, True) == pytest.approx(expected)


def test_point_diff_reward_is_clipped_and_terminal_only():
    r = PointDiffReward(15.0)
    assert r.compute(_done_state([30, 0]), 0, True) == 1.0
    assert r.compute(_done_state([0, 30]), 0, True) == -1.0
    assert r.compute(_done_state([3, 0]), 0, False) == 0.0


def test_diff_reward_keeps_the_sign_of_the_sparse_reward():
    for pts in ([1, 0], [0, 4], [2, 2], [7, 3]):
        s = _done_state(pts)
        sign = SparseReward().compute(s, 0, True)
        diff = PointDiffReward(15.0).compute(s, 0, True)
        assert (sign > 0) == (diff > 0) and (sign < 0) == (diff < 0)
