"""
Experiment 010 league driver (docs/experiments/010-*.md): a seat-rotated round robin over the
exp 009 checkpoints, rated by ``gamekit.league`` (anchored Bradley-Terry/Elo, Threshold = 0).

    python -m scripts.league_010 run --name league --n 4000 --workers 3
    python -m scripts.league_010 summarize --name league

Truco reduction: ``num_seats=2`` *team slots* (slot 0 = Team A's 3 players, slot 1 = Team B's),
each filled with 3 copies of one agent -- exactly the ``scripts/benchmark.py`` arms. A pairing is
full matches. ``gamekit.league`` hands ``play`` an already-rotated lineup, so ``play`` must NOT
rotate again.

Parallelism: ``run_league`` plays pairings one after another, but a pairing's seeds and config
hash depend only on ``(seed, a, b, num_seats, n)``. So one ``run_league(agents=[a, b])`` per
pairing, in a process pool, writes the same files as a full-roster run. Every call also rewrites
``league.json`` (a race, ignored); ``summarize`` is the authoritative writer.

Reproducibility: Random/Threshold agents are rebuilt inside ``play`` for every pairing, seeded
from that pairing's driver seed, so a resumed or re-run pairing never depends on run order.
"""

import argparse
import hashlib
import itertools
import json
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gamekit.league import ScheduledGame, load_pairings, run_league, summarize_league
from gamekit.results import write_result

from agents.base import TrucoAgent
from agents.determinized_von_neumann_agent import DeterminizedVonNeumannAgent
from agents.random_agent import RandomAgent
from agents.rl_agent import RLAgent
from agents.threshold_agent import ThresholdAgent
from agents.von_neumann_agent import VonNeumannAgent
from engine.match import TrucoMatch
from log import get_logger
from training.eval import place_agents, run_match, sha256_file

logger = get_logger("league_010")

NUM_SEATS = 2  # team slots, not individual players
ANCHOR = "threshold"
ANCHOR_RATING = 0.0
PRIOR_DRAWS = 1.0
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 0
DEFAULT_SEED = 20261005
PROGRESS_EVERY = 100
ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "results" / "010" / "manifest.json"
RESULTS_DIR = ROOT / "results" / "010"
_SLOT_OFFSETS = ((0, 2, 4), (1, 3, 5))  # role a keeps Team A's RNG offsets, role b Team B's

BASELINES = ("threshold", "random")
VON_NEUMANN = "vonneumann"  # exp 011 only: not in the exp 010 roster; PERFECT information
VON_NEUMANN_DET = "vonneumann_determinized"  # the fair (determinized) variant
VN_ROLLOUTS = 20  # as in exp 009 (benchmark.py default)


@dataclass(slots=True)
class LeagueConfig:
    name: str
    n: int
    seed: int
    workers: int
    ckpt_root: Path
    results_dir: Path
    pairs: tuple[str, ...] = ()
    baselines: tuple[str, ...] = BASELINES
    manifest: Path | None = None  # default: MANIFEST


def load_manifest(path: Path | None = None) -> dict[str, dict[str, Any]]:
    agents: dict[str, dict[str, Any]] = json.loads((path or MANIFEST).read_text())["agents"]
    return agents


def roster_names(
    manifest: dict[str, dict[str, Any]], baselines: Sequence[str] = BASELINES
) -> list[str]:
    return sorted([*manifest, *baselines])


def verify_manifest(manifest: dict[str, dict[str, Any]], ckpt_root: Path) -> None:
    """Refuse to play unless every checkpoint exists and matches its recorded sha256."""
    for name, entry in sorted(manifest.items()):
        path = ckpt_root / entry["path"]
        if not path.is_file():
            raise FileNotFoundError(f"{name}: checkpoint missing at {path}")
        got = sha256_file(path)
        if got != entry["sha256"]:
            raise ValueError(f"{name}: sha256 {got[:12]} != manifest {entry['sha256'][:12]}")
    logger.info("manifest verified: %d checkpoints", len(manifest))


