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

from agents.random_agent import RandomAgent
from agents.threshold_agent import ThresholdAgent
from agents.von_neumann_agent import VonNeumannAgent
from engine.game import TrucoGame
from engine.game_state import TEAM_A
from engine.phases import Phase
from log import get_logger

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


def benchmark(mode: str, n: int, seed: int = 42, profile: bool = False, rollouts: int = 20):
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
            VonNeumannAgent(n_rollouts=rollouts, seed=seed + i)
            if i in TEAM_A
            else RandomAgent(seed=seed + i)
            for i in range(6)
        ]
        label_A, label_B = f"VonNeumann(r={rollouts})", "Random"
    elif mode == "von_neumann_vs_threshold":
        # Team A = Von Neumann, Team B = threshold
        agents = [
            VonNeumannAgent(n_rollouts=rollouts, seed=seed + i)
            if i in TEAM_A
            else ThresholdAgent(seed=seed + i)
            for i in range(6)
        ]
        label_A, label_B = f"VonNeumann(r={rollouts})", "Threshold"
    else:
        logger.error("Unknown mode: %s", mode)
        sys.exit(1)

    wins_A = wins_B = ties = 0
    t0 = time.perf_counter()

    for i in range(n):
        result = run_game(game, agents, seed=seed + i)
        if result == 0:
            wins_A += 1
        elif result == 1:
            wins_B += 1
        else:
            ties += 1

    elapsed = time.perf_counter() - t0
    games_per_sec = n / elapsed

    print(f"\n{'─' * 50}")
    print(f"Mode:        {mode}")
    print(f"Games:       {n:,}")
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
        ],
        default="random",
    )
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument(
        "--rollouts", type=int, default=20, help="MC rollouts per action (VonNeumannAgent)"
    )
    args = parser.parse_args()

    benchmark(args.mode, args.n, seed=args.seed, profile=args.profile, rollouts=args.rollouts)


if __name__ == "__main__":
    main()
