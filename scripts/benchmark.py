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
"""

import argparse
import sys
import time
from pathlib import Path

from agents.random_agent import RandomAgent
from agents.rl_agent import RLAgent
from agents.threshold_agent import ThresholdAgent
from agents.von_neumann_agent import VonNeumannAgent
from engine.game import TrucoGame
from engine.game_state import TEAM_A
from engine.phases import Phase
from log import get_logger

# Flush stdout after each line so progress appears immediately when piped or captured.
sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

logger = get_logger("benchmark")


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


def benchmark(
    mode: str,
    n: int,
    seed: int = 42,
    profile: bool = False,
    rollouts: int = 20,
    cache_path: Path | None = None,
    checkpoint: str | None = None,
):
    game = TrucoGame()

    if mode == "random":
        agents = [RandomAgent(seed=seed + i) for i in range(6)]
        label_A, label_B = "Random A", "Random B"
    elif mode == "threshold_vs_random":
        # Team A = threshold, Team B = random
        agents = [
            ThresholdAgent(seed=seed + i) if i in TEAM_A else RandomAgent(seed=seed + i)
            for i in range(6)
        ]
        label_A, label_B = "Threshold", "Random"
    elif mode == "threshold_vs_threshold":
        agents = [ThresholdAgent(seed=seed + i) for i in range(6)]
        label_A, label_B = "Threshold A", "Threshold B"
    elif mode == "von_neumann_vs_random":
        # Team A = Von Neumann, Team B = random
        agents = [
            VonNeumannAgent(n_rollouts=rollouts, seed=seed + i, cache_path=cache_path)
            if i in TEAM_A
            else RandomAgent(seed=seed + i)
            for i in range(6)
        ]
        label_A, label_B = f"VonNeumann(r={rollouts})", "Random"
    elif mode == "von_neumann_vs_threshold":
        # Team A = Von Neumann, Team B = threshold
        agents = [
            VonNeumannAgent(n_rollouts=rollouts, seed=seed + i, cache_path=cache_path)
            if i in TEAM_A
            else ThresholdAgent(seed=seed + i)
            for i in range(6)
        ]
        label_A, label_B = f"VonNeumann(r={rollouts})", "Threshold"
    elif mode == "match_von_neumann_vs_random":
        agents = [
            VonNeumannAgent(n_rollouts=rollouts, seed=seed + i, cache_path=cache_path)
            if i in TEAM_A
            else RandomAgent(seed=seed + i)
            for i in range(6)
        ]
        label_A, label_B = f"VonNeumann(r={rollouts})", "Random"
    elif mode == "match_von_neumann_vs_threshold":
        agents = [
            VonNeumannAgent(n_rollouts=rollouts, seed=seed + i, cache_path=cache_path)
            if i in TEAM_A
            else ThresholdAgent(seed=seed + i)
            for i in range(6)
        ]
        label_A, label_B = f"VonNeumann(r={rollouts})", "Threshold"
    elif mode == "match_threshold_vs_random":
        agents = [
            ThresholdAgent(seed=seed + i) if i in TEAM_A else RandomAgent(seed=seed + i)
            for i in range(6)
        ]
        label_A, label_B = "Threshold", "Random"
    elif mode in ("match_rl_vs_random", "match_rl_vs_threshold", "match_rl_vs_vonneumann"):
        if checkpoint is None:
            logger.error("--checkpoint is required for RL modes")
            sys.exit(1)
        rl = RLAgent(checkpoint)
        if mode == "match_rl_vs_random":
            agents = [rl if i in TEAM_A else RandomAgent(seed=seed + i) for i in range(6)]
            opp_label = "Random"
        elif mode == "match_rl_vs_threshold":
            agents = [rl if i in TEAM_A else ThresholdAgent(seed=seed + i) for i in range(6)]
            opp_label = "Threshold"
        else:  # match_rl_vs_vonneumann
            agents = [
                rl if i in TEAM_A
                else VonNeumannAgent(n_rollouts=rollouts, seed=seed + i, cache_path=cache_path)
                for i in range(6)
            ]
            opp_label = f"VonNeumann(r={rollouts})"
        label_A, label_B = f"RL({Path(checkpoint).stem})", opp_label
    else:
        logger.error("Unknown mode: %s", mode)
        sys.exit(1)

    is_match = mode.startswith("match_")
    run_fn = run_match if is_match else run_game
    unit = "matches" if is_match else "hands"

    wins_A = wins_B = ties = 0
    t0 = time.perf_counter()

    for i in range(n):
        result = run_fn(game, agents, seed=seed + i)
        if result == 0:
            wins_A += 1
        elif result == 1:
            wins_B += 1
        else:
            ties += 1
        if (i + 1) % 10 == 0:
            elapsed_so_far = time.perf_counter() - t0
            rate = (i + 1) / elapsed_so_far
            eta = (n - i - 1) / rate if rate > 0 else float("inf")
            logger.info(
                "%d/%d  A:%.0f%%  %.2f %s/s  ETA %.0fs",
                i + 1, n,
                100 * wins_A / (i + 1),
                rate, unit, eta,
            )

    elapsed = time.perf_counter() - t0
    games_per_sec = n / elapsed

    for agent in agents:
        if isinstance(agent, VonNeumannAgent):
            agent.save_cache()

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


def main():
    parser = argparse.ArgumentParser(description="Benchmark Truco agents")
    parser.add_argument(
        "--mode",
        choices=[
            "random",
            "threshold_vs_random",
            "threshold_vs_threshold",
            "von_neumann_vs_random",
            "von_neumann_vs_threshold",
            "match_von_neumann_vs_random",
            "match_von_neumann_vs_threshold",
            "match_threshold_vs_random",
            "match_rl_vs_random",
            "match_rl_vs_threshold",
            "match_rl_vs_vonneumann",
        ],
        default="random",
    )
    parser.add_argument("--n", type=int, default=1000)
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
