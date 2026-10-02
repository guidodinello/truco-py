"""
Behavioral-cloning warm start for the Truco RL agent (experiment 009).

Differences from the exp-002 version (whose flaw was reporting *training-set* accuracy):
  * validation is held out **by game** (game index % VAL_EVERY == 0), never by decision --
    decisions inside one hand are strongly correlated, so a decision-level split leaks;
  * the whole actor is trained (features -> policy MLP -> action head), not just ``action_net``
    on frozen random features, plus a value head on the hand outcome, so PPO does not start
    from a cold critic that wrecks the clone;
  * the dataset is generated in parallel from a seeded set of games, optionally from real
    pre-hand (scores, mano) contexts (``--context-bank``, exp 009 D4), and saved to disk;
  * the best epoch by *validation* loss is kept, and ``bc_metrics.json`` records every epoch.

    python -m scripts.pretrain_bc --games 50000 --workers 16 \\
        --context-bank runs/009/bc/context_bank.npz --out runs/009/bc/bc_init.zip

Exit code 2 when validation accuracy is below ``--min-val-acc`` (the pre-registered hard stop).
"""

import argparse
import copy
import json
import logging
import random
import time
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from agents.rl_agent import check_action_space
from agents.threshold_agent import ThresholdAgent
from engine.actions import N_ACTIONS
from engine.game import TrucoGame
from engine.phases import Phase
from engine.rules import N_SEATS
from log import get_logger
from training.context_bank import ContextBank
from training.env import TrucoEnv
from training.reward import PointDiffReward, SparseReward
from training.state_encoder import obs_to_vector

logger = logging.getLogger("pretrain_bc")

VAL_EVERY = 10  # every 10th game is validation
GAMMA = 0.99  # discount of the value target, as in PPO
MAX_ACTIONS_PER_HAND = 2000
VF_COEF = 0.5

Dataset = dict[str, np.ndarray]


# ── data collection ───────────────────────────────────────────────────────────


def split_by_game(game_ids: np.ndarray, val_every: int = VAL_EVERY) -> np.ndarray:
    """Boolean validation mask: whole games go to validation, so train/val never share a hand."""
    return game_ids % val_every == 0


def _collect_shard(job: tuple[list[int], int, str | None, str, float]) -> Dataset:
    """Worker: play the given game indices (ThresholdAgent in all 6 seats)."""
    game_ids, seed, bank_path, reward_kind, scale = job
    bank = ContextBank.load(Path(bank_path)) if bank_path else None
    reward = PointDiffReward(scale) if reward_kind == "diff" else SparseReward()
    game = TrucoGame()
    agents = [ThresholdAgent(seed=seed + i) for i in range(N_SEATS)]

    obs_l: list[np.ndarray] = []
    act_l: list[int] = []
    mask_l: list[np.ndarray] = []
    val_l: list[float] = []
    gid_l: list[int] = []

    for gid in game_ids:
        # Each game's randomness is a pure function of (seed, gid), so any shard layout and any
        # worker count produce the same dataset.
        rng = random.Random(f"bc-{seed}-{gid}")
        deal_seed = rng.randint(0, 2**31 - 1)
        if bank is not None:
            scores, mano = bank.sample(rng)
            state = game.reset(seed=deal_seed, scores=scores, mano=mano)
        else:
            state = game.reset(seed=deal_seed)
        for agent in agents:
            agent.reset()

        rows: list[tuple[int, np.ndarray, int, np.ndarray]] = []  # (player, obs, action, mask)
        n_actions = 0
        while state.phase != Phase.DONE:
            cp = state.current_player
            legal = game.legal_actions(state)
            if not legal:
                break
            action = agents[cp].choose_action(state, legal, cp)
            mask = np.zeros(N_ACTIONS, dtype=bool)
            for a in legal:
                mask[a.value] = True
            rows.append((cp, obs_to_vector(state, cp), action.value, mask))
            game.apply_action(state, action)
            n_actions += 1
            if n_actions > MAX_ACTIONS_PER_HAND:
                raise RuntimeError(f"game {gid}: hand exceeded {MAX_ACTIONS_PER_HAND} actions")

        # Value target = the learner-perspective return PPO will see: the terminal reward of the
        # player's team, discounted per *that player's* remaining decisions.
        remaining = [0] * N_SEATS
        for player, obs, act, mask in reversed(rows):
            r = reward.compute(state, player, True)
            obs_l.append(obs)
            act_l.append(act)
            mask_l.append(mask)
            val_l.append(r * GAMMA ** remaining[player])
            gid_l.append(gid)
            remaining[player] += 1

    return {
        "obs": np.stack(obs_l).astype(np.float32),
        "actions": np.array(act_l, dtype=np.int64),
        "masks": np.stack(mask_l),
        "values": np.array(val_l, dtype=np.float32),
        "game_ids": np.array(gid_l, dtype=np.int64),
    }


