"""
Benchmark: play N games between two agent configurations and report win rates.

Usage:
    # Random vs Random (sanity check, should be ~50/50)
    uv run scripts/benchmark.py --mode random --n 1000

    # Threshold agent vs Random (should win 60-70%)
    uv run scripts/benchmark.py --mode threshold_vs_random --n 1000

    # Threshold vs Threshold (should be ~50/50)
    uv run scripts/benchmark.py --mode threshold_vs_threshold --n 1000

    # Von Neumann vs Random (should win >70%)
    uv run scripts/benchmark.py --mode von_neumann_vs_random --n 200 --rollouts 20

    # Von Neumann vs Threshold
    uv run scripts/benchmark.py --mode von_neumann_vs_threshold --n 100 --rollouts 20

    # Profile game speed
    uv run scripts/benchmark.py --mode random --n 10000 --profile

Modes are 2-role team arms driven by ``gamekit.benchmark.run_arm``: a gamekit
"seat" here is a *team slot* (0 = Team A's three players, 1 = Team B's), not
an individual player -- ``--n`` must therefore be even, since ``run_arm``
requires ``n_games`` be a multiple of the (2-role) lineup length. Seat
rotation is mandatory (gamekit's contract): across an arm, each role plays
Team A in half the games and Team B in the other half, removing the mano
(first-player) advantage that always favoured Team A. See
``~/projects/docs/shared-ml-package.md`` for the full design.
"""

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from gamekit.benchmark import run_arm
from gamekit.seats import rotate

from agents.base import TrucoAgent
from agents.random_agent import RandomAgent
from agents.rl_agent import RLAgent
from agents.threshold_agent import ThresholdAgent
from agents.von_neumann_agent import VonNeumannAgent
from engine.game import TrucoGame
from engine.game_state import TEAM_A, TEAM_B
from engine.phases import Phase
from log import get_logger

# Flush stdout after each line so progress appears immediately when piped or captured.
sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]

logger = get_logger("benchmark")

# One role occupies each gamekit "seat" (team slot); slot 0 = Team A, slot 1 = Team B.
_SLOT_PLAYERS = (TEAM_A, TEAM_B)


@dataclass(frozen=True, slots=True)
class Mode:
    """A benchmark arm: a 2-role lineup (one role per team slot) plus whether
    it plays single hands (``run_game``) or full matches (``run_match``)."""

    lineup: tuple[str, str]
    is_match: bool


MODES: dict[str, Mode] = {
    "random": Mode(("random_a", "random_b"), False),
    "threshold_vs_random": Mode(("threshold", "random"), False),
    "threshold_vs_threshold": Mode(("threshold_a", "threshold_b"), False),
    "von_neumann_vs_random": Mode(("von_neumann", "random"), False),
    "von_neumann_vs_threshold": Mode(("von_neumann", "threshold"), False),
    "match_von_neumann_vs_random": Mode(("von_neumann", "random"), True),
    "match_von_neumann_vs_threshold": Mode(("von_neumann", "threshold"), True),
    "match_threshold_vs_random": Mode(("threshold", "random"), True),
    "match_rl_vs_random": Mode(("rl", "random"), True),
    "match_rl_vs_threshold": Mode(("rl", "threshold"), True),
    "match_rl_vs_vonneumann": Mode(("rl", "von_neumann"), True),
}


def run_game(game: TrucoGame, agents: list, seed: int | None = None) -> int:
    """
    Play one complete hand.

    Returns:
        0 if team A wins, 1 if team B wins, -1 if tied.
    """
    state = game.reset(seed=seed)

    while state.phase != Phase.DONE:
        cp = state.current_player
        legal = game.legal_actions(state)
        if not legal:
            break
        action = agents[cp].choose_action(state, legal, cp)
        game.apply_action(state, action)

    if state.hand_pts[0] > state.hand_pts[1]:
        return 0
    if state.hand_pts[1] > state.hand_pts[0]:
        return 1
    return -1


def run_match(game: TrucoGame, agents: list, seed: int | None = None) -> int:
    """
    Play a full match (multiple hands) until one team reaches game.target points.

    Returns:
        0 if team A wins, 1 if team B wins.
    """
    scores = [0, 0]
    hand = 0
    rng_seed = seed
    while scores[0] < game.target and scores[1] < game.target:
        state = game.reset(seed=rng_seed, scores=scores)
        rng_seed = (rng_seed + 1) if rng_seed is not None else None
        while state.phase != Phase.DONE:
            cp = state.current_player
            legal = game.legal_actions(state)
            if not legal:
                break
            action = agents[cp].choose_action(state, legal, cp)
            game.apply_action(state, action)
        scores = list(state.scores)
        hand += 1
        if hand > 200:  # safety valve against infinite loops
            break
    return 0 if scores[0] >= game.target else 1


