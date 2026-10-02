"""TeamOpponentPool: team-consistent sampling, run scoping, loud failures (exp 009 D1/D2)."""

import math
from collections import Counter
from pathlib import Path

import pytest

from agents.random_agent import RandomAgent
from agents.threshold_agent import ThresholdAgent
from engine.game_state import team_of
from tests.helpers import save_old_checkpoint
from training.config import (
    ROLE_RANDOM,
    ROLE_SELF,
    ROLE_THRESHOLD,
    OpponentMix,
    snapshot_name,
)
from training.pool import TeamOpponentPool
from training.self_play import _CheckpointAgent

RUN_ID = "run_a"


class _Snap:
    """Stands in for a snapshot agent: remembers which file it was loaded from."""

    def __init__(self, path: Path) -> None:
        self.path = path


def _pool(tmp_path: Path, steps=(0, 1_000_000, 2_000_000), **kw) -> TeamOpponentPool:
    d = tmp_path / RUN_ID
    d.mkdir(parents=True, exist_ok=True)
    for s in steps:
        (d / snapshot_name(s)).touch()
    kw.setdefault("mix", OpponentMix())
    kw.setdefault("partners", "snapshot")
    return TeamOpponentPool(tmp_path, run_id=RUN_ID, load_opponent=_Snap, seed=7, **kw)  # type: ignore[arg-type]


def _kind(agent) -> str:
    if isinstance(agent, ThresholdAgent):
        return "threshold"
    if isinstance(agent, RandomAgent):
        return "random"
    return str(agent.path.name)


def test_opponent_team_is_one_role_and_partners_are_the_latest_snapshot(tmp_path):
    pool = _pool(tmp_path)
    latest = snapshot_name(2_000_000)
    for episode in range(300):
        learner = episode % 6
        agents = pool.seat_agents(6, learner)
        assert agents[learner] is None
        opp = {_kind(a) for s, a in enumerate(agents) if a and team_of(s) != team_of(learner)}
        partners = [a for s, a in enumerate(agents) if a and team_of(s) == team_of(learner)]
        assert len(opp) == 1, "all 3 opponent seats share ONE role (and one snapshot)"
        assert len(partners) == 2 and all(_kind(p) == latest for p in partners)


def test_opponent_role_frequencies_match_the_mix(tmp_path):
    pool = _pool(tmp_path)
    n = 6000
    roles = Counter()
    for i in range(n):
        pool.seat_agents(6, i % 6)
        roles[pool.last_opp_role] += 1
    for role, p in ((ROLE_THRESHOLD, 0.4), (ROLE_RANDOM, 0.2), (ROLE_SELF, 0.4)):
        assert abs(roles[role] / n - p) < 4 * math.sqrt(p * (1 - p) / n)


def test_snapshot_role_is_uniform_over_the_pool(tmp_path):
    pool = _pool(tmp_path, mix=OpponentMix(0.0, 0.0, 1.0))
    seen = Counter()
    for _ in range(900):
        agents = pool.seat_agents(6, 0)
        seen[_kind(agents[1])] += 1  # seat 1 is an opponent of the learner at seat 0
    assert set(seen) == {snapshot_name(s) for s in (0, 1_000_000, 2_000_000)}
    assert min(seen.values()) > 250


def test_pool_is_scoped_to_its_run_id(tmp_path):
    pool = _pool(tmp_path, steps=(0,), mix=OpponentMix(0.0, 0.0, 1.0))
    # stale / foreign checkpoints: a sibling run and a flat file in the pool root
    (tmp_path / "other_run").mkdir()
    (tmp_path / "other_run" / snapshot_name(9_000_000)).touch()
    (tmp_path / snapshot_name(8_000_000)).touch()
    assert [p.name for p in pool.checkpoints()] == [snapshot_name(0)]
    for _ in range(50):
        for a in pool.seat_agents(6, 0):
            assert a is None or _kind(a) == snapshot_name(0)


def test_empty_pool_is_an_error_not_a_silent_fallback(tmp_path):
    pool = _pool(tmp_path, steps=())
    with pytest.raises(RuntimeError, match="no snapshots"):
        for i in range(50):  # partners="snapshot" always needs one
            pool.seat_agents(6, i % 6)


def test_threshold_partners_need_no_snapshots(tmp_path):
    pool = _pool(tmp_path, steps=(), mix=OpponentMix(0.5, 0.5, 0.0), partners="threshold")
    agents = pool.seat_agents(6, 2)
    assert all(isinstance(a, ThresholdAgent) for s, a in enumerate(agents) if a and s % 2 == 0)


def test_a_pre_26_checkpoint_is_refused_when_loaded(tmp_path):
    old = save_old_checkpoint(tmp_path / "old.zip")
    with pytest.raises(ValueError, match="53 actions"):
        _CheckpointAgent(str(old))._load()