_RL_CACHE: dict[Path, RLAgent] = {}


def _rl_agent(path: Path) -> RLAgent:
    if path not in _RL_CACHE:
        _RL_CACHE[path] = RLAgent(path, deterministic=True)
    return _RL_CACHE[path]


def _triplet(
    name: str,
    offsets: tuple[int, int, int],
    seed: int,
    manifest: dict[str, dict[str, Any]],
    ckpt_root: Path,
) -> list[TrucoAgent]:
    if name == "threshold":
        return [ThresholdAgent(seed=seed + o) for o in offsets]
    if name == "random":
        return [RandomAgent(seed=seed + o) for o in offsets]
    if name == VON_NEUMANN:
        # In-memory EV cache only (cache_path=None), built per pairing: no state leaks across
        # pairings or runs, so a re-run pairing is reproducible.
        return [VonNeumannAgent(n_rollouts=VN_ROLLOUTS, seed=seed + o) for o in offsets]
    if name == VON_NEUMANN_DET:
        return [DeterminizedVonNeumannAgent(n_rollouts=VN_ROLLOUTS, seed=seed + o) for o in offsets]
    rl = _rl_agent(ckpt_root / manifest[name]["path"])
    return [rl, rl, rl]


def winners_sha256(winners: Sequence[int | None]) -> str:
    return hashlib.sha256(json.dumps(list(winners)).encode()).hexdigest()


def make_play(manifest: dict[str, dict[str, Any]], ckpt_root: Path):
    """The ``play`` callable for ``run_league``: one pairing's games -> winning team slot."""

    def play(games: Sequence[ScheduledGame]) -> Sequence[int | None]:
        a, b = sorted(set(games[0].lineup))
        seed = games[0].driver_seed
        role_agents = {
            name: _triplet(name, offsets, seed, manifest, ckpt_root)
            for name, offsets in zip((a, b), _SLOT_OFFSETS, strict=True)
        }
        match = TrucoMatch()
        winners: list[int | None] = []
        t0 = time.perf_counter()
        for i, game in enumerate(games, 1):
            # game.lineup is already rotated by gamekit.league: place it as-is.
            agents = place_agents(game.lineup, role_agents)
            result = run_match(match, agents, seed=game.engine_seed)
            winners.append(None if result == -1 else result)
            if i % PROGRESS_EVERY == 0 or i == len(games):
                wins_a = sum(
                    1
                    for w, g in zip(winners, games, strict=False)
                    if w is not None and g.lineup[w] == a
                )
                logger.info(
                    "%s__vs__%s %d/%d  %s wins %.1f%%  %.2f matches/s",
                    a,
                    b,
                    i,
                    len(games),
                    a,
                    100 * wins_a / i,
                    i / (time.perf_counter() - t0),
                )
        logger.info("%s__vs__%s winners_sha256=%s", a, b, winners_sha256(winners))
        return winners

    return play


def _worker_init() -> None:
    import torch

    torch.set_num_threads(1)


def play_pairing(task: tuple[str, str, LeagueConfig]) -> str:
    a, b, cfg = task
    manifest = load_manifest(cfg.manifest)
    run_league(
        agents=[a, b],
        num_seats=NUM_SEATS,
        n_per_pairing=cfg.n,
        seed=cfg.seed,
        play=make_play(manifest, cfg.ckpt_root),
        winning_seat=lambda r: r,
        results_dir=cfg.results_dir,
        name=cfg.name,
        anchor=a,  # run_league insists the anchor is in the roster; not part of the config hash
        n_bootstrap=10,
    )
    return f"{a}__vs__{b}"


