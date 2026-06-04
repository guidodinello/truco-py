"""
SelfPlayManager: maintains a rolling pool of past checkpoints used as opponents.

When the pool is empty (early training), falls back to ThresholdAgent.
"""

import random
from collections import deque

from agents.base import Agent
from agents.threshold_agent import ThresholdAgent

# Process-local cache: {path -> MaskablePPO model}.
# Each SubprocVecEnv worker loads each checkpoint at most once, then serves
# from memory. Safe because subprocesses are forked and share no state.
_MODEL_CACHE: dict = {}


class _CheckpointAgent:
    """Loads a MaskablePPO checkpoint lazily and wraps it as an Agent."""

    def __init__(self, checkpoint_path: str):
        self._path = checkpoint_path

    def _load(self):
        if self._path not in _MODEL_CACHE:
            from sb3_contrib import MaskablePPO

            # Force CPU: checkpoint agents run inside subprocess workers where
            # CUDA initialization can deadlock with PyTorch's multiprocessing fork.
            _MODEL_CACHE[self._path] = MaskablePPO.load(self._path, device="cpu")

    def choose_action(self, state, legal_actions, player_idx):
        import numpy as np

        from engine.actions import N_ACTIONS, Action
        from training.state_encoder import obs_to_vector

        self._load()
        obs = obs_to_vector(state, player_idx).reshape(1, -1)
        model = _MODEL_CACHE[self._path]
        mask = np.zeros(N_ACTIONS, dtype=bool)
        for a in legal_actions:
            mask[a.value] = True

        action, _ = model.predict(obs, action_masks=mask.reshape(1, -1), deterministic=False)
        return Action(int(action[0]))

    def reset(self):
        pass


class SelfPlayManager:
    """
    Maintains a deque of recent checkpoints (pool_size most recent).
    Opponents are sampled uniformly from the pool.
    Falls back to ThresholdAgent when pool is empty.
    """

    def __init__(self, checkpoint_dir: str, pool_size: int = 5, seed: int = 42):
        self._dir = checkpoint_dir
        self._pool: deque[str] = deque(maxlen=pool_size)
        self._rng = random.Random(seed)

    def add_checkpoint(self, path: str):
        self._pool.append(path)

    def sample_opponent(self) -> Agent:
        if not self._pool:
            return ThresholdAgent()
        path = self._rng.choice(list(self._pool))
        return _CheckpointAgent(path)

    def __len__(self):
        return len(self._pool)
