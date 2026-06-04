"""
RL training entry point for Truco Uruguayo.

Phases:
  Phase 4 — Warm-start: train against ThresholdAgent opponents (--opponents threshold)
  Phase 5 — Self-play:  train against a rolling checkpoint pool (--opponents selfplay)

Usage:
    uv run training/train.py --opponents threshold --steps 5000000
    uv run training/train.py --opponents selfplay  --steps 50000000
    uv run training/train.py --opponents threshold --steps 2000000 --n-envs 4 --shaped-reward
"""

import argparse
import re
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

from agents.random_agent import RandomAgent
from agents.threshold_agent import ThresholdAgent
from log import get_logger
from training.env import TrucoEnv
from training.mc_tables import envido_label_from_obs, flor_label_from_obs
from training.policy import TrucoActorCriticPolicy
from training.reward import MCPotentialReward, ShapedReward, SparseReward
from training.self_play import SelfPlayManager

ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = ROOT / "checkpoints"
LOG_DIR = ROOT / "logs"

logger = get_logger("train", LOG_DIR / "train.log")

# How many CPU cores are available — used for env-count throughput advice.
_CPU_COUNT: int = len(__import__("os").sched_getaffinity(0))

# Empirical FPS per env measured on this hardware (threshold opponents, 24 envs).
# Used only to produce startup estimates; actual FPS is logged during training.
_FPS_PER_ENV: float = 150.0  # ~3600 FPS / 24 envs


def _steps_from_checkpoint(path: str) -> int:
    """Parse step count from a checkpoint filename like truco_selfplay_5000000.zip.

    Returns 0 if the filename doesn't match the pattern (e.g. *_final.zip).
    """
    m = re.search(r"_(\d+)\.zip$", Path(path).name)
    return int(m.group(1)) if m else 0


def _fmt_eta(seconds: float) -> str:
    # TODO: shouldnt this be better implemented with divmod?
    # or maybe using datetime or some standard time library
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m:02d}m"


# ── Env factory ─────────────────────────────────────────────────────────────


def make_env(
    opponent_mode: str,  # TODO: we should have an enum for this.
    shaped: bool,
    checkpoint_dir: str,  # TODO: if its a dir, use pathlib instead of a simple string
    seed: int,
    mc_rollouts: int = 0,
    mc_potential_reward: bool = False,
):
    """Return a callable that creates one masked TrucoEnv."""

    def _init():
        if shaped:
            reward_fn = ShapedReward()
        elif mc_potential_reward:
            reward_fn = MCPotentialReward()
        else:
            reward_fn = SparseReward()

        if opponent_mode == "selfplay":
            # Opponents are resampled from disk at each reset() — no shared state
            env = TrucoEnv(
                selfplay_dir=checkpoint_dir,
                reward_shaper=reward_fn,
                seed=seed,
                mc_rollouts=mc_rollouts,
            )
        else:
            if opponent_mode == "threshold":
                opponents = [ThresholdAgent(seed=seed + i) for i in range(5)]
            else:  # random
                opponents = [RandomAgent(seed=seed + i) for i in range(5)]
            env = TrucoEnv(
                opponent_agents=opponents,
                reward_shaper=reward_fn,
                seed=seed,
                mc_rollouts=mc_rollouts,
            )

        env = ActionMasker(env, lambda e: e.action_masks())
        return env

    return _init


# ── Auxiliary update step (Track B) ─────────────────────────────────────────