def _build_agent(
    role: str,
    seed: int,
    *,
    rollouts: int,
    cache_path: Path | None,
    rl_agent: RLAgent | None,
) -> TrucoAgent:
    if role in ("random", "random_a", "random_b"):
        return RandomAgent(seed=seed)
    if role in ("threshold", "threshold_a", "threshold_b"):
        return ThresholdAgent(seed=seed)
    if role == "von_neumann":
        return VonNeumannAgent(n_rollouts=rollouts, seed=seed, cache_path=cache_path)
    if role == "rl":
        assert rl_agent is not None
        return rl_agent
    raise ValueError(f"unknown role {role!r}")


def _build_role_agents(
    role: str,
    seed_offsets: tuple[int, int, int],
    seed: int,
    *,
    rollouts: int,
    cache_path: Path | None,
    rl_agent: RLAgent | None,
) -> list[TrucoAgent]:
    """The 3 agent instances for one role, one per team-position -- built once
    and reused for every game, keeping RNG streams and VonNeumann caches
    stable across the whole arm, exactly as when they lived in a fixed team."""
    return [
        _build_agent(role, seed + off, rollouts=rollouts, cache_path=cache_path, rl_agent=rl_agent)
        for off in seed_offsets
    ]


def _build_agents(
    mode_def: Mode,
    seed: int,
    *,
    rollouts: int,
    cache_path: Path | None,
    checkpoint: str | None,
) -> dict[str, list[TrucoAgent]]:
    """Build one agent triplet per role, keyed by role name. ``role_a`` keeps
    the RNG seeds Team A always used (``seed+0,2,4``), ``role_b`` keeps Team
    B's (``seed+1,3,5``) -- seat rotation only changes which team slot a role
    plays in a given game, never its identity or seed."""
    role_a, role_b = mode_def.lineup
    rl_agent: RLAgent | None = None
    if "rl" in mode_def.lineup:
        if checkpoint is None:
            logger.error("--checkpoint is required for RL modes")
            sys.exit(1)
        rl_agent = RLAgent(checkpoint)
    return {
        role_a: _build_role_agents(
            role_a, (0, 2, 4), seed, rollouts=rollouts, cache_path=cache_path, rl_agent=rl_agent
        ),
        role_b: _build_role_agents(
            role_b, (1, 3, 5), seed, rollouts=rollouts, cache_path=cache_path, rl_agent=rl_agent
        ),
    }


def _place_agents(
    rotated_lineup: tuple[str, str], role_agents: dict[str, list[TrucoAgent]]
) -> list[TrucoAgent]:
    """Map a rotated (slot -> role) lineup to the 6 players: slot 0 is Team
    A's 3 players, slot 1 is Team B's, each in mano order."""
    player_to_agent: dict[int, TrucoAgent] = {}
    for slot, role in enumerate(rotated_lineup):
        for pos_idx, player in enumerate(_SLOT_PLAYERS[slot]):
            player_to_agent[player] = role_agents[role][pos_idx]
    return [player_to_agent[p] for p in range(6)]


