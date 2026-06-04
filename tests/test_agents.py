"""Tests verifying that agents always return a legal action."""

import pytest

from agents.base import Agent
from agents.random_agent import RandomAgent
from agents.threshold_agent import ThresholdAgent
from agents.von_neumann_agent import VonNeumannAgent
from engine.game import TrucoGame
from engine.phases import Phase


@pytest.fixture
def game() -> TrucoGame:
    return TrucoGame()


@pytest.mark.parametrize(
    "agent_cls,kwargs",
    [
        (RandomAgent, {"seed": 0}),
        (ThresholdAgent, {"seed": 0}),
        (VonNeumannAgent, {"seed": 0, "n_rollouts": 2}),
    ],
)
def test_agent_satisfies_protocol(agent_cls, kwargs):
    agent = agent_cls(**kwargs)
    assert isinstance(agent, Agent)


@pytest.mark.parametrize(
    "agent_cls,kwargs",
    [
        (RandomAgent, {"seed": 1}),
        (ThresholdAgent, {"seed": 1}),
        (VonNeumannAgent, {"seed": 1, "n_rollouts": 2}),
    ],
)
def test_agent_always_returns_legal_action(agent_cls, kwargs, game: TrucoGame):
    """Agent must return an action that is in the legal actions list."""
    agent = agent_cls(**kwargs)
    state = game.reset(seed=42)
    steps = 0
    while state.phase != Phase.DONE and steps < 200:
        cp = state.current_player
        legal = game.legal_actions(state)
        action = agent.choose_action(state, legal, cp)
        assert action in legal, (
            f"{agent_cls.__name__} returned illegal action {action} "
            f"(legal: {[a.name for a in legal]})"
        )
        game.apply_action(state, action)
        steps += 1


@pytest.mark.parametrize(
    "agent_cls,kwargs",
    [
        (RandomAgent, {"seed": 2}),
        (ThresholdAgent, {"seed": 2}),
        (VonNeumannAgent, {"seed": 2, "n_rollouts": 2}),
    ],
)
def test_agent_reset_does_not_raise(agent_cls, kwargs):
    agent = agent_cls(**kwargs)
    agent.reset()  # must not raise