def aux_update_step(
    model: MaskablePPO,
    steps_done: int,
    aux_optimizer: torch.optim.Optimizer,
    anneal_total: int,
    lambda_max: float = 0.1,
    batch_size: int = 512,
) -> dict:  # TODO: cant this be typed more specifically? should we?
    """Run one auxiliary supervised gradient pass after model.learn().

    Uses observations from the just-filled rollout buffer to compute
    MC-derived labels and train the envido/flor prediction heads.

    Parameters
    ----------
    model         : MaskablePPO with TrucoActorCriticPolicy
    steps_done    : total training steps so far (for lambda annealing)
    aux_optimizer : Adam optimizer over model.policy.parameters()
    anneal_total  : step count at which lambda reaches 0
    lambda_max    : initial auxiliary loss weight
    batch_size    : mini-batch size for the aux update

    Returns
    -------
    dict with aux/lambda, aux/envido_loss, aux/flor_loss for logging
    """
    lambda_aux = max(0.0, lambda_max * (1.0 - steps_done / anneal_total))
    if lambda_aux == 0.0:
        return {"aux/lambda": 0.0, "aux/envido_loss": 0.0, "aux/flor_loss": 0.0}

    policy = model.policy
    device = model.device

    # rollout_buffer.observations shape: (n_steps, n_envs, obs_dim)
    obs_np = model.rollout_buffer.observations.reshape(
        -1, model.rollout_buffer.observations.shape[-1]
    )

    envido_labels_np = envido_label_from_obs(obs_np)  # (N,)
    flor_labels_np, flor_mask = flor_label_from_obs(obs_np)  # (N,), bool (N,)

    N = len(obs_np)
    idx = np.random.permutation(N)
    total_env_loss = 0.0
    total_flor_loss = 0.0
    n_batches = 0

    policy.set_training_mode(True)
    for start in range(0, N, batch_size):
        batch_idx = idx[start : start + batch_size]
        obs_t = torch.tensor(obs_np[batch_idx], dtype=torch.float32, device=device)
        env_lbl = torch.tensor(
            envido_labels_np[batch_idx], dtype=torch.float32, device=device
        ).unsqueeze(1)
        flor_lbl = torch.tensor(
            flor_labels_np[batch_idx], dtype=torch.float32, device=device
        ).unsqueeze(1)
        flor_msk = torch.tensor(flor_mask[batch_idx], dtype=torch.bool, device=device)

        env_pred, flor_pred = policy.predict_aux(obs_t)

        envido_loss = F.binary_cross_entropy(env_pred, env_lbl)
        flor_loss = (
            F.binary_cross_entropy(flor_pred[flor_msk], flor_lbl[flor_msk])
            if flor_msk.any()
            else torch.tensor(0.0, device=device)
        )

        loss = lambda_aux * (envido_loss + flor_loss)
        aux_optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), max_norm=0.5)
        aux_optimizer.step()

        total_env_loss += envido_loss.item()
        total_flor_loss += flor_loss.item()
        n_batches += 1

    policy.set_training_mode(False)
    return {
        "aux/lambda": lambda_aux,
        "aux/envido_loss": total_env_loss / max(n_batches, 1),
        "aux/flor_loss": total_flor_loss / max(n_batches, 1),
    }


# ── Checkpoint callback ──────────────────────────────────────────────────────


class CheckpointCallback:
    """Saves model every `save_freq` steps and registers it with SelfPlayManager."""

    def __init__(self, save_freq: int, spm: "SelfPlayManager | None", label: str = "truco"):
        self.save_freq = save_freq
        self.spm = spm
        self.label = label
        self._last_save = 0

    def __call__(self, model: MaskablePPO, n_steps: int):
        if n_steps - self._last_save >= self.save_freq:
            path = CHECKPOINT_DIR / f"{self.label}_{n_steps}.zip"
            model.save(str(path))
            if self.spm is not None:
                self.spm.add_checkpoint(str(path))
            self._last_save = n_steps
            logger.info("checkpoint saved: %s", path.name)


# ── Checkpoint loading ───────────────────────────────────────────────────────


def _graft_aux_heads(model: MaskablePPO) -> None:
    """Add envido/flor heads to an existing policy that was saved without them."""
    import torch.nn as nn

    p = model.policy
    latent_dim = p.mlp_extractor.latent_dim_pi
    p.envido_head = nn.Linear(latent_dim, 1).to(model.device)
    p.flor_head = nn.Linear(latent_dim, 1).to(model.device)
    nn.init.normal_(p.envido_head.weight, std=0.01)
    nn.init.zeros_(p.envido_head.bias)
    nn.init.normal_(p.flor_head.weight, std=0.01)
    nn.init.zeros_(p.flor_head.bias)
    p.__class__ = TrucoActorCriticPolicy
    logger.info("Upgraded loaded policy to TrucoActorCriticPolicy (aux heads grafted)")


