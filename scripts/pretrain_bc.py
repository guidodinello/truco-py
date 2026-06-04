"""
Behavioral Cloning pre-trainer for Truco RL agent.

Generates trajectories by having ThresholdAgent play all 6 seats, then trains
the MaskablePPO policy network via supervised cross-entropy on (obs, action) pairs.
This initializes the policy to imitate ThresholdAgent in ~100k steps — far faster
than the equivalent PPO warm-start (~5M steps).

After BC pre-training, continue with PPO for fine-tuning:
    uv run training/train.py --opponents threshold --steps 2000000

Workflow:
    uv run scripts/pretrain_bc.py --games 50000 --epochs 10 --out checkpoints/bc_init.zip
    uv run scripts/pretrain_bc.py --games 50000 --epochs 10 --load checkpoints/bc_init.zip --out checkpoints/bc_v2.zip  # noqa: E501

Incremental re-training (after new MC experiments update ThresholdAgent):
    uv run scripts/pretrain_bc.py --games 20000 --epochs 5 --load checkpoints/truco_selfplay_final.zip --out checkpoints/bc_updated.zip  # noqa: E501
"""

import argparse
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from torch.utils.data import DataLoader, TensorDataset

from agents.threshold_agent import ThresholdAgent
from engine.actions import N_ACTIONS
from engine.game import TrucoGame
from engine.phases import Phase
from log import get_logger
from training.env import TrucoEnv
from training.state_encoder import obs_to_vector

ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = ROOT / "checkpoints"
LOG_DIR = ROOT / "logs"

logger = get_logger("pretrain_bc", LOG_DIR / "bc_pretrain.log")


# ── Data collection ──────────────────────────────────────────────────────────


