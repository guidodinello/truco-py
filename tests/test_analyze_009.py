"""The exp 009 verdict ladder on synthetic results (scripts/analyze_009.py)."""

import json
from pathlib import Path

import pytest

from scripts.analyze_009 import analyze

N = 4000
JOBS = {  # job -> (role, rate)
    "M20M_vs_thr": ("rl", 0.90),
    "C20M_vs_thr": ("rl", 0.90),
    "M20M_vs_vn": ("rl", 0.60),
    "C20M_vs_vn": ("rl", 0.60),
    "M20M_vs_rnd": ("rl", 0.90),
    "C20M_vs_rnd": ("rl", 0.90),
    "bc_vs_thr": ("rl", 0.40),
    "bc_vs_vn": ("rl", 0.50),
    "bc_vs_rnd": ("rl", 0.80),
    "M10M_vs_thr": ("rl", 0.88),
    "M5M_vs_thr": ("rl", 0.85),
    "M10M_vs_rnd": ("rl", 0.88),
    "M5M_vs_rnd": ("rl", 0.85),
    "baseline_thr_vs_rnd": ("threshold", 0.87),
    "baseline_thr_vs_vn": ("threshold", 0.65),
}


def _write(results: Path, overrides: dict[str, float]) -> None:
    results.mkdir(parents=True, exist_ok=True)
    for job, (role, rate) in JOBS.items():
        rate = overrides.get(job, rate)
        wins = round(rate * N)
        body = {"by_role": {role: {"wins": wins, "n_seat_occupancies": N}}, "voided_hands": 0}
        (results / f"{job}.json").write_text(json.dumps(body))


def _verdict(tmp_path: Path, **overrides: float) -> str:
    _write(tmp_path / "r", overrides)
    (tmp_path / "runs" / "M" / "ckpt").mkdir(parents=True)
    (tmp_path / "runs" / "C" / "ckpt").mkdir(parents=True)
    return analyze(tmp_path / "r", tmp_path / "runs")["verdict"]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"M20M_vs_vn": 0.70}, "2. Generalises"),
        ({"M20M_vs_vn": 0.70, "M20M_vs_thr": 0.80}, "3. Generalises with trade-off"),
        ({"C20M_vs_vn": 0.70}, "4. Control better"),
        ({}, "5. Inconclusive"),
    ],
)
def test_ladder(tmp_path, overrides, expected):
    assert _verdict(tmp_path, **overrides) == expected


def test_a_freeze_checkpoint_is_rung_one(tmp_path):
    _write(tmp_path / "r", {"M20M_vs_vn": 0.70})
    (tmp_path / "runs" / "M" / "ckpt").mkdir(parents=True)
    (tmp_path / "runs" / "C" / "ckpt").mkdir(parents=True)
    (tmp_path / "runs" / "C" / "ckpt" / "freeze_0000000100.zip").touch()
    assert analyze(tmp_path / "r", tmp_path / "runs")["verdict"] == "1. Collapsed"