def _load_checkpoint(path: str, vec_env, aux_heads: bool) -> MaskablePPO:
    """Load a checkpoint, handling all combinations of saved/requested policy class.

    Four cases:
      saved=MlpPolicy,             aux_heads=False → plain load ✓
      saved=MlpPolicy,             aux_heads=True  → plain load + graft heads
      saved=TrucoActorCriticPolicy, aux_heads=True  → load with custom_objects ✓
      saved=TrucoActorCriticPolicy, aux_heads=False → load + strip heads (not supported;
                                                       just load with custom_objects)
    """
    _kwargs = dict(env=vec_env, verbose=1, tensorboard_log=str(LOG_DIR), device="auto")

    if aux_heads:
        # Try loading as TrucoActorCriticPolicy (checkpoint already has aux heads)
        try:
            return MaskablePPO.load(
                path, custom_objects={"policy_class": TrucoActorCriticPolicy}, **_kwargs
            )
        except RuntimeError:
            # Checkpoint was saved without aux heads — load normally then graft
            model = MaskablePPO.load(path, **_kwargs)
            _graft_aux_heads(model)
            return model
    else:
        try:
            return MaskablePPO.load(path, **_kwargs)
        except RuntimeError:
            # Checkpoint was saved with aux heads but --aux-heads not passed.
            # Load with the correct class so the weights match; the heads will
            # simply be unused during this run.
            logger.warning(
                "Checkpoint has aux heads but --aux-heads not set. "
                "Loading with TrucoActorCriticPolicy anyway."
            )
            return MaskablePPO.load(
                path, custom_objects={"policy_class": TrucoActorCriticPolicy}, **_kwargs
            )


# ── Main training loop ───────────────────────────────────────────────────────


