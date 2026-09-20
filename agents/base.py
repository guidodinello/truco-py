"""The ``Agent`` protocol.

Extracted to ``gamekit.agent.Agent[StateT, ActionT]`` -- see
``~/projects/docs/shared-ml-package.md``. ``TrucoAgent`` is the parameterised alias
this codebase's annotations use; ``isinstance`` checks stay against the bare ``Agent``
re-exported below (a subscripted generic Protocol raises ``TypeError`` from
``isinstance``), which is what ``tests/test_agents.py`` already does.
"""

from __future__ import annotations

from gamekit import Agent as Agent

from engine.actions import Action
from engine.game_state import GameState

type TrucoAgent = Agent[GameState, Action]
