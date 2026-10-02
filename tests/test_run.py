"""The chunked, resumable run loop (exp 009): complete, resume, clean stop, refusal cases."""

import dataclasses
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from engine.actions import N_ACTIONS
from tests.helpers import save_old_checkpoint, tiny_model
from training.config import ROOT, OpponentMix, TrainConfig, snapshot_name
from training.run import EXIT_OK, _parser, config_from_args, run

N_ENVS, N_STEPS = 2, 512  # one rollout = 1024 env steps


def _cfg(tmp_path: Path, init: Path, run_id: str = "t", **kw) -> TrainConfig:
    base = dict(
        run_id=run_id,
        init_checkpoint=init,
        total_steps=2048,
        n_envs=N_ENVS,
        checkpoint_every=1024,
        snapshot_every=1024,
        eval_every=2048,
        eval_n=2,
        device="cpu",
        vec_env="dummy",
        inference="local",
        runs_root=tmp_path / "runs",
        seed=1,
    )
    return TrainConfig(**{**base, **kw})


@pytest.fixture(scope="module")
def init(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("bc") / "bc_init.zip"
    tiny_model().save(str(path))
    return path


def _state(cfg: TrainConfig) -> dict:
    return json.loads(cfg.run_json.read_text())


def test_run_completes_then_resumes_with_a_continuous_step_count(tmp_path, init):
    cfg = _cfg(tmp_path, init)
    assert run(cfg) == EXIT_OK
    s1 = _state(cfg)
    assert s1["status"] == "complete" and s1["num_timesteps"] >= 2048
    assert s1["config"]["opponent_mix"] == "thr=0.4,rand=0.2,self=0.4"
    assert s1["git_commit"] and "gamekit_commit" in s1

    pool = sorted(p.name for p in cfg.pool_dir.glob("snap_*.zip"))
    assert pool[0] == snapshot_name(0), "the BC init seeds the pool"
    assert len(pool) >= 2, "snapshots are published every snapshot_every steps"
    assert list(cfg.eval_dir.glob("eval_*.json")), "in-loop eval wrote its Wilson-stamped JSON"
    ev = json.loads(next(cfg.eval_dir.glob("eval_*.json")).read_text())
    assert {"threshold", "random"} <= set(ev) and len(ev["threshold"]["wilson95"]) == 2

    cfg2 = dataclasses.replace(cfg, total_steps=3072)
    assert run(cfg2, resume=True) == EXIT_OK
    s2 = _state(cfg2)
    assert s2["status"] == "complete"
    assert s2["num_timesteps"] > s1["num_timesteps"] and s2["num_timesteps"] >= 3072
    steps = [int(p.stem.split("_")[1]) for p in sorted(cfg.ckpt_dir.glob("ckpt_*.zip"))]
    assert steps == sorted(steps) and steps[-1] == s2["num_timesteps"]


def test_fresh_run_refuses_to_clobber_and_needs_an_init(tmp_path, init):
    cfg = _cfg(tmp_path, init, total_steps=1024)
    run(cfg)
    with pytest.raises(RuntimeError, match="--resume"):
        run(cfg)
    with pytest.raises(RuntimeError, match="--init"):
        run(_cfg(tmp_path, init, run_id="u", init_checkpoint=None))


def test_a_pre_26_init_checkpoint_is_refused(tmp_path):
    old = save_old_checkpoint(tmp_path / "old.zip")
    with pytest.raises(ValueError, match=f"53 actions, engine has {N_ACTIONS}"):
        run(_cfg(tmp_path, old))


def test_resume_cli_rejects_changed_experiment_variables(tmp_path, init):
    cfg = _cfg(tmp_path, init, total_steps=1024)
    run(cfg)
    base = ["--run-id", "t", "--runs-root", str(cfg.runs_root), "--resume"]
    ok = config_from_args(_parser().parse_args([*base, "--steps", "4096"]))
    assert ok.total_steps == 4096 and ok.opponent_mix == cfg.opponent_mix and ok.seed == 1
    for flag, value in (("--lr", "3e-4"), ("--ent-coef", "0.05"), ("--partners", "threshold")):
        with pytest.raises(RuntimeError, match="changed across --resume"):
            config_from_args(_parser().parse_args([*base, flag, value]))


def test_opponent_mix_validation():
    assert OpponentMix.parse("thr=0.5,rand=0.1,self=0.4").weights == (0.5, 0.1, 0.4)
    with pytest.raises(ValueError, match="sum to 1"):
        OpponentMix(0.5, 0.5, 0.5)
    with pytest.raises(ValueError):
        OpponentMix.parse("thr=1.0")


def test_cadences_must_align(tmp_path, init):
    with pytest.raises(ValueError, match="multiple of checkpoint_every"):
        _cfg(tmp_path, init, snapshot_every=1500)


def test_touch_stop_checkpoints_and_exits_cleanly_then_resume_continues(tmp_path, init):
    """The real thing, in a subprocess: ``touch STOP`` mid-run -> exit 0 + status 'stopped';
    ``--resume`` picks up at the saved step count."""
    runs = tmp_path / "runs"
    common = ["--run-id", "s", "--runs-root", str(runs), "--device", "cpu", "--vec-env", "dummy"]
    run_dir = runs / "s"
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "training.run", *common,
            "--init", str(init), "--n-envs", "2", "--steps", "102400000",
            "--checkpoint-every", "1024", "--snapshot-every", "1024",
            "--eval-every", "102400000", "--eval-n", "2", "--inference", "local",
        ],
        cwd=ROOT,
    )  # fmt: skip
    try:
        deadline = time.time() + 180
        while time.time() < deadline and len(list((run_dir / "ckpt").glob("ckpt_*.zip"))) < 2:
            assert proc.poll() is None, "run died before producing checkpoints"
            time.sleep(0.5)
        (run_dir / "STOP").touch()
        assert proc.wait(timeout=120) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
    stopped = json.loads((run_dir / "run.json").read_text())
    assert stopped["status"] == "stopped" and stopped["num_timesteps"] >= 2048
    assert not (run_dir / "run.pid").exists()

    target = stopped["num_timesteps"] + 2048
    done = subprocess.run(
        [sys.executable, "-m", "training.run", *common, "--resume", "--steps", str(target),
         "--inference", "local"],
        cwd=ROOT, timeout=300, check=False,
    )  # fmt: skip
    assert done.returncode == 0
    final = json.loads((run_dir / "run.json").read_text())
    assert final["status"] == "complete" and final["num_timesteps"] >= target
