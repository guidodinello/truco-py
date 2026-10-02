"""PolicyFreezeDetector against the real June-2026 collapse trace (gamekit note 011)."""

import csv
import random
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from stable_baselines3.common.callbacks import BaseCallback

from tests.helpers import tiny_model
from training.callbacks import RunCallback
from training.collapse import ABS_CLIP, ABS_ENTROPY, ABS_KL, PolicyFreezeDetector

FIXTURE = Path(__file__).parent / "fixtures" / "june_collapse.csv"


@pytest.fixture(scope="module")
def june() -> list[dict[str, float]]:
    with FIXTURE.open() as f:
        return [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]


def _first_fire(rows: list[tuple[float, float, float]]) -> int | None:
    det = PolicyFreezeDetector()
    for i, (ent, clip, kl) in enumerate(rows):
        if det.observe(ent, clip, kl):
            return i
    return None


def test_fixture_is_the_143_update_june_trace(june):
    assert len(june) == 143
    assert june[0]["total_timesteps"] == 5_709_824
    assert june[-1]["approx_kl"] == 0.0


def test_fires_on_june_collapse_well_before_everything_is_zero(june):
    rows = [(r["entropy_loss"], r["clip_fraction"], r["approx_kl"]) for r in june]
    fire = _first_fire(rows)
    assert fire is not None
    near_zero = next(
        i
        for i, (e, c, k) in enumerate(rows)
        if abs(e) < ABS_ENTROPY and abs(c) < ABS_CLIP and abs(k) < ABS_KL
    )
    lead = june[near_zero]["total_timesteps"] - june[fire]["total_timesteps"]
    assert lead >= 300_000  # note 011 gate (calibration gives ~420k)


def test_silent_on_the_healthy_prefix(june):
    healthy = [(r["entropy_loss"], r["clip_fraction"], r["approx_kl"]) for r in june[:61]]
    assert _first_fire(healthy) is None


def test_absolute_fallback_fires_without_warmup():
    det = PolicyFreezeDetector()
    assert det.observe(-1e-5, 0.0, 0.0)
    assert det.fired_reason and "absolute" in det.fired_reason


def test_negative_controls_do_not_fire():
    rng = random.Random(0)
    noisy = [(-0.17 + rng.uniform(-0.02, 0.02), 0.012 + rng.uniform(-0.004, 0.004), 1e-3)] * 200
    assert _first_fire(noisy) is None
    # slow linear sharpening: -0.28 -> -0.17 over 200 updates (catan's healthy 40% drop)
    slow = [(-0.28 + 0.11 * i / 200, 0.015, 1e-3) for i in range(200)]
    assert _first_fire(slow) is None
    # one-update dip, then recovery
    dip = [(-0.17, 0.012, 1e-3)] * 40 + [(-0.02, 0.001, 1e-3)] + [(-0.17, 0.012, 1e-3)] * 40
    assert _first_fire(dip) is None


# ── how the callback reads SB3's logger ───────────────────────────────────────


class _FakeLogger:
    def __init__(self) -> None:
        self.name_to_value: dict[str, float] = {}
        self.recorded: dict[str, float] = {}

    def record(self, key: str, value: float) -> None:
        self.recorded[key] = value


def _callback(tmp_path: Path) -> tuple[RunCallback, _FakeLogger]:
    cb = RunCallback(tmp_path / "STOP", threading.Event(), PolicyFreezeDetector())
    log = _FakeLogger()
    cb.model = SimpleNamespace(logger=log)  # type: ignore[assignment]  # BaseCallback.logger -> model.logger
    return cb, log


def test_callback_skips_first_rollout_then_flags_a_frozen_update(tmp_path):
    cb, log = _callback(tmp_path)
    cb._on_rollout_end()  # no train/* values exist before the first update
    assert not cb.frozen
    log.name_to_value.update(
        {"train/entropy_loss": -1e-5, "train/clip_fraction": 0.0, "train/approx_kl": 0.0}
    )
    cb._on_rollout_end()
    assert cb.frozen and cb.freeze_reason
    # the freeze only ends learn() at the *next* env step (SB3 cannot stop from rollout_end)
    cb.locals = {"infos": []}
    assert cb._on_step() is False


def test_callback_stops_on_stop_file_and_on_signal_event(tmp_path):
    cb, _ = _callback(tmp_path)
    cb.locals = {"infos": []}
    cb.n_calls = 1
    assert cb._on_step() is True
    (tmp_path / "STOP").touch()
    cb.n_calls = 64  # the file is polled every 64 env steps
    assert cb._on_step() is False and cb.stop_requested

    cb2, _ = _callback(tmp_path / "other")
    cb2.locals = {"infos": []}
    cb2._stop_event.set()
    assert cb2._on_step() is False


def test_callback_counts_episodes_per_opponent_role(tmp_path):
    cb, _ = _callback(tmp_path)
    cb.locals = {
        "infos": [
            {"episode": {"r": 1.0, "opp_role": 0}},
            {"episode": {"r": -1.0, "opp_role": 2}},
            {"episode": {"r": 0.5, "opp_role": 0}},
            {},
        ]
    }
    cb._on_step()
    stats = cb.role_stats()
    assert stats["threshold"] == {"episodes": 2, "mean_return": 0.75}
    assert stats["self"] == {"episodes": 1, "mean_return": -1.0}
    assert stats["random"]["episodes"] == 0


def test_sb3_exposes_previous_update_metrics_at_rollout_end():
    """Pins the SB3 ordering note 011 relies on: at ``_on_rollout_end`` of rollout k, the
    ``train/*`` values of update k-1 are recorded and not yet dumped."""

    class Spy(BaseCallback):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[bool] = []

        def _on_step(self) -> bool:
            return True

        def _on_rollout_end(self) -> None:
            self.seen.append("train/entropy_loss" in self.logger.name_to_value)

    model = tiny_model(n_steps=32, batch_size=32, n_epochs=1)
    spy = Spy()
    model.learn(total_timesteps=32 * 4, callback=spy)
    assert spy.seen == [False, True, True, True]