def collect_trajectories(n_games: int, seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Play n_games with ThresholdAgent in all 6 seats.
    Returns (observations, actions, action_masks) arrays.

    Each step where ThresholdAgent acts in seat `p` contributes one sample:
      obs   = obs_to_vector(state, p)
      action = ThresholdAgent.choose_action(...)
      mask  = legal action mask
    """
    game = TrucoGame()
    rng = random.Random(seed)

    obs_list = []
    act_list = []
    mask_list = []

    agents = [ThresholdAgent(seed=seed + i) for i in range(6)]

    for game_idx in range(n_games):
        state = game.reset(seed=rng.randint(0, 2**31))
        for agent in agents:
            agent.reset()

        while state.phase != Phase.DONE:
            cp = state.current_player
            legal = game.legal_actions(state)
            if not legal:
                break

            obs = obs_to_vector(state, cp)
            action = agents[cp].choose_action(state, legal, cp)

            mask = np.zeros(N_ACTIONS, dtype=bool)
            for a in legal:
                mask[a.value] = True

            obs_list.append(obs)
            act_list.append(action.value)
            mask_list.append(mask)

            game.apply_action(state, action)

        if (game_idx + 1) % 5000 == 0:
            logger.info(
                "collected %s/%s games (%s steps)",
                f"{game_idx + 1:,}",
                f"{n_games:,}",
                f"{len(obs_list):,}",
            )

    observations = np.stack(obs_list).astype(np.float32)
    actions = np.array(act_list, dtype=np.int64)
    masks = np.stack(mask_list)

    return observations, actions, masks


# ── BC training ───────────────────────────────────────────────────────────────


def train_bc(
    observations: np.ndarray,
    actions: np.ndarray,
    masks: np.ndarray,
    model: MaskablePPO,
    epochs: int,
    batch_size: int,
    lr: float,
) -> None:
    """
    Supervised cross-entropy on (obs -> action) pairs, masked to legal actions.
    Only updates the policy network (actor), not the value head.
    """
    device = model.device
    policy = model.policy
    policy.train()

    optimizer = torch.optim.Adam(policy.parameters(), lr=lr)

    obs_t = torch.tensor(observations, device=device)
    act_t = torch.tensor(actions, device=device)
    mask_t = torch.tensor(masks, device=device)

    dataset = TensorDataset(obs_t, act_t, mask_t)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    n_samples = len(observations)
    logger.info(
        "BC training: %s samples, %d epochs, batch=%d", f"{n_samples:,}", epochs, batch_size
    )

    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        correct = 0

        for obs_b, act_b, mask_b in loader:
            # Get action logits from the actor
            with torch.no_grad():
                features = policy.extract_features(obs_b)
                latent_pi, _ = policy.mlp_extractor(features)

            logits = policy.action_net(latent_pi)

            # Mask illegal actions (set to large negative before softmax)
            logits = logits + (~mask_b).float() * (-1e9)

            loss = nn.functional.cross_entropy(logits, act_b)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(obs_b)
            correct += (logits.argmax(dim=1) == act_b).sum().item()

        avg_loss = total_loss / n_samples
        accuracy = correct / n_samples
        logger.info("epoch %2d/%d  loss=%.4f  acc=%.3f", epoch, epochs, avg_loss, accuracy)


# ── Model init helpers ────────────────────────────────────────────────────────


def build_fresh_model(seed: int) -> MaskablePPO:
    """Create a MaskablePPO with the standard architecture, using a dummy env."""
    CHECKPOINT_DIR.mkdir(exist_ok=True)

    def _make_env():
        env = TrucoEnv(seed=seed)
        return ActionMasker(env, lambda e: e.action_masks())

    from stable_baselines3.common.vec_env import DummyVecEnv

    vec_env = DummyVecEnv([_make_env])

    model = MaskablePPO(
        "MlpPolicy",
        vec_env,
        verbose=0,
        seed=seed,
        device="auto",
        policy_kwargs=dict(net_arch=[256, 256]),
    )
    return model


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Behavioral Cloning pre-trainer for Truco")
    parser.add_argument(
        "--games",
        type=int,
        default=50_000,
        help="Number of ThresholdAgent games to collect (default 50k)",
    )
    parser.add_argument("--epochs", type=int, default=10, help="BC training epochs (default 10)")
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument(
        "--lr", type=float, default=1e-3, help="Learning rate for BC (higher than PPO is fine)"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--load",
        type=str,
        default=None,
        help="Path to existing checkpoint to fine-tune (incremental BC)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output path for BC checkpoint (default: checkpoints/bc_init.zip)",
    )
    args = parser.parse_args()

    out_path = args.out or str(CHECKPOINT_DIR / "bc_init.zip")

    logger.info("Behavioral Cloning — Truco RL")
    logger.info("  Games to collect : %s", f"{args.games:,}")
    logger.info("  Epochs           : %d", args.epochs)
    logger.info("  Load checkpoint  : %s", args.load or "None (fresh model)")
    logger.info("  Output           : %s", out_path)

    t0 = time.perf_counter()

    # 1. Collect ThresholdAgent trajectories
    logger.info("[1/3] Collecting trajectories...")
    observations, actions, masks = collect_trajectories(args.games, seed=args.seed)
    logger.info("Done: %s (obs, action) pairs", f"{len(observations):,}")

    # 2. Load or build model
    logger.info("[2/3] %s model...", "Loading" if args.load else "Building")
    if args.load:
        from sb3_contrib.common.wrappers import ActionMasker
        from stable_baselines3.common.vec_env import DummyVecEnv

        def _make_env():
            env = TrucoEnv(seed=args.seed)
            return ActionMasker(env, lambda e: e.action_masks())

        vec_env = DummyVecEnv([_make_env])
        model = MaskablePPO.load(args.load, env=vec_env, device="auto")
        logger.info("Loaded from %s", args.load)
    else:
        model = build_fresh_model(args.seed)
        logger.info("Built fresh model (256x256, device=%s)", model.device)

    # 3. BC training
    logger.info("[3/3] Training...")
    train_bc(observations, actions, masks, model, args.epochs, args.batch_size, args.lr)

    # 4. Save
    model.save(out_path)
    elapsed = time.perf_counter() - t0
    logger.info("Done in %.1fs. Saved to %s", elapsed, out_path)
    logger.info("Next step — PPO fine-tuning from BC checkpoint:")
    logger.info("  uv run training/train.py --opponents threshold --steps 2000000")


if __name__ == "__main__":
    main()
