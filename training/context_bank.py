"""
ContextBank (exp 009, D4): real pre-hand ``(scores, mano)`` states.

Training episodes are single hands, but the encoder reads team/rival score, malas and the
falta -- features that sit at 0-0 forever if every hand starts fresh, while ``TrucoMatch``
benchmarks vary them. The bank is recorded from Threshold-vs-Threshold ``TrucoMatch`` games
(general 3v3 rounds only: mano-a-mano hands restrict play to a seat pair, so a randomly
seated learner would often never act) and sampled at each env reset.
"""

import random
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path

import numpy as np

from agents.threshold_agent import ThresholdAgent
from engine.match import TrucoMatch
from engine.rules import N_SEATS


@dataclass(frozen=True, slots=True)
class ContextBank:
    scores: np.ndarray  # (N, 2) int16: [team A, team B] points in the chico before the hand
    mano: np.ndarray  # (N,) int8: seat that is mano

    def __len__(self) -> int:
        return len(self.mano)

    def sample(self, rng: random.Random) -> tuple[list[int], int]:
        i = rng.randrange(len(self))
        return [int(self.scores[i, 0]), int(self.scores[i, 1])], int(self.mano[i])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, scores=self.scores, mano=self.mano)

    @classmethod
    def load(cls, path: Path) -> "ContextBank":
        with np.load(path) as f:
            return cls(scores=f["scores"], mano=f["mano"])


def _record_match(seed: int) -> list[tuple[int, int, int]]:
    """Play one all-Threshold match; return (score_a, score_b, mano) per general hand."""
    match = TrucoMatch()
    agents = [ThresholdAgent(seed=seed + i) for i in range(N_SEATS)]
    ms = match.reset(seed=seed)
    out: list[tuple[int, int, int]] = []
    seen = None
    while not match.is_terminal(ms):
        if ms.hand is not seen:
            seen = ms.hand
            if len(ms.hand.seats) == N_SEATS:
                out.append((ms.hand.scores[0], ms.hand.scores[1], ms.hand.mano))
        cp = ms.hand.current_player
        match.apply_action(ms, agents[cp].choose_action(ms.hand, match.legal_actions(ms), cp))
    return out


def build_bank(n_matches: int, seed: int, workers: int = 1) -> ContextBank:
    seeds = [seed + i for i in range(n_matches)]
    if workers > 1:
        with get_context("fork").Pool(workers) as pool:
            shards = pool.map(_record_match, seeds, chunksize=max(1, n_matches // (workers * 8)))
    else:
        shards = [_record_match(s) for s in seeds]
    rows = [row for shard in shards for row in shard]
    arr = np.array(rows, dtype=np.int16)
    return ContextBank(scores=arr[:, :2].copy(), mano=arr[:, 2].astype(np.int8))
