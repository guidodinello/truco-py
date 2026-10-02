"""
Experiment-009 training entry point: chunked, resumable PPO against a mixed, run-scoped
opponent pool, with in-loop seat-rotated eval and a policy-freeze detector.

    python -m training.run --run-id m1 --init runs/009/bc/bc_init.zip \\
        --context-bank runs/009/bc/context_bank.npz --opponent-mix thr=0.4,rand=0.2,self=0.4
    python -m training.run --run-id m1 --resume            # continue after a stop / shutdown
    touch runs/009/m1/STOP                                  # clean stop (checkpoint, then exit 0)

Exit codes: 0 finished or cleanly stopped, 3 policy-freeze detector fired (``ckpt/freeze_*.zip``).
Everything a run writes lives under ``cfg.run_dir`` and ``cfg.pool_dir`` (see training/config.py).
"""

import argparse
import contextlib
import dataclasses
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from importlib import metadata
from pathlib import Path
from typing import Any

import torch
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecEnv, VecMonitor

from agents.rl_agent import check_action_space
from log import get_logger
from training.callbacks import RunCallback
from training.collapse import PolicyFreezeDetector
from training.config import (
    DEFAULT_RUNS_ROOT,
    IMMUTABLE_ON_RESUME,
    ROOT,
    OpponentMix,
    TrainConfig,
    snapshot_name,
)
from training.context_bank import ContextBank
from training.env import TrucoEnv
from training.eval import ModelAgent, eval_matches
from training.inference_server import InferenceServer
from training.pool import TeamOpponentPool
from training.reward import PointDiffReward, SparseReward
from training.self_play import _CheckpointAgent

EXIT_OK = 0
EXIT_FROZEN = 3

# PPO hyper-parameters that are not experiment variables (unchanged from exp 003/005).
PPO_KWARGS: dict[str, Any] = dict(
    n_steps=512, batch_size=2048, n_epochs=4, gamma=0.99, gae_lambda=0.95, clip_range=0.2
)


# ── provenance ────────────────────────────────────────────────────────────────


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def gamekit_commit() -> str:
    try:
        raw = metadata.distribution("gamekit").read_text("direct_url.json")
        return json.loads(raw)["vcs_info"]["commit_id"] if raw else "unknown"
    except (metadata.PackageNotFoundError, KeyError, ValueError):
        return "unknown"


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


# ── env / model construction ──────────────────────────────────────────────────


def make_env(cfg: TrainConfig, rank: int, handle: Any):
    """Factory for one masked TrucoEnv; runs inside the worker process."""

    def _init():
        if cfg.vec_env == "subproc":
            # Workers are single-threaded: 16 workers x 14 torch threads thrashes the cores.
            torch.set_num_threads(1)
        bank = ContextBank.load(cfg.context_bank) if cfg.context_bank else None
        reward = PointDiffReward(cfg.reward_scale) if cfg.reward == "diff" else SparseReward()
        pool = TeamOpponentPool(
            cfg.pool_root,
            run_id=cfg.run_id,
            mix=cfg.opponent_mix,
            partners=cfg.partners,
            load_opponent=lambda path: _CheckpointAgent(str(path), inference_handle=handle),
            seed=cfg.seed * 1000 + rank,
        )
        env = TrucoEnv(
            opponent_pool=pool,
            reward_shaper=reward,
            seed=cfg.seed * 100 + rank,
            context_bank=bank,
        )
        return ActionMasker(env, lambda e: e.action_masks())

    return _init


def build_vec_env(cfg: TrainConfig, server: InferenceServer | None) -> VecEnv:
    fns = [
        make_env(cfg, i, server.make_handle(i) if server is not None else None)
        for i in range(cfg.n_envs)
    ]
    if cfg.vec_env == "dummy":
        vec: VecEnv = DummyVecEnv(fns)
    else:
        # fork so workers inherit the pipes to the inference server (see inference_server.py)
        vec = SubprocVecEnv(fns, start_method="fork" if server is not None else None)
    return VecMonitor(vec, info_keywords=("opp_role",))


