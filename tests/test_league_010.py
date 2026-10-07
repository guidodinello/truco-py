"""Wiring tests for scripts/league_010.py (exp 010): Random/Threshold only, no checkpoints."""

import json
from pathlib import Path

import pytest
from gamekit.league import ScheduledGame, load_pairings

from agents.random_agent import RandomAgent
from agents.threshold_agent import ThresholdAgent
from agents.von_neumann_agent import VonNeumannAgent
from scripts import league_010
from training.eval import sha256_file, validate_agent_name


@pytest.fixture
def baseline_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty checkpoint manifest, so the roster is just random + threshold."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"agents": {}}))
    monkeypatch.setattr(league_010, "MANIFEST", manifest)
    return tmp_path


def _games(lineup: tuple[str, ...], n: int = 4) -> list[ScheduledGame]:
    return [ScheduledGame(engine_seed=100 + i, driver_seed=7, lineup=lineup) for i in range(n)]


def test_play_places_the_already_rotated_lineup_without_rotating_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[type, type]] = []

    def fake_run_match(match, agents, seed=None):  # noqa: ANN001
        # Team A = players 0/2/4, Team B = players 1/3/5
        assert {type(a) for a in agents[0::2]} == {type(agents[0])}
        assert {type(a) for a in agents[1::2]} == {type(agents[1])}
        seen.append((type(agents[0]), type(agents[1])))
        return 0

    monkeypatch.setattr(league_010, "run_match", fake_run_match)
    play = league_010.make_play({}, Path("."))
    play(_games(("random", "threshold"), 1))
    play(_games(("threshold", "random"), 1))
    assert seen == [(RandomAgent, ThresholdAgent), (ThresholdAgent, RandomAgent)]


def test_play_is_deterministic_and_maps_slots_to_winners() -> None:
    games = _games(("random", "threshold"), 6)
    play = league_010.make_play({}, Path("."))
    first = play(games)
    assert first == play(games)
    assert all(w in (0, 1) for w in first)


def test_pending_pairings_skip_finished_files(baseline_only: Path) -> None:
    cfg = league_010.LeagueConfig("t", 4, 1, 1, baseline_only, baseline_only)
    manifest = league_010.load_manifest()
    assert league_010.pending_pairings(cfg, manifest) == [("random", "threshold")]
    (baseline_only / "t").mkdir()
    (baseline_only / "t" / "random__vs__threshold.json").write_text("{}")
    assert league_010.pending_pairings(cfg, manifest) == []


def test_pairing_then_summarize_anchors_threshold_at_zero(baseline_only: Path) -> None:
    cfg = league_010.LeagueConfig("t", 4, 1, 1, baseline_only, baseline_only)
    assert league_010.play_pairing(("random", "threshold", cfg)) == "random__vs__threshold"
    [pairing] = load_pairings(baseline_only / "t")
    assert pairing["league_config"]["n_games"] == 4
    summary = league_010.summarize(baseline_only, "t")
    assert summary["ratings"]["threshold"]["elo"] == 0.0
    assert (baseline_only / "t" / "league.json").exists()


def test_odd_n_is_refused(baseline_only: Path) -> None:
    cfg = league_010.LeagueConfig("t", 5, 1, 1, baseline_only, baseline_only)
    with pytest.raises(ValueError, match="even"):
        league_010.run(cfg)


def test_verify_manifest_refuses_tampered_or_missing(tmp_path: Path) -> None:
    ckpt = tmp_path / "a.zip"
    ckpt.write_bytes(b"weights")
    entry = {"path": "a.zip", "sha256": sha256_file(ckpt)}
    league_010.verify_manifest({"a": entry}, tmp_path)
    ckpt.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="sha256"):
        league_010.verify_manifest({"a": entry}, tmp_path)
    with pytest.raises(FileNotFoundError):
        league_010.verify_manifest({"a": {**entry, "path": "gone.zip"}}, tmp_path)


def test_committed_manifest_is_well_formed() -> None:
    manifest = league_010.load_manifest()
    assert sorted(manifest) == ["C10", "C20", "C5", "M10", "M20", "M5", "bc_init"]
    for name, entry in manifest.items():
        validate_agent_name(name)
        assert len(entry["sha256"]) == 64
    assert len(league_010.roster_names(manifest)) == 9


@pytest.fixture
def cheap_vn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(league_010, "VN_ROLLOUTS", 1)


def test_von_neumann_pairing_is_deterministic(cheap_vn: None) -> None:
    games = _games(("random", "vonneumann"), 2)
    play = league_010.make_play({}, Path("."))
    first = play(games)
    assert first == play(games)
    assert all(w in (0, 1) for w in first)


def test_von_neumann_is_built_per_pairing_with_no_disk_cache(cheap_vn: None) -> None:
    agents = league_010._triplet("vonneumann", (0, 2, 4), 7, {}, Path("."))
    assert [type(a).__name__ for a in agents] == ["VonNeumannAgent"] * 3
    for a in agents:
        assert isinstance(a, VonNeumannAgent)
        assert a._cfg.cache_path is None and a._cfg.n_rollouts == 1


def test_added_pairings_join_existing_files_with_mixed_n(
    baseline_only: Path, cheap_vn: None
) -> None:
    """Exp 011: finished 010-style files are skipped; new pairings are rated together with them."""
    old = league_010.LeagueConfig("t", 4, 1, 1, baseline_only, baseline_only)
    league_010.play_pairing(("random", "threshold", old))
    new = league_010.LeagueConfig(
        "t", 2, 1, 1, baseline_only, baseline_only, baselines=(*league_010.BASELINES, "vonneumann")
    )
    manifest = league_010.load_manifest()
    assert league_010.pending_pairings(new, manifest) == [
        ("random", "vonneumann"),
        ("threshold", "vonneumann"),
    ]
    for a, b in league_010.pending_pairings(new, manifest):
        league_010.play_pairing((a, b, new))
    assert league_010.pending_pairings(new, manifest) == []
    summary = league_010.summarize(baseline_only, "t")
    assert set(summary["ratings"]) == {"random", "threshold", "vonneumann"}
    assert summary["ratings"]["threshold"]["elo"] == 0.0
