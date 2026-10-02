"""Small builders shared by the exp-009 training tests."""

from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.vec_env import DummyVecEnv

from training.env import TrucoEnv
from training.state_encoder import OBS_DIM


def _masked_env(seed: int) -> ActionMasker:
    env = TrucoEnv(seed=seed)
    return ActionMasker(env, lambda _: env.action_masks())


def tiny_model(seed: int = 0, **kwargs) -> MaskablePPO:
    """A CPU MaskablePPO on the real 65-action TrucoEnv (cheap to build and save)."""
    env = DummyVecEnv([lambda: _masked_env(seed)])
    return MaskablePPO(
        "MlpPolicy",
        env,
        device="cpu",
        seed=seed,
        verbose=0,
        policy_kwargs=dict(net_arch=[32, 32]),
        **kwargs,
    )


class _OldEnv(gym.Env):
    """A stand-in for the pre-#26 engine: 53 actions."""

    observation_space = spaces.Box(0.0, 1.0, (OBS_DIM,), np.float32)
    action_space = spaces.Discrete(53)

    def reset(self, *, seed=None, options=None):
        return np.zeros(OBS_DIM, np.float32), {}

    def step(self, action):
        return np.zeros(OBS_DIM, np.float32), 0.0, True, False, {}


def save_old_checkpoint(path: Path) -> Path:
    """Save a 53-action checkpoint, exactly what every pre-#26 file on disk is."""
    MaskablePPO("MlpPolicy", _OldEnv(), device="cpu", verbose=0).save(str(path))
    return path
