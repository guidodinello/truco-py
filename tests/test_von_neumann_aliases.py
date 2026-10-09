"""Old VonNeumann strings are PERMANENT aliases of the omniscient agent (issue #50).

Logs 009-011 cite "von_neumann" / "vonneumann" and the old mode names. They must keep
resolving to the perfect-information agent and never to the fair one. The strings are
hardcoded on purpose: looping over a registry constant would let someone delete or
repoint an entry and keep the test green.
"""

import json
from pathlib import Path

import pytest

from agents.determinized_von_neumann_agent import DeterminizedVonNeumannAgent
from agents.von_neumann_agent import OmniscientVonNeumannAgent, VonNeumannAgent
from scripts import benchmark, league_010
from training.eval import validate_agent_name

OLD_MODE_LINEUPS = {
    "von_neumann_vs_random": ("von_neumann", "random"),
    "von_neumann_vs_threshold": ("von_neumann", "threshold"),
    "match_von_neumann_vs_random": ("von_neumann", "random"),
    "match_von_neumann_vs_threshold": ("von_neumann", "threshold"),
    "match_rl_vs_vonneumann": ("rl", "von_neumann"),
    "match_von_neumann_determinized_vs_von_neumann": ("von_neumann_determinized", "von_neumann"),
}
NEW_MODE_LINEUPS = {
    "von_neumann_omniscient_vs_random": ("von_neumann_omniscient", "random"),
    "von_neumann_omniscient_vs_threshold": ("von_neumann_omniscient", "threshold"),
    "match_von_neumann_omniscient_vs_random": ("von_neumann_omniscient", "random"),
    "match_von_neumann_omniscient_vs_threshold": ("von_neumann_omniscient", "threshold"),
    "match_rl_vs_von_neumann_omniscient": ("rl", "von_neumann_omniscient"),
    "match_von_neumann_determinized_vs_von_neumann_omniscient": (
        "von_neumann_determinized",
        "von_neumann_omniscient",
    ),
}


def _build(role: str, cache: Path | None = None) -> object:
    return benchmark._build_agent(role, 3, rollouts=2, cache_path=cache, rl_agent=None)


def test_class_alias_is_the_omniscient_class() -> None:
    assert VonNeumannAgent is OmniscientVonNeumannAgent
    assert OmniscientVonNeumannAgent.name == "von_neumann_omniscient"
    assert not issubclass(DeterminizedVonNeumannAgent, OmniscientVonNeumannAgent)


@pytest.mark.parametrize("role", ["von_neumann", "von_neumann_omniscient"])
def test_benchmark_roles_resolve_to_the_omniscient_agent(role: str) -> None:
    assert type(_build(role)) is OmniscientVonNeumannAgent


def test_benchmark_fair_role_is_not_omniscient() -> None:
    assert type(_build("von_neumann_determinized")) is DeterminizedVonNeumannAgent


@pytest.mark.parametrize("mode", sorted(OLD_MODE_LINEUPS))
def test_old_modes_keep_their_lineup_and_resolve_to_the_omniscient_agent(mode: str) -> None:
    lineup = benchmark.MODES[mode].lineup
    assert lineup == OLD_MODE_LINEUPS[mode]  # by_role keys read by scripts/analyze_009.py
    for role in lineup:
        if role in ("von_neumann", "von_neumann_omniscient"):
            assert type(_build(role)) is OmniscientVonNeumannAgent


@pytest.mark.parametrize("mode", sorted(NEW_MODE_LINEUPS))
def test_new_modes_use_the_omniscient_role(mode: str) -> None:
    assert benchmark.MODES[mode].lineup == NEW_MODE_LINEUPS[mode]
    assert "VonNeumann-Omniscient(r=20)" in benchmark._labels(mode, 20, None)


@pytest.mark.parametrize("name", ["vonneumann", "vonneumann_omniscient"])
def test_league_names_resolve_to_the_omniscient_agent(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(league_010, "VN_ROLLOUTS", 1)
    validate_agent_name(name)
    agents = league_010._triplet(name, (0, 2, 4), 7, {}, Path("."))
    assert [type(a) for a in agents] == [OmniscientVonNeumannAgent] * 3


def test_league_fair_name_is_not_omniscient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(league_010, "VN_ROLLOUTS", 1)
    agents = league_010._triplet("vonneumann_determinized", (0, 2, 4), 7, {}, Path("."))
    assert [type(a) for a in agents] == [DeterminizedVonNeumannAgent] * 3


@pytest.mark.parametrize("role", ["von_neumann", "von_neumann_omniscient"])
def test_old_flat_cache_still_loads_for_the_omniscient_agent(role: str, tmp_path: Path) -> None:
    path = tmp_path / "vn_cache.json"
    path.write_text(json.dumps({"some-key": 0.25}))
    agent = _build(role, path)
    assert isinstance(agent, OmniscientVonNeumannAgent)
    assert agent._cache == {"some-key": 0.25}


def test_fair_agent_still_refuses_the_old_cache(tmp_path: Path) -> None:
    path = tmp_path / "vn_cache.json"
    path.write_text(json.dumps({"some-key": 0.25}))
    with pytest.raises(ValueError):
        DeterminizedVonNeumannAgent(seed=1, n_rollouts=2, cache_path=path)
