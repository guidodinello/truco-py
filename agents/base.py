from typing import Protocol, runtime_checkable

from engine.actions import Action
from engine.game_state import GameState


@runtime_checkable
class Agent(Protocol):
    """Structural interface for all Truco agents."""

    def choose_action(
        self,
        state: GameState,
        legal_actions: list[Action],
        player_idx: int,
    ) -> Action:
        """Return one action from legal_actions for player_idx."""
        ...

    def reset(self) -> None:
        """Called at the start of each new game. Override for stateful agents."""
        ...
