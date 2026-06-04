"""Tests for the TrucoGame engine."""

import pytest

from engine.game import TrucoGame
from engine.game_state import GameState
from engine.phases import Phase


@pytest.fixture
def game() -> TrucoGame:
    return TrucoGame()


def test_reset_returns_game_state(game: TrucoGame):
    state = game.reset(seed=0)
    assert isinstance(state, GameState)


def test_reset_phase_not_done(game: TrucoGame):
    state = game.reset(seed=0)
    assert state.phase != Phase.DONE


def test_reset_deals_three_cards_per_player(game: TrucoGame):
    state = game.reset(seed=0)
    for i in range(6):
        assert len(state.manos[i]) == 3
        assert len(state.cards_in_hand[i]) == 3


def test_reset_scores_zero(game: TrucoGame):
    state = game.reset(seed=0)
    assert state.scores == [0, 0]
    assert state.hand_pts == [0, 0]


def test_reset_muestra_is_valid_card(game: TrucoGame):
    state = game.reset(seed=0)
    palo, numero = state.muestra
    assert 0 <= palo <= 3
    assert numero in [1, 2, 3, 4, 5, 6, 7, 10, 11, 12]


def test_legal_actions_never_empty_before_done(game: TrucoGame):
    """legal_actions() must always return at least one action in non-terminal states."""
    state = game.reset(seed=42)
    steps = 0
    while state.phase != Phase.DONE and steps < 500:
        legal = game.legal_actions(state)
        assert len(legal) > 0, f"Empty legal actions at phase={state.phase}"
        game.apply_action(state, legal[0])
        steps += 1


def test_full_game_completes(game: TrucoGame):
    """A full hand must reach Phase.DONE within a reasonable step budget."""
    state = game.reset(seed=7)
    steps = 0
    while state.phase != Phase.DONE and steps < 200:
        legal = game.legal_actions(state)
        game.apply_action(state, legal[0])
        steps += 1
    assert state.phase == Phase.DONE, f"Game did not complete in {steps} steps"


def test_hand_pts_nonnegative(game: TrucoGame):
    state = game.reset(seed=99)
    while state.phase != Phase.DONE:
        legal = game.legal_actions(state)
        game.apply_action(state, legal[0])
    assert state.hand_pts[0] >= 0
    assert state.hand_pts[1] >= 0


def test_reset_with_scores(game: TrucoGame):
    state = game.reset(seed=1, scores=[10, 20])
    assert state.scores == [10, 20]


def test_multiple_seeds_differ(game: TrucoGame):
    s1 = game.reset(seed=0)
    s2 = game.reset(seed=1)
    # Different seeds should produce different deals (with very high probability)
    assert s1.manos != s2.manos or s1.muestra != s2.muestra