def build_model(cfg: TrainConfig, vec_env: VecEnv, resume_from: Path | None, steps: int):
    common: dict[str, Any] = dict(
        env=vec_env, device=cfg.device, tensorboard_log=str(cfg.tb_dir), verbose=1
    )
    if resume_from is not None:
        # Saved hyper-parameters, optimizer state and num_timesteps all come back from the zip;
        # only the env seed moves, so a resume doesn't replay the run's first episodes.
        model = MaskablePPO.load(resume_from, seed=cfg.seed + steps, **common)
        check_action_space(model, resume_from)
        return model
    assert cfg.init_checkpoint is not None
    model = MaskablePPO.load(
        cfg.init_checkpoint,
        seed=cfg.seed,
        learning_rate=cfg.learning_rate,
        ent_coef=cfg.ent_coef,
        **PPO_KWARGS,
        **common,
    )
    check_action_space(model, cfg.init_checkpoint)
    return model


# ── snapshots ─────────────────────────────────────────────────────────────────


def write_snapshot(
    model: MaskablePPO | Path, step: int, cfg: TrainConfig, server: InferenceServer | None
) -> Path:
    """Atomically publish a pool snapshot: save under a name the pool glob ignores, register it
    with the inference server under its final name, then rename it into the pool. A worker can
    therefore never sample a half-written or unregistered file."""
    cfg.pool_dir.mkdir(parents=True, exist_ok=True)
    final = cfg.pool_dir / snapshot_name(step)
    tmp = cfg.pool_dir / f".tmp_{step}.zip"
    if isinstance(model, Path):
        shutil.copyfile(model, tmp)
    else:
        model.save(str(tmp))
    if server is not None:
        server.update_model(str(tmp), key=str(final))
    else:
        check_action_space(MaskablePPO.load(tmp, device="cpu"), tmp)
    os.replace(tmp, final)
    return final


# ── in-loop eval (alarm only) ─────────────────────────────────────────────────


def run_eval(model: MaskablePPO, cfg: TrainConfig, step: int, logger) -> dict[str, Any]:
    agent = ModelAgent(model, deterministic=True)
    out: dict[str, Any] = {"step": step, "n": cfg.eval_n, "git_commit": git_commit()}
    for opponent in ("threshold", "random"):
        t0 = time.perf_counter()
        payload = eval_matches(agent, opponent, cfg.eval_n, seed=cfg.seed + 777)
        ci = payload["by_role"]["rl"]["win_rate_wilson_ci"]
        out[opponent] = {
            "wins": payload["rl_wins"],
            "win_rate": payload["rl_win_rate"],
            "wilson95": ci,
        }
        model.logger.record(f"eval/winrate_{opponent}", payload["rl_win_rate"])
        logger.info(
            "eval %s: %d/%d = %.1f%% [%.1f, %.1f]  (%.0fs, alarm only)",
            opponent,
            payload["rl_wins"],
            cfg.eval_n,
            100 * payload["rl_win_rate"],
            100 * ci[0],
            100 * ci[1],
            time.perf_counter() - t0,
        )
    cfg.eval_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(cfg.eval_dir / f"eval_{step:010d}.json", out)
    model.logger.dump(step)
    return out


# ── run state ─────────────────────────────────────────────────────────────────


def latest_checkpoint(cfg: TrainConfig) -> Path | None:
    ckpts = sorted(cfg.ckpt_dir.glob("ckpt_*.zip"))
    return ckpts[-1] if ckpts else None


def write_run_state(cfg: TrainConfig, status: str, model: MaskablePPO | None, **extra: Any) -> None:
    prev = json.loads(cfg.run_json.read_text()) if cfg.run_json.exists() else {}
    state = {
        **prev,
        "config": cfg.to_json(),
        "status": status,
        "num_timesteps": int(model.num_timesteps) if model is not None else 0,
        "git_commit": git_commit(),
        "gamekit_commit": gamekit_commit(),
        "updated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        **extra,
    }
    write_json_atomic(cfg.run_json, state)