def pending_pairings(
    cfg: LeagueConfig, manifest: dict[str, dict[str, Any]]
) -> list[tuple[str, str]]:
    """Unfinished pairings, RL-vs-RL first (the slowest), so the tail of the run is short."""
    league_dir = cfg.results_dir / cfg.name
    pairs = list(itertools.combinations(roster_names(manifest, cfg.baselines), 2))
    if cfg.pairs:
        wanted = set(cfg.pairs)
        pairs = [p for p in pairs if f"{p[0]}__vs__{p[1]}" in wanted]
    pairs = [p for p in pairs if not (league_dir / f"{p[0]}__vs__{p[1]}.json").exists()]
    return sorted(pairs, key=lambda p: -sum(x not in cfg.baselines for x in p))


def run(cfg: LeagueConfig) -> None:
    if cfg.n % NUM_SEATS or cfg.n < NUM_SEATS:
        raise ValueError(f"--n must be a positive even number, got {cfg.n}")
    manifest = load_manifest(cfg.manifest)
    verify_manifest(manifest, cfg.ckpt_root)
    todo = pending_pairings(cfg, manifest)
    logger.info(
        "league %s: %d pairings to play (n=%d, seed=%d, workers=%d)",
        cfg.name,
        len(todo),
        cfg.n,
        cfg.seed,
        cfg.workers,
    )
    with ProcessPoolExecutor(cfg.workers, initializer=_worker_init) as pool:
        for done in pool.map(play_pairing, [(a, b, cfg) for a, b in todo]):
            logger.info("finished %s", done)
    logger.info("league %s: all pairings done", cfg.name)


def summarize(results_dir: Path, name: str) -> dict[str, Any]:
    league_dir = results_dir / name
    summary = summarize_league(
        load_pairings(league_dir),
        anchor=ANCHOR,
        anchor_rating=ANCHOR_RATING,
        prior_draws=PRIOR_DRAWS,
        n_bootstrap=N_BOOTSTRAP,
        bootstrap_seed=BOOTSTRAP_SEED,
    )
    write_result(league_dir, "league", summary)
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    print(f"{'agent':<12}{'Elo':>9}   95% CI")
    for agent, r in summary["ratings"].items():
        lo, hi = r["elo_ci"]
        print(f"{agent:<12}{r['elo']:>9.1f}   [{lo:.1f}, {hi:.1f}]")
    print("\nwin matrix (row beats column, decisive matches, Wilson 95%):")
    for pair, e in sorted(summary["matrix"].items()):
        lo, hi = e["win_rate_wilson_ci"]
        rate, n = 100 * e["win_rate"], e["n_decisive"]
        print(f"  {pair:<28} {rate:5.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]  n={n}")
    print(f"\nties per pairing: {summary['ties']}")
    print(f"significant 3-cycles: {summary['cycles'] or 'none'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exp 010 truco league")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ("run", "summarize"):
        p = sub.add_parser(cmd)
        p.add_argument("--name", default="league")
        p.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
        if cmd == "run":
            p.add_argument("--n", type=int, required=True, help="matches per pairing (even)")
            p.add_argument("--seed", type=int, default=DEFAULT_SEED)
            p.add_argument("--workers", type=int, default=3)
            p.add_argument("--ckpt-root", type=Path, default=ROOT)
            p.add_argument("--pairs", default="", help="comma list of a__vs__b to restrict to")
            p.add_argument(
                "--baselines",
                default=",".join(BASELINES),
                help=(
                    "comma list of non-checkpoint agents "
                    "(threshold, random, vonneumann, vonneumann_determinized)"
                ),
            )
            p.add_argument(
                "--manifest", type=Path, default=None, help="default: results/010/manifest.json"
            )
    args = parser.parse_args()
    if args.cmd == "run":
        run(
            LeagueConfig(
                name=args.name,
                n=args.n,
                seed=args.seed,
                workers=args.workers,
                ckpt_root=args.ckpt_root,
                results_dir=args.results_dir,
                pairs=tuple(s for s in args.pairs.split(",") if s),
                baselines=tuple(s for s in args.baselines.split(",") if s),
                manifest=args.manifest,
            )
        )
    else:
        print_summary(summarize(args.results_dir, args.name))


if __name__ == "__main__":
    main()
