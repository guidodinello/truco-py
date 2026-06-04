"""
MC lookup tables derived from Monte Carlo simulation results.

Provides win-probability estimates for envido and flor sub-games,
indexed by score. Used to generate auxiliary prediction labels for
the RL agent's representation learning.

Tables are loaded once at module import from the results/ directory.
All entries default to 0.5 (neutral prior) for scores with no data.
"""

import re
from pathlib import Path

import numpy as np

_RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
_ENVIDO_FILE = _RESULTS_DIR / "envido_1v1_n1000000_seed42.txt"
_FLOR_FILE = _RESULTS_DIR / "flor_decision_1v1_n1000000_seed42.txt"

# P(win envido 1v1 | my_envido == Y), indexed by score Y in [0, 37].
# Scores 8–19 are structurally impossible in Truco; they stay at 0.5.
ENVIDO_WIN_PROB: np.ndarray = np.full(38, 0.5, dtype=np.float32)

# P(win flor 1v1 | my_flor == X), indexed by score X in [0, 47].
# Scores below 20 are impossible; they stay at 0.5.
FLOR_WIN_PROB: np.ndarray = np.full(48, 0.5, dtype=np.float32)

_ROW_RE = re.compile(r"^\s*(\d+)\s+[\d,]+\s+([\d.]+)%")


def _load_table(filepath: Path, table: np.ndarray, max_score: int) -> None:
    """Parse a result text file and fill `table` in-place."""
    if not filepath.exists():
        return
    with open(filepath) as f:
        for line in f:
            m = _ROW_RE.match(line)
            if not m:
                continue
            score = int(m.group(1))
            prob = float(m.group(2)) / 100.0
            if 0 <= score <= max_score:
                table[score] = prob


_load_table(_ENVIDO_FILE, ENVIDO_WIN_PROB, 37)
_load_table(_FLOR_FILE, FLOR_WIN_PROB, 47)


# ── Label helpers ────────────────────────────────────────────────────────────


def envido_label_from_obs(obs: np.ndarray) -> np.ndarray:
    """
    Compute P(win envido 1v1) labels from a batch of observations.

    Parameters
    ----------
    obs : np.ndarray, shape (N, 204)

    Returns
    -------
    np.ndarray, shape (N,), float32
        MC-derived win probability for each observation.
    """
    scores = np.round(obs[:, 133] * 37.0).astype(np.int32).clip(0, 37)
    return ENVIDO_WIN_PROB[scores]


def flor_label_from_obs(obs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute P(win flor 1v1) labels and a validity mask from a batch of observations.

    Only observations where the training agent has flor (obs[:, 134] > 0) are valid;
    the rest should be excluded from the flor auxiliary loss.

    Parameters
    ----------
    obs : np.ndarray, shape (N, 204)

    Returns
    -------
    labels : np.ndarray, shape (N,), float32
    valid_mask : np.ndarray, shape (N,), bool
        True where the agent has flor and the label is meaningful.
    """
    has_flor = obs[:, 134] > 1e-6
    scores = np.round(obs[:, 134] * 47.0).astype(np.int32).clip(0, 47)
    labels = FLOR_WIN_PROB[scores]
    return labels, has_flor
