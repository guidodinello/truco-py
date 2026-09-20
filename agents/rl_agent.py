"""
RLAgent: wraps a trained MaskablePPO checkpoint as an Agent.

Usage:
    from agents.rl_agent import RLAgent
    agent = RLAgent("checkpoints/truco_threshold_final.zip")
    action = agent.choose_action(state, legal_actions, player_idx)
"""

from pathlib import Path

import numpy as np
from sb3_contrib import MaskablePPO

from engine.actions import N_ACTIONS, Action
from engine.game_state import GameState
from training.policy import TrucoActorCriticPolicy
from training.state_encoder import obs_to_vector


class RLAgent:
    """Trained PPO agent loaded from a checkpoint file."""

    name = "rl"

    def __init__(
        self, checkpoint_path: str | Path, deterministic: bool = True, device: str = "cpu"
    ):
        self._path = Path(checkpoint_path)
        self._deterministic = deterministic
        # Try loading with the custom policy first (checkpoints saved with --aux-heads),
        # fall back to the default policy for checkpoints saved without aux heads.
        try:
            self._model = MaskablePPO.load(
                str(self._path),
                device=device,
                custom_objects={"policy_class": TrucoActorCriticPolicy},
            )
        except RuntimeError:
            self._model = MaskablePPO.load(str(self._path), device=device)

    def choose_action(
        self,
        state: GameState,
        legal_actions: list[Action],
        player_idx: int,
    ) -> Action:
        obs = obs_to_vector(state, player_idx).reshape(1, -1)
        mask = np.zeros(N_ACTIONS, dtype=bool)
        for a in legal_actions:
            mask[a.value] = True
        action, _ = self._model.predict(
            obs,
            action_masks=mask.reshape(1, -1),
            deterministic=self._deterministic,
        )
        return Action(int(action[0]))

    def reset(self) -> None:
        pass