def collect_dataset(
    n_games: int,
    seed: int,
    *,
    bank_path: Path | None = None,
    reward_kind: str = "diff",
    scale: float = 15.0,
    workers: int = 1,
) -> Dataset:
    ids = list(range(n_games))
    shards = [ids[i::workers] for i in range(workers)] if workers > 1 else [ids]
    jobs = [(s, seed, str(bank_path) if bank_path else None, reward_kind, scale) for s in shards]
    if workers > 1:
        with get_context("fork").Pool(workers) as pool:
            parts = pool.map(_collect_shard, jobs)
    else:
        parts = [_collect_shard(jobs[0])]
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


# ── training ──────────────────────────────────────────────────────────────────


def _forward(
    policy: Any, obs: torch.Tensor, mask: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """Masked action logits and state values through the *whole* network."""
    features = policy.extract_features(obs)
    latent_pi, latent_vf = policy.mlp_extractor(features)
    logits = policy.action_net(latent_pi).masked_fill(~mask, -1e9)
    return logits, policy.value_net(latent_vf).squeeze(-1)


def _evaluate(policy: Any, data: dict[str, torch.Tensor], batch_size: int) -> dict[str, float]:
    policy.eval()
    n = len(data["actions"])
    ce = vf = correct = 0.0
    with torch.no_grad():
        for i in range(0, n, batch_size):
            sl = slice(i, i + batch_size)
            logits, value = _forward(policy, data["obs"][sl], data["masks"][sl])
            ce += nn.functional.cross_entropy(logits, data["actions"][sl], reduction="sum").item()
            vf += nn.functional.mse_loss(value, data["values"][sl], reduction="sum").item()
            correct += (logits.argmax(1) == data["actions"][sl]).sum().item()
    return {"loss": ce / n, "acc": correct / n, "vf_loss": vf / n}


def train_bc(
    ds: Dataset, model: MaskablePPO, epochs: int, batch_size: int, lr: float
) -> list[dict[str, float]]:
    """Joint policy + value cloning; restores the best-validation-loss epoch into ``model``."""
    device = model.device
    policy = model.policy
    val = split_by_game(ds["game_ids"])

    def to_t(mask: np.ndarray) -> dict[str, torch.Tensor]:
        return {
            "obs": torch.tensor(ds["obs"][mask], device=device),
            "actions": torch.tensor(ds["actions"][mask], device=device),
            "masks": torch.tensor(ds["masks"][mask], device=device),
            "values": torch.tensor(ds["values"][mask], device=device),
        }

    train_t, val_t = to_t(~val), to_t(val)
    n_train = len(train_t["actions"])
    logger.info(
        "BC: %s train / %s val samples (%d val games of %d), %d epochs, batch=%d, lr=%g",
        f"{n_train:,}",
        f"{len(val_t['actions']):,}",
        len(np.unique(ds["game_ids"][val])),
        len(np.unique(ds["game_ids"])),
        epochs,
        batch_size,
        lr,
    )
    optimizer = torch.optim.Adam(policy.parameters(), lr=lr)
    history: list[dict[str, float]] = []
    best: tuple[float, dict[str, torch.Tensor]] = (float("inf"), {})

    for epoch in range(1, epochs + 1):
        policy.train()
        perm = torch.randperm(n_train, device=device)
        tot_ce = tot_vf = correct = 0.0
        for i in range(0, n_train, batch_size):
            idx = perm[i : i + batch_size]
            logits, value = _forward(policy, train_t["obs"][idx], train_t["masks"][idx])
            ce = nn.functional.cross_entropy(logits, train_t["actions"][idx])
            vf = nn.functional.mse_loss(value, train_t["values"][idx])
            optimizer.zero_grad()
            (ce + VF_COEF * vf).backward()
            optimizer.step()
            tot_ce += ce.item() * len(idx)
            tot_vf += vf.item() * len(idx)
            correct += (logits.argmax(1) == train_t["actions"][idx]).sum().item()

        v = _evaluate(policy, val_t, batch_size)
        row = {
            "epoch": epoch,
            "train_loss": tot_ce / n_train,
            "train_acc": correct / n_train,
            "train_vf_loss": tot_vf / n_train,
            "val_loss": v["loss"],
            "val_acc": v["acc"],
            "val_vf_loss": v["vf_loss"],
        }
        history.append(row)
        logger.info(
            "epoch %2d/%d  train loss=%.4f acc=%.3f | val loss=%.4f acc=%.3f vf=%.4f",
            epoch,
            epochs,
            row["train_loss"],
            row["train_acc"],
            row["val_loss"],
            row["val_acc"],
            row["val_vf_loss"],
        )
        if row["val_loss"] < best[0]:
            best = (row["val_loss"], copy.deepcopy(policy.state_dict()))

    policy.load_state_dict(best[1])
    best_epoch = min(history, key=lambda r: r["val_loss"])["epoch"]
    logger.info("kept epoch %d (lowest validation loss)", int(best_epoch))
    return history


# ── model init ────────────────────────────────────────────────────────────────


def build_fresh_model(seed: int) -> MaskablePPO:
    """A MaskablePPO with the standard 256x256 architecture on a dummy env."""
    from stable_baselines3.common.vec_env import DummyVecEnv

    def _make_env():
        return ActionMasker(TrucoEnv(seed=seed), lambda e: e.action_masks())

    return MaskablePPO(
        "MlpPolicy",
        DummyVecEnv([_make_env]),
        verbose=0,
        seed=seed,
        device="auto",
        policy_kwargs=dict(net_arch=[256, 256]),
    )


def load_model(path: Path, seed: int) -> MaskablePPO:
    from stable_baselines3.common.vec_env import DummyVecEnv

    vec_env = DummyVecEnv([lambda: ActionMasker(TrucoEnv(seed=seed), lambda e: e.action_masks())])
    model = MaskablePPO.load(path, env=vec_env, device="auto")
    check_action_space(model, path)
    return model


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description="Behavioral cloning (exp 009)")
    p.add_argument("--games", type=int, default=50_000)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=2048)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--context-bank", type=Path, default=None)
    p.add_argument("--reward", choices=["sign", "diff"], default="diff")
    p.add_argument("--reward-scale", type=float, default=15.0)
    p.add_argument(
        "--dataset", type=Path, default=None, help="npz cache: load if present, else save"
    )
    p.add_argument("--load", type=Path, default=None, help="fine-tune an existing checkpoint")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--min-val-acc", type=float, default=0.70, help="pre-registered hard stop")
    args = p.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    get_logger("pretrain_bc", args.out.parent / "bc_pretrain.log")
    t0 = time.perf_counter()

    if args.dataset is not None and args.dataset.exists():
        logger.info("loading dataset %s", args.dataset)
        with np.load(args.dataset) as f:
            ds = {k: f[k] for k in f.files}
    else:
        logger.info("collecting %s games with %d workers", f"{args.games:,}", args.workers)
        ds = collect_dataset(
            args.games,
            args.seed,
            bank_path=args.context_bank,
            reward_kind=args.reward,
            scale=args.reward_scale,
            workers=args.workers,
        )
        if args.dataset is not None:
            args.dataset.parent.mkdir(parents=True, exist_ok=True)
            np.savez(args.dataset, **ds)
            logger.info("saved dataset %s", args.dataset)
    logger.info("%s (obs, action) pairs", f"{len(ds['actions']):,}")

    torch.manual_seed(args.seed)
    model = load_model(args.load, args.seed) if args.load else build_fresh_model(args.seed)
    history = train_bc(ds, model, args.epochs, args.batch_size, args.lr)
    model.save(str(args.out))

    final = min(history, key=lambda r: r["val_loss"])
    passed = final["val_acc"] >= args.min_val_acc
    metrics = {
        "games": int(len(np.unique(ds["game_ids"]))),
        "samples": int(len(ds["actions"])),
        "val_every": VAL_EVERY,
        "kept_epoch": int(final["epoch"]),
        "val_acc": final["val_acc"],
        "min_val_acc": args.min_val_acc,
        "gate_passed": passed,
        "seed": args.seed,
        "context_bank": str(args.context_bank) if args.context_bank else None,
        "elapsed_s": time.perf_counter() - t0,
        "history": history,
    }
    (args.out.parent / "bc_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    logger.info(
        "validation accuracy %.3f (%s the %.2f gate); saved %s in %.0fs",
        final["val_acc"],
        "PASSES" if passed else "FAILS",
        args.min_val_acc,
        args.out,
        time.perf_counter() - t0,
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
