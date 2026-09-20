import random

from engine.actions import Action
from engine.game_state import GameState


class RandomAgent:
    """Chooses uniformly at random from legal actions."""

    name = "random"

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def reset(self) -> None:
        pass

    def choose_action(
        self,
        state: GameState,
        legal_actions: list[Action],
        player_idx: int,
    ) -> Action:
        return self._rng.choice(legal_actions)