def train(
    opponent_mode: str,
    total_steps: int,
    n_envs: int,
    shaped_reward: bool,
    seed: int,
    checkpoint_freq: int,
    load_checkpoint: str | None = None,
    aux_heads: bool = False,
    lambda_aux: float = 0.1,
    aux_anneal_steps: int = 10_000_000,
    mc_rollouts: int = 0,
    mc_potential_reward: bool = False,
):
    CHECKPOINT_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    checkpoint_dir_str = str(CHECKPOINT_DIR)

    est_fps = _FPS_PER_ENV * min(n_envs, _CPU_COUNT)
    est_total_s = total_steps / est_fps
    logger.info("Truco RL Training")
    logger.info("  Opponent mode : %s", opponent_mode)
    logger.info("  Total steps   : %s", f"{total_steps:,}")
    logger.info("  Parallel envs : %d  (CPU cores: %d)", n_envs, _CPU_COUNT)
    logger.info("  Shaped reward : %s", shaped_reward)
    logger.info(
        "  Aux heads     : %s  (lambda_max=%.3f, anneal=%s steps)",
        aux_heads,
        lambda_aux,
        f"{aux_anneal_steps:,}",
    )
    logger.info("  MC rollouts   : %d  (V_MC in obs[169])", mc_rollouts)
    logger.info("  MC pot. reward: %s", mc_potential_reward)
    logger.info("  Load checkpoint: %s", load_checkpoint or "None (fresh)")
    logger.info("  Device        : %s", "cuda" if torch.cuda.is_available() else "cpu")
    logger.info(
        "  Est. FPS      : ~%d  (%.0f envs × %.0f FPS/env, capped at %d cores)",
        int(est_fps),
        min(n_envs, _CPU_COUNT),
        _FPS_PER_ENV,
        _CPU_COUNT,
    )
    logger.info("  Est. duration : ~%s (rough — selfplay is slower)", _fmt_eta(est_total_s))

    env_fns = [
        make_env(
            opponent_mode,
            shaped_reward,
            checkpoint_dir_str,
            seed=seed * 100 + i,
            mc_rollouts=mc_rollouts,
            mc_potential_reward=mc_potential_reward,
        )
        for i in range(n_envs)
    ]

    vec_env = SubprocVecEnv(env_fns)
    vec_env = VecMonitor(vec_env)

    policy_cls = TrucoActorCriticPolicy if aux_heads else "MlpPolicy"

    if load_checkpoint:
        logger.info("Loading checkpoint: %s", load_checkpoint)
        model = _load_checkpoint(load_checkpoint, vec_env, aux_heads)
    else:
        model = MaskablePPO(
            policy_cls,
            vec_env,
            n_steps=512,
            batch_size=2048,
            n_epochs=4,
            learning_rate=3e-4,
            ent_coef=0.01,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            verbose=1,
            tensorboard_log=str(LOG_DIR),
            seed=seed,
            device="auto",
            policy_kwargs=dict(net_arch=[256, 256]),
        )

    # Separate optimizer for auxiliary heads (lower LR to not disturb PPO trunk)
    aux_optimizer = (
        torch.optim.Adam(model.policy.parameters(), lr=1e-4, eps=1e-5) if aux_heads else None
    )

    label = f"truco_{opponent_mode}"
    ckpt_cb = CheckpointCallback(save_freq=checkpoint_freq, spm=None, label=label)

    # Auto-detect how many steps are already done from the checkpoint filename.
    # e.g. truco_selfplay_5000000.zip → steps_done = 5_000_000
    steps_done = _steps_from_checkpoint(load_checkpoint) if load_checkpoint else 0
    if steps_done:
        logger.info("Resuming from step %s", f"{steps_done:,}")

    t0 = time.perf_counter()

    while steps_done < total_steps:
        chunk = min(checkpoint_freq, total_steps - steps_done)
        model.learn(
            total_timesteps=chunk,
            reset_num_timesteps=(steps_done == 0),
            tb_log_name=f"MaskablePPO_{opponent_mode}",
            progress_bar=False,
        )
        steps_done += chunk

        # Auxiliary supervised update on MC-known quantities (Track B)
        if aux_heads and aux_optimizer is not None:
            aux_metrics = aux_update_step(
                model,
                steps_done,
                aux_optimizer,
                anneal_total=aux_anneal_steps,
                lambda_max=lambda_aux,
            )
            logger.info(
                "  [aux] lambda=%.4f  envido_loss=%.4f  flor_loss=%.4f",
                aux_metrics["aux/lambda"],
                aux_metrics["aux/envido_loss"],
                aux_metrics["aux/flor_loss"],
            )

        ckpt_cb(model, steps_done)

        # Log progress + ETA after each checkpoint
        elapsed = time.perf_counter() - t0
        fps = steps_done / elapsed if elapsed > 0 else 0
        remaining = total_steps - steps_done
        eta_s = remaining / fps if fps > 0 else 0
        pct = 100.0 * steps_done / total_steps
        logger.info(
            "Progress: %s / %s steps  (%.1f%%)  fps=%.0f  ETA=%s",
            f"{steps_done:,}",
            f"{total_steps:,}",
            pct,
            fps,
            _fmt_eta(eta_s),
        )
        # Self-play envs auto-resample opponents from disk at each reset() —
        # no need to rebuild SubprocVecEnv after each checkpoint.

    elapsed = time.perf_counter() - t0
    final_path = CHECKPOINT_DIR / f"{label}_final.zip"
    model.save(str(final_path))
    logger.info("Training complete in %.1fmin. Final model: %s", elapsed / 60, final_path)
    vec_env.close()


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Train Truco RL agent")
    parser.add_argument(
        "--opponents",
        choices=["threshold", "random", "selfplay"],
        default="threshold",
        help="Opponent type for training",
    )
    parser.add_argument("--steps", type=int, default=5_000_000)
    parser.add_argument("--n-envs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shaped-reward", action="store_true")
    parser.add_argument("--checkpoint-freq", type=int, default=500_000)
    parser.add_argument(
        "--load",
        type=str,
        default=None,
        help="Path to checkpoint to resume from (e.g. BC pre-trained model)",
    )
    # Track B: auxiliary prediction heads
    parser.add_argument(
        "--aux-heads",
        action="store_true",
        help="Enable auxiliary envido/flor prediction heads (Track B)",
    )
    parser.add_argument(
        "--lambda-aux",
        type=float,
        default=0.1,
        help="Initial weight for auxiliary loss (annealed to 0)",
    )
    parser.add_argument(
        "--aux-anneal-steps",
        type=int,
        default=10_000_000,
        help="Steps over which auxiliary loss weight anneals to 0",
    )
    # Track C: V_MC in observation
    parser.add_argument(
        "--mc-rollouts",
        type=int,
        default=0,
        help="Random rollouts per reset() to estimate V_MC for obs[169] (0=disabled)",
    )
    # Track D: MC potential reward
    parser.add_argument(
        "--mc-potential-reward",
        action="store_true",
        help="Use MCPotentialReward (V_MC-adjusted terminal reward) instead of sparse",
    )
    args = parser.parse_args()

    train(
        opponent_mode=args.opponents,
        total_steps=args.steps,
        n_envs=args.n_envs,
        shaped_reward=args.shaped_reward,
        seed=args.seed,
        checkpoint_freq=args.checkpoint_freq,
        load_checkpoint=args.load,
        aux_heads=args.aux_heads,
        lambda_aux=args.lambda_aux,
        aux_anneal_steps=args.aux_anneal_steps,
        mc_rollouts=args.mc_rollouts,
        mc_potential_reward=args.mc_potential_reward,
    )


if __name__ == "__main__":
    main()
