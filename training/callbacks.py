"""
RunCallback: the one SB3 callback of an exp-009 run.

  * freeze detector (gamekit note 011) -- fed once per PPO update from ``_on_rollout_end``;
  * clean stop -- a ``STOP`` file in the run dir or a signal event ends ``learn()`` at the next
    env step, so the loop can checkpoint and exit (the laptop is shut down every night);
  * per-opponent-role episode stats (how often each role was drawn, and the learner's mean
    return against it) so the mix weights can be verified from the log.
"""

import threading
from pathlib import Path

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from training.collapse import PolicyFreezeDetector
from training.config import ROLE_NAMES

_STOP_CHECK_EVERY = 64  # env steps between STOP-file checks


class RunCallback(BaseCallback):
    def __init__(
        self, stop_file: Path, stop_event: threading.Event, detector: PolicyFreezeDetector
    ) -> None:
        super().__init__()
        self._stop_file = stop_file
        self._stop_event = stop_event
        self._detector = detector
        self.frozen = False
        self.freeze_reason: str | None = None
        self.stop_requested = False
        self.role_episodes = np.zeros(len(ROLE_NAMES), dtype=np.int64)
        self.role_return = np.zeros(len(ROLE_NAMES), dtype=np.float64)

    # ── SB3 hooks ─────────────────────────────────────────────────────────
    def _on_step(self) -> bool:
        for info in self.locals["infos"]:
            ep = info.get("episode")
            if ep is not None and int(ep.get("opp_role", -1)) >= 0:
                role = int(ep["opp_role"])
                self.role_episodes[role] += 1
                self.role_return[role] += float(ep["r"])

        if self._stop_event.is_set() or (
            self.n_calls % _STOP_CHECK_EVERY == 0 and self._stop_file.exists()
        ):
            self.stop_requested = True
        return not (self.stop_requested or self.frozen)

    def _on_rollout_end(self) -> None:
        # SB3 records ``train/*`` at the end of update k and dumps it only after the *next*
        # rollout, so at this point the values are the previous update's (note 011).
        values = self.logger.name_to_value
        keys = ("train/entropy_loss", "train/clip_fraction", "train/approx_kl")
        if all(k in values for k in keys) and not self.frozen:
            ent, clip, kl = (float(values[k]) for k in keys)
            if self._detector.observe(ent, clip, kl):
                self.frozen = True
                self.freeze_reason = self._detector.fired_reason

        total = int(self.role_episodes.sum())
        if total:
            for i, name in enumerate(ROLE_NAMES):
                self.logger.record(f"roles/frac_{name}", self.role_episodes[i] / total)
                if self.role_episodes[i]:
                    self.logger.record(
                        f"roles/return_vs_{name}", self.role_return[i] / self.role_episodes[i]
                    )

    # ── reporting ─────────────────────────────────────────────────────────
    def role_stats(self) -> dict[str, dict[str, float | int]]:
        return {
            name: {
                "episodes": int(self.role_episodes[i]),
                "mean_return": (
                    float(self.role_return[i] / self.role_episodes[i])
                    if self.role_episodes[i]
                    else 0.0
                ),
            }
            for i, name in enumerate(ROLE_NAMES)
        }
