"""ThresholdRolloutVonNeumannAgent (#42): fair, Threshold rollouts, its own cache namespace."""

import json
from pathlib import Path

import pytest

from agents.determinized_von_neumann_agent import (
    CACHE_FORMAT as FAIR_CACHE_FORMAT,
)
from agents.determinized_von_neumann_agent import (
    DeterminizedVonNeumannAgent,
    _fair_state_key,
)
from agents.threshold_agent import ThresholdAgent
from agents.threshold_rollout_von_neumann_agent import (
    CACHE_FORMAT,
    ThresholdRolloutVonNeumannAgent,
)
from engine.game import TrucoGame
from engine.game_state import GameState
from scripts import benchmark
from tests.test_determinized_von_neumann import STRONG, WEAK, _decide, _world


@pytest.fixture
def world_a() -> GameState:
    return _world(STRONG)


@pytest.fixture
def world_b() -> GameState:
    return _world(WEAK)


def test_decision_does_not_depend_on_hidden_hands(world_a: GameState, world_b: GameState) -> None:
    """Same view from seat 0, different hidden hands -> same action and same EVs."""
    assert _decide(ThresholdRolloutVonNeumannAgent, world_a) == _decide(
        ThresholdRolloutVonNeumannAgent, world_b
    )


def test_rollouts_are_played_by_threshold(
    world_a: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    real = ThresholdAgent.choose_action

    def spy(self, state, legal, player_idx):
        calls.append(player_idx)
        return real(self, state, legal, player_idx)

    monkeypatch.setattr(ThresholdAgent, "choose_action", spy)
    agent = ThresholdRolloutVonNeumannAgent(seed=1, n_rollouts=2)
    agent.choose_action(world_a, TrucoGame().legal_actions(world_a), 0)
    assert calls  # rollouts used Threshold...
    assert len(set(calls)) > 1  # ...for more than the acting seat


def test_rollout_reward_is_for_the_acting_seat(world_a: GameState) -> None:
    agent = ThresholdRolloutVonNeumannAgent(seed=1, n_rollouts=1)
    reward = agent._run_rollout(world_a, 0)
    assert -1.0 <= reward <= 1.0


def test_cache_namespace_is_separate(world_a: GameState, tmp_path: Path) -> None:
    action = TrucoGame().legal_actions(world_a)[0]
    assert CACHE_FORMAT != FAIR_CACHE_FORMAT
    assert json.loads(_fair_state_key(world_a, 0, action))[0] == FAIR_CACHE_FORMAT  # unchanged
    path = tmp_path / "ev.json"
    fair = DeterminizedVonNeumannAgent(seed=1, n_rollouts=2, cache_path=path)
    fair._estimate_ev(world_a, action, 0)
    fair.save_cache()
    with pytest.raises(ValueError, match="must not be reused"):
        ThresholdRolloutVonNeumannAgent(seed=1, n_rollouts=2, cache_path=path)
    tr_path = tmp_path / "tr.json"
    tr = ThresholdRolloutVonNeumannAgent(seed=1, n_rollouts=2, cache_path=tr_path)
    tr._estimate_ev(world_a, action, 0)
    tr.save_cache()
    with pytest.raises(ValueError, match="must not be reused"):
        DeterminizedVonNeumannAgent(seed=1, n_rollouts=2, cache_path=tr_path)
    (key,) = tr._cache
    assert json.loads(key)[0] == CACHE_FORMAT


def test_variant_cache_paths_differ(tmp_path: Path) -> None:
    base = tmp_path / "ev.json"
    paths = {
        benchmark._variant_cache_path(base, "determinized"),
        benchmark._variant_cache_path(base, "determinized_threshold"),
    }
    assert len(paths) == 2


def test_every_mode_has_a_label() -> None:
    for mode in benchmark.MODES:
        assert len(benchmark._labels(mode, 20, "x.zip")) == 2


@pytest.mark.parametrize("mode", sorted(m for m in benchmark.MODES if "threshold_rollout" in m))
def test_threshold_rollout_modes_run(mode: str, tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    benchmark.benchmark(mode, 2, seed=1, rollouts=2, out=out)
    assert out.exists()
