"""
TeamOpponentPool (exp 009, D1/D2): team-consistent, run-scoped opponent sampling.

gamekit's ``OpponentPool.seat_agents`` samples every non-learner seat independently, so the
learner's partners would be Random/Threshold/snapshots too, while benchmarks and the league
always play 3 copies of one agent against 3 copies of another. This subclass samples per team:

  * opponent team: ONE role per episode, drawn from the mix (Threshold / Random / one
    uniformly-drawn own snapshot), replicated on all 3 opponent seats;
  * partners (the learner's two teammates): per ``partners`` -- the latest own snapshot
    (default), Threshold, or independent draws from the mix.

Snapshots live in ``directory/run_id`` (gamekit's run scoping), so a stale or foreign
checkpoint can never leak in. An empty pool when a snapshot is needed is an error, not a
silent fallback -- silent fallbacks are what contaminated exp 004/005.
"""

import random
from collections.abc import Callable
from pathlib import Path

from gamekit.rl.selfplay import OpponentPool

from agents.base import TrucoAgent
from agents.random_agent import RandomAgent
from agents.threshold_agent import ThresholdAgent
from engine.actions import Action
from engine.game_state import GameState, team_of
from training.config import (
    ROLE_RANDOM,
    ROLE_SELF,
    ROLE_THRESHOLD,
    SNAPSHOT_GLOB,
    OpponentMix,
    PartnerPolicy,
)


class TeamOpponentPool(OpponentPool[GameState, Action]):
    def __init__(
        self,
        directory: Path,
        *,
        run_id: str,
        mix: OpponentMix,
        partners: PartnerPolicy,
        load_opponent: Callable[[Path], TrucoAgent],
        seed: int = 0,
    ) -> None:
        rng = random.Random(seed)
        super().__init__(
            directory,
            SNAPSHOT_GLOB,
            load_opponent=load_opponent,
            baseline_factory=ThresholdAgent,
            run_id=run_id,
            rng=rng,
        )
        self._mix = mix
        self._partners = partners
        self.last_opp_role: int = ROLE_THRESHOLD
        self.last_partner_role: int = ROLE_THRESHOLD

    # ── role sampling ─────────────────────────────────────────────────────
    def _draw_role(self) -> int:
        return self._rng.choices((ROLE_THRESHOLD, ROLE_RANDOM, ROLE_SELF), self._mix.weights)[0]

    def _team_factory(self, role: int) -> Callable[[], TrucoAgent]:
        """A zero-arg factory producing one team-mate of ``role``; the snapshot, if any, is
        drawn once so all 3 seats of the team share it."""
        if role == ROLE_THRESHOLD:
            return lambda: ThresholdAgent(seed=self._rng.randrange(2**31))
        if role == ROLE_RANDOM:
            return lambda: RandomAgent(seed=self._rng.randrange(2**31))
        path = self._rng.choice(self._require_snapshots())
        return lambda: self._load_opponent(path)

    def _require_snapshots(self) -> list[Path]:
        paths = self.checkpoints()
        if not paths:
            raise RuntimeError(
                f"no snapshots in {self.checkpoint_dir}: the trainer must seed snap_0 (the BC "
                "init) before any env is created"
            )
        return paths

    def _partner_factory(self) -> tuple[int, Callable[[], TrucoAgent]]:
        if self._partners == "snapshot":
            latest = self._require_snapshots()[-1]
            return ROLE_SELF, lambda: self._load_opponent(latest)
        if self._partners == "threshold":
            return ROLE_THRESHOLD, self._team_factory(ROLE_THRESHOLD)
        role = self._draw_role()  # "pool": today's noisy behaviour, kept as an ablation
        return role, self._team_factory(role)

    # ── gamekit hook ──────────────────────────────────────────────────────
    def seat_agents(self, num_seats: int, learner_seat: int) -> list[TrucoAgent | None]:
        learner_team = team_of(learner_seat)
        self.last_opp_role = self._draw_role()
        make_opponent = self._team_factory(self.last_opp_role)
        self.last_partner_role, make_partner = self._partner_factory()
        return [
            None
            if seat == learner_seat
            else (make_partner() if team_of(seat) == learner_team else make_opponent())
            for seat in range(num_seats)
        ]