def benchmark(
    mode: str,
    n: int,
    seed: int = 42,
    profile: bool = False,
    rollouts: int = 20,
    cache_path: Path | None = None,
    checkpoint: str | None = None,
    rotation_offset: Callable[[int], int] = lambda engine_seed: engine_seed,
):
    if mode not in MODES:
        logger.error("Unknown mode: %s", mode)
        sys.exit(1)
    mode_def = MODES[mode]
    role_a, role_b = mode_def.lineup

    if n % 2 != 0:
        logger.error("--n must be even (2-role lineup, one role per team slot)")
        sys.exit(1)

    game = TrucoGame()
    run_fn = run_match if mode_def.is_match else run_game
    unit = "matches" if mode_def.is_match else "hands"
    label_A, label_B = _labels(mode, rollouts, checkpoint)

    role_agents = _build_agents(
        mode_def, seed, rollouts=rollouts, cache_path=cache_path, checkpoint=checkpoint
    )

    t0 = time.perf_counter()

    def play(pairs: Sequence[tuple[int, int]]) -> Sequence[int | None]:
        winning_seats: list[int | None] = []
        wins_role = {role_a: 0, role_b: 0}
        for i, (engine_seed, _driver_seed) in enumerate(pairs):
            rotated = rotate(mode_def.lineup, rotation_offset(engine_seed))
            agents = _place_agents(rotated, role_agents)
            result = run_fn(game, agents, seed=engine_seed)
            if result == -1:
                winning_seats.append(None)
            else:
                wins_role[rotated[result]] += 1
                winning_seats.append(result)

            if (i + 1) % 10 == 0:
                elapsed_so_far = time.perf_counter() - t0
                rate = (i + 1) / elapsed_so_far
                eta = (len(pairs) - i - 1) / rate if rate > 0 else float("inf")
                logger.info(
                    "%d/%d  A:%.0f%%  %.2f %s/s  ETA %.0fs",
                    i + 1,
                    len(pairs),
                    100 * wins_role[role_a] / (i + 1),
                    rate,
                    unit,
                    eta,
                )
        return winning_seats

    payload = run_arm(
        lineup=mode_def.lineup,
        num_seats=2,
        n_games=n,
        engine_seed_base=seed,
        driver_seed_base=seed,
        play=play,
        winning_seat=lambda r: r,
        rotation_offset=rotation_offset,
    )

    elapsed = time.perf_counter() - t0
    games_per_sec = n / elapsed

    for agents in role_agents.values():
        for agent in agents:
            if isinstance(agent, VonNeumannAgent):
                agent.save_cache()

    by_role = payload["by_role"]
    wins_A = by_role[role_a]["wins"]
    wins_B = by_role[role_b]["wins"]
    ties = n - wins_A - wins_B

    print(f"\n{'─' * 50}")
    print(f"Mode:        {mode}")
    print(f"{unit.capitalize()}:      {n:,}")
    print(f"{'─' * 50}")
    print(f"{label_A} wins:  {wins_A:,}  ({100 * wins_A / n:.1f}%)")
    print(f"{label_B} wins:  {wins_B:,}  ({100 * wins_B / n:.1f}%)")
    print(f"Ties:        {ties:,}  ({100 * ties / n:.1f}%)")
    if profile:
        print(f"{'─' * 50}")
        print(f"Elapsed:     {elapsed:.2f}s")
        print(f"Speed:       {games_per_sec:,.0f} games/sec")
    print(f"{'─' * 50}\n")

    # Validation hints
    if mode == "random":
        win_rate_A = wins_A / (wins_A + wins_B) if (wins_A + wins_B) > 0 else 0.5
        if abs(win_rate_A - 0.5) > 0.05:
            logger.warning("Random vs Random win rate is far from 50%%. Check engine.")
    elif mode == "threshold_vs_random":
        win_rate_T = wins_A / (wins_A + wins_B) if (wins_A + wins_B) > 0 else 0.5
        if win_rate_T < 0.55:
            logger.warning("ThresholdAgent win rate < 55%% vs random. Check engine or thresholds.")
        else:
            logger.info("OK: ThresholdAgent is performing better than random.")
    elif mode == "von_neumann_vs_random":
        win_rate_vn = wins_A / (wins_A + wins_B) if (wins_A + wins_B) > 0 else 0.5
        if win_rate_vn < 0.60:
            logger.warning("VonNeumannAgent win rate < 60%% vs random. May need more rollouts.")
        else:
            logger.info("OK: VonNeumannAgent is performing better than random.")


def _labels(mode: str, rollouts: int, checkpoint: str | None) -> tuple[str, str]:
    """The printed report's role labels -- kept as an explicit table (rather
    than derived from role names) so display strings are exactly what they
    were before the mode-registry rewrite, including the ones parameterised
    by ``--rollouts``/``--checkpoint``."""
    vn = f"VonNeumann(r={rollouts})"
    rl_label = f"RL({Path(checkpoint).stem})" if checkpoint else "RL"
    return {
        "random": ("Random A", "Random B"),
        "threshold_vs_random": ("Threshold", "Random"),
        "threshold_vs_threshold": ("Threshold A", "Threshold B"),
        "von_neumann_vs_random": (vn, "Random"),
        "von_neumann_vs_threshold": (vn, "Threshold"),
        "match_von_neumann_vs_random": (vn, "Random"),
        "match_von_neumann_vs_threshold": (vn, "Threshold"),
        "match_threshold_vs_random": ("Threshold", "Random"),
        "match_rl_vs_random": (rl_label, "Random"),
        "match_rl_vs_threshold": (rl_label, "Threshold"),
        "match_rl_vs_vonneumann": (rl_label, vn),
    }[mode]


def main():
    parser = argparse.ArgumentParser(description="Benchmark Truco agents")
    parser.add_argument("--mode", choices=sorted(MODES), default="random")
    parser.add_argument("--n", type=int, default=1000, help="Number of games (must be even)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument(
        "--rollouts", type=int, default=20, help="MC rollouts per action (VonNeumannAgent)"
    )
    parser.add_argument(
        "--cache_path", type=Path, default=None, help="Path to JSON EV cache file (VonNeumannAgent)"
    )
    parser.add_argument(
        "--checkpoint", type=str, default=None, help="Path to trained RL checkpoint (.zip)"
    )
    args = parser.parse_args()

    benchmark(
        args.mode,
        args.n,
        seed=args.seed,
        profile=args.profile,
        rollouts=args.rollouts,
        cache_path=args.cache_path,
        checkpoint=args.checkpoint,
    )


if __name__ == "__main__":
    main()
