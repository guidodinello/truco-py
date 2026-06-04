"""
Smoke test for MC→RL integration (Tracks A-D).

Runs a short training loop with all features enabled to verify end-to-end
wiring. Not a correctness test — just checks nothing crashes.

Usage:
    uv run scripts/smoke_test_mc_rl.py
    uv run scripts/smoke_test_mc_rl.py --steps 2000 --n-envs 4
    uv run scripts/smoke_test_mc_rl.py --no-aux --no-mc   # baseline only
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from training.train import train  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=5_000)
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--mc-rollouts", type=int, default=10)
    parser.add_argument("--lambda-aux", type=float, default=0.1)
    parser.add_argument("--no-aux", action="store_true", help="Disable --aux-heads")
    parser.add_argument(
        "--no-mc", action="store_true", help="Disable mc_rollouts and mc_potential_reward"
    )
    args = parser.parse_args()

    aux_heads = not args.no_aux
    mc_rollouts = 0 if args.no_mc else args.mc_rollouts
    mc_pot_reward = not args.no_mc

    print(f"Smoke test: steps={args.steps}  n_envs={args.n_envs}")
    print(f"  aux_heads={aux_heads}  lambda_aux={args.lambda_aux}")
    print(f"  mc_rollouts={mc_rollouts}  mc_potential_reward={mc_pot_reward}")
    print()

    train(
        opponent_mode="random",
        total_steps=args.steps,
        n_envs=args.n_envs,
        shaped_reward=False,
        seed=42,
        checkpoint_freq=args.steps,  # only one checkpoint at the end
        load_checkpoint=None,
        aux_heads=aux_heads,
        lambda_aux=args.lambda_aux,
        aux_anneal_steps=50_000,  # fast anneal for smoke test
        mc_rollouts=mc_rollouts,
        mc_potential_reward=mc_pot_reward,
    )

    print("\nSmoke test passed.")


if __name__ == "__main__":
    main()
