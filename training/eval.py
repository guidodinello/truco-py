"""
Seat-rotated match evaluation shared by ``scripts/benchmark.py`` (final n>=4000 benchmarks),
the in-loop eval callback (n~200, an *alarm only* -- gamekit#009) and the league manifest.

A gamekit "seat" here is a *team slot* (0 = Team A's players 0/2/4, 1 = Team B's 1/3/5);
``run_arm`` rotates which role occupies which slot, so every role plays both sides.
"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from gamekit.benchmark import run_arm
from gamekit.seats import rotate
from sb3_contrib import MaskablePPO

from agents.base import TrucoAgent
from agents.random_agent import RandomAgent
from agents.rl_agent import RLAgent
from agents.threshold_agent import ThresholdAgent
from engine.actions import N_ACTIONS, Action
from engine.game_state import TEAM_A, TEAM_B, GameState
from engine.match import TrucoMatch
from training.state_encoder import obs_to_vector

# Every call ladder is bounded, so a hand over this cap is an engine liveness bug.
MAX_ACTIONS_PER_HAND = 2000

_SLOT_PLAYERS = (TEAM_A, TEAM_B)


def run_match(match: TrucoMatch, agents: list, seed: int | None = None) -> int:
    """Play a full match (chicos, mano rotation, redondilla / pico a pico).
    Returns 0 if team A wins, 1 if team B wins."""
    ms = match.reset(seed=seed)
    hand, n_actions = ms.hand, 0
    while not match.is_terminal(ms):
        cp = ms.hand.current_player
        legal = match.legal_actions(ms)
        action = agents[cp].choose_action(ms.hand, legal, cp)
        match.apply_action(ms, action)
        n_actions = n_actions + 1 if ms.hand is hand else 0
        hand = ms.hand
        if n_actions > MAX_ACTIONS_PER_HAND:
            raise RuntimeError(f"hand exceeded {MAX_ACTIONS_PER_HAND} actions: engine liveness bug")
    return ms.winner


def place_agents(
    rotated_lineup: Sequence[str], role_agents: dict[str, list[TrucoAgent]]
) -> list[TrucoAgent]:
    """Map a rotated (slot -> role) lineup to the 6 players: slot 0 is Team A's 3 players,
    slot 1 is Team B's, each in mano order."""
    player_to_agent: dict[int, TrucoAgent] = {}
    for slot, role in enumerate(rotated_lineup):
        for pos_idx, player in enumerate(_SLOT_PLAYERS[slot]):
            player_to_agent[player] = role_agents[role][pos_idx]
    return [player_to_agent[p] for p in range(6)]


class ModelAgent:
    """A loaded/live ``MaskablePPO`` as an Agent (``RLAgent`` for models already in memory)."""

    name = "rl"

    def __init__(self, model: MaskablePPO, deterministic: bool = True) -> None:
        self._model = model
        self._deterministic = deterministic

    def choose_action(
        self, state: GameState, legal_actions: list[Action], player_idx: int
    ) -> Action:
        obs = obs_to_vector(state, player_idx).reshape(1, -1)
        mask = np.zeros(N_ACTIONS, dtype=bool)
        for a in legal_actions:
            mask[a.value] = True
        action, _ = self._model.predict(
            obs, action_masks=mask.reshape(1, -1), deterministic=self._deterministic
        )
        return Action(int(action[0]))

    def reset(self) -> None:
        pass


def _opponent_triplet(opponent: str, seed: int) -> list[TrucoAgent]:
    offsets = (1, 3, 5)  # the opponent is always "role_b": the seeds Team B always used
    if opponent == "threshold":
        return [ThresholdAgent(seed=seed + o) for o in offsets]
    if opponent == "random":
        return [RandomAgent(seed=seed + o) for o in offsets]
    raise ValueError(f"in-loop eval supports threshold/random, got {opponent!r}")


def eval_matches(agent: TrucoAgent, opponent: str, n: int, seed: int) -> dict[str, Any]:
    """``n`` full matches of ``agent`` (3 copies) vs 3 copies of ``opponent``, seat-rotated.

    Returns the stamped ``run_arm`` payload (``by_role[...]["win_rate_wilson_ci"]`` etc.) plus
    ``rl_wins`` / ``n`` / ``rl_win_rate`` for convenience. ``n`` must be even."""
    lineup = ("rl", opponent)
    role_agents: dict[str, list[TrucoAgent]] = {
        "rl": [agent, agent, agent],
        opponent: _opponent_triplet(opponent, seed),
    }
    match = TrucoMatch()

    def play(pairs: Sequence[tuple[int, int]]) -> Sequence[int | None]:
        winners: list[int | None] = []
        for engine_seed, _driver_seed in pairs:
            rotated = rotate(lineup, engine_seed)
            winners.append(run_match(match, place_agents(rotated, role_agents), seed=engine_seed))
        return winners

    payload = run_arm(
        lineup=lineup,
        num_seats=2,
        n_games=n,
        engine_seed_base=seed,
        driver_seed_base=seed,
        play=play,
        winning_seat=lambda r: r,
    )
    wins = payload["by_role"]["rl"]["wins"]
    payload.update(opponent=opponent, rl_wins=wins, n=n, rl_win_rate=wins / n)
    return payload


# ── league readiness (gamekit#38) ─────────────────────────────────────────────


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_agent_name(name: str) -> str:
    """gamekit.league forbids '/' and '__vs__' in agent names (they become file names)."""
    if not name or "/" in name or "__vs__" in name:
        raise ValueError(f"invalid league agent name {name!r}")
    return name


def build_agent(name: str, manifest: dict[str, Any]) -> TrucoAgent:
    """Resolve a league agent name: the built-in baselines, or a manifest entry (a checkpoint,
    played deterministically as in exp 008/009 finals)."""
    if name == "threshold":
        return ThresholdAgent()
    if name == "random":
        return RandomAgent()
    entry = manifest["agents"][name]
    path = Path(entry["path"])
    if sha256_file(path) != entry["sha256"]:
        raise ValueError(f"{path}: sha256 differs from the manifest entry for {name!r}")
    return RLAgent(path, deterministic=entry.get("deterministic", True))


def write_manifest(path: Path, agents: dict[str, dict[str, Any]], **meta: Any) -> None:
    for name in agents:
        validate_agent_name(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**meta, "agents": agents}, indent=2, sort_keys=True) + "\n")
