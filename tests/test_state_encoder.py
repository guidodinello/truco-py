"""Tests for the RL observation encoder."""

import numpy as np
import pytest

from engine.game import TrucoGame
from engine.phases import Phase
from training.state_encoder import OBS_DIM, obs_to_vector


@pytest.fixture
def game_state():
    game = TrucoGame()
    return game, game.reset(seed=0)


def test_obs_shape(game_state):
    game, state = game_state
    for player in range(6):
        obs = obs_to_vector(state, player)
        assert obs.shape == (OBS_DIM,), f"Wrong shape for player {player}: {obs.shape}"


def test_obs_dtype(game_state):
    game, state = game_state
    obs = obs_to_vector(state, 0)
    assert obs.dtype == np.float32


def test_obs_bounds(game_state):
    """All values must lie in [0, 1]."""
    game, state = game_state
    for player in range(6):
        obs = obs_to_vector(state, player)
        assert obs.min() >= 0.0, f"Negative value for player {player}: {obs.min()}"
        assert obs.max() <= 1.0, f"Value > 1 for player {player}: {obs.max()}"


def test_obs_own_cards_set(game_state):
    """Own card slots [0:40] must have exactly 3 ones for each player."""
    game, state = game_state
    for player in range(6):
        obs = obs_to_vector(state, player)
        own_card_bits = obs[:40]
        assert int(own_card_bits.sum()) == 3, (
            f"Player {player} should have 3 own cards set, got {own_card_bits.sum()}"
        )


def test_obs_player_position_onehot(game_state):
    """Player position one-hot [157:163] must have exactly one 1."""
    game, state = game_state
    for player in range(6):
        obs = obs_to_vector(state, player)
        position_bits = obs[157:163]
        assert position_bits.sum() == 1.0
        assert position_bits[player] == 1.0


def test_obs_team_membership(game_state):
    """Team membership [163:169]: my team members should be 1, opponents 0."""
    game, state = game_state
    from engine.game_state import team_of

    for player in range(6):
        obs = obs_to_vector(state, player)
        team_bits = obs[163:169]
        my_team = team_of(player)
        for i in range(6):
            expected = 1.0 if team_of(i) == my_team else 0.0
            assert team_bits[i] == expected, f"Team bit wrong for player={player}, seat={i}"


def test_obs_stable_across_phases():
    """Encoder must not raise for any phase reached during normal play."""
    game = TrucoGame()
    state = game.reset(seed=42)
    steps = 0
    while state.phase != Phase.DONE and steps < 200:
        for player in range(6):
            obs = obs_to_vector(state, player)
            assert obs.shape == (OBS_DIM,)
            assert obs.min() >= 0.0 and obs.max() <= 1.0
        legal = game.legal_actions(state)
        game.apply_action(state, legal[0])
        steps += 1