def _next_boundary(steps: int, every: int) -> int:
    return (steps // every + 1) * every


# ── main loop ─────────────────────────────────────────────────────────────────


def run(cfg: TrainConfig, resume: bool = False) -> int:
    cfg.run_dir.mkdir(parents=True, exist_ok=True)
    for d in (cfg.ckpt_dir, cfg.eval_dir, cfg.tb_dir, cfg.pool_dir):
        d.mkdir(parents=True, exist_ok=True)
    logger = get_logger(f"train.{cfg.run_id}", cfg.log_path)

    resume_from = latest_checkpoint(cfg) if resume else None
    if resume and resume_from is None:
        raise RuntimeError(f"--resume: no checkpoint in {cfg.ckpt_dir}")
    if not resume:
        if cfg.run_json.exists():
            raise RuntimeError(f"{cfg.run_json} exists: pass --resume or choose a new --run-id")
        if cfg.init_checkpoint is None:
            raise RuntimeError("a fresh run needs --init (the BC checkpoint)")
    if cfg.stop_file.exists():
        logger.info("removing stale %s", cfg.stop_file)
        cfg.stop_file.unlink()
    (cfg.run_dir / "run.pid").write_text(str(os.getpid()))

    logger.info("run %s  resume=%s  config=%s", cfg.run_id, resume, json.dumps(cfg.to_json()))

    server: InferenceServer | None = None
    if cfg.use_inference_server:
        server = InferenceServer(n_envs=cfg.n_envs, device=cfg.inference)
        for snap in sorted(cfg.pool_dir.glob("snap_*.zip")):
            server.update_model(str(snap))  # resume: re-register what is already in the pool

    if not resume:
        assert cfg.init_checkpoint is not None
        write_snapshot(cfg.init_checkpoint, 0, cfg, server)  # snap_0 = the BC init
        logger.info("seeded pool with %s", snapshot_name(0))

    vec_env = build_vec_env(cfg, server)
    steps0 = 0
    if resume_from is not None:
        steps0 = int(json.loads(cfg.run_json.read_text()).get("num_timesteps", 0))
    model = build_model(cfg, vec_env, resume_from, steps0)
    steps0 = int(model.num_timesteps)
    logger.info("start at %s steps (device=%s)", f"{steps0:,}", model.device)
    write_run_state(cfg, "running", model, resumed_from=str(resume_from) if resume_from else None)

    stop_event = threading.Event()

    def _on_signal(signum: int, _frame: Any) -> None:
        logger.info("signal %d: finishing the current rollout, then checkpointing", signum)
        stop_event.set()
        signal.signal(signum, signal.SIG_DFL)  # a second signal kills immediately

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    cb = RunCallback(cfg.stop_file, stop_event, PolicyFreezeDetector())
    exit_code = EXIT_OK
    status = "running"
    last_snap = model.num_timesteps // cfg.snapshot_every
    last_eval = model.num_timesteps // cfg.eval_every
    try:
        while model.num_timesteps < cfg.total_steps:
            target = min(_next_boundary(model.num_timesteps, cfg.checkpoint_every), cfg.total_steps)
            t0, s0 = time.perf_counter(), model.num_timesteps
            model.learn(
                total_timesteps=target - model.num_timesteps,
                reset_num_timesteps=False,
                tb_log_name=cfg.run_id,
                callback=cb,
                progress_bar=False,
            )
            step = int(model.num_timesteps)
            fps = (step - s0) / max(time.perf_counter() - t0, 1e-9)

            if cb.frozen:
                path = cfg.ckpt_dir / f"freeze_{step:010d}.zip"
                model.save(str(path))
                logger.error(
                    "policy-freeze detector fired at %s: %s", f"{step:,}", cb.freeze_reason
                )
                status, exit_code = "frozen", EXIT_FROZEN
                write_run_state(cfg, status, model, freeze_reason=cb.freeze_reason)
                break

            path = cfg.ckpt_dir / f"ckpt_{step:010d}.zip"
            model.save(str(path))
            if step // cfg.snapshot_every > last_snap:
                last_snap = step // cfg.snapshot_every
                write_snapshot(model, step, cfg, server)
                logger.info("snapshot %s published", snapshot_name(step))
            eval_out = None
            if step // cfg.eval_every > last_eval and not cb.stop_requested:
                last_eval = step // cfg.eval_every
                eval_out = run_eval(model, cfg, step, logger)
            logger.info(
                "step %s / %s  fps=%.0f  roles=%s",
                f"{step:,}",
                f"{cfg.total_steps:,}",
                fps,
                json.dumps(cb.role_stats()),
            )
            write_run_state(
                cfg,
                "running",
                model,
                latest_checkpoint=str(path),
                fps_last_chunk=fps,
                roles=cb.role_stats(),
                **({"last_eval": eval_out} if eval_out else {}),
            )
            if cb.stop_requested:
                status = "stopped"
                logger.info("clean stop at %s steps; resume with --resume", f"{step:,}")
                break
        else:
            status = "complete"
            logger.info("complete at %s steps", f"{int(model.num_timesteps):,}")
        if status in ("stopped", "complete"):
            write_run_state(cfg, status, model, roles=cb.role_stats())
    finally:
        vec_env.close()
        if server is not None:
            server.stop()
        with contextlib.suppress(OSError):
            (cfg.run_dir / "run.pid").unlink()
    return exit_code


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    S = argparse.SUPPRESS  # only explicitly-passed flags land in the namespace
    p = argparse.ArgumentParser(description="Experiment 009: resumable PPO vs a mixed pool")
    p.add_argument("--run-id", required=True)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--init", dest="init_checkpoint", type=Path, default=S)
    p.add_argument("--steps", dest="total_steps", type=int, default=S)
    p.add_argument("--n-envs", type=int, default=S)
    p.add_argument("--seed", type=int, default=S)
    p.add_argument("--lr", dest="learning_rate", type=float, default=S)
    p.add_argument("--ent-coef", type=float, default=S)
    p.add_argument(
        "--opponent-mix", type=OpponentMix.parse, default=S, help="thr=0.4,rand=0.2,self=0.4"
    )
    p.add_argument("--partners", choices=["snapshot", "threshold", "pool"], default=S)
    p.add_argument("--reward", choices=["sign", "diff"], default=S)
    p.add_argument("--reward-scale", type=float, default=S)
    p.add_argument("--context-bank", type=Path, default=S)
    p.add_argument("--checkpoint-every", type=int, default=S)
    p.add_argument("--snapshot-every", type=int, default=S)
    p.add_argument("--eval-every", type=int, default=S)
    p.add_argument("--eval-n", type=int, default=S)
    p.add_argument("--device", default=S)
    p.add_argument("--vec-env", choices=["subproc", "dummy"], default=S)
    p.add_argument("--inference", choices=["cpu", "cuda", "local"], default=S)
    p.add_argument("--runs-root", type=Path, default=S)
    return p


def config_from_args(args: argparse.Namespace) -> TrainConfig:
    given = {k: v for k, v in vars(args).items() if k != "resume"}
    run_id = given["run_id"]
    runs_root = given.get("runs_root", DEFAULT_RUNS_ROOT)
    if not args.resume:
        return TrainConfig(**given)
    run_json = runs_root / run_id / "run.json"
    if not run_json.exists():
        raise RuntimeError(f"--resume: {run_json} not found")
    saved = TrainConfig.from_json(json.loads(run_json.read_text())["config"])
    for name in IMMUTABLE_ON_RESUME:
        if name in given and given[name] != getattr(saved, name):
            raise RuntimeError(
                f"--{name.replace('_', '-')} changed across --resume "
                f"({getattr(saved, name)!r} -> {given[name]!r}); start a new run instead"
            )
    return dataclasses.replace(saved, **{k: v for k, v in given.items() if k != "run_id"})


def main() -> None:
    args = _parser().parse_args()
    raise SystemExit(run(config_from_args(args), resume=args.resume))


if __name__ == "__main__":
    main()
