"""
PolicyFreezeDetector (gamekit note 011): flags the collapse truco-py actually saw in
exp 005 -- ``approx_kl`` and ``clip_fraction`` going to zero while entropy drains -- not a
KL spike.

Fires when ``|entropy|`` AND ``clip_fraction`` are both below ``ratio`` x their trailing
``window``-update median for ``patience`` consecutive updates, once ``window`` updates have
been seen (warm-up). An absolute near-zero rule is an independent fallback. Replayed on the
June 2026 trace this fires at update 74 (6.32M steps), ~420k steps before everything is zero.
"""

from collections import deque
from statistics import median

ABS_ENTROPY = 1e-3
ABS_CLIP = 1e-3
ABS_KL = 1e-4


class PolicyFreezeDetector:
    def __init__(self, window: int = 20, ratio: float = 0.5, patience: int = 3) -> None:
        self._window = window
        self._ratio = ratio
        self._patience = patience
        self._entropy: deque[float] = deque(maxlen=window)
        self._clip: deque[float] = deque(maxlen=window)
        self._streak = 0
        self.fired_reason: str | None = None

    def observe(self, entropy: float, clip_fraction: float, approx_kl: float) -> bool:
        """Feed one PPO update's metrics; True once the policy looks frozen."""
        ent, clip = abs(entropy), abs(clip_fraction)

        if ent < ABS_ENTROPY and clip < ABS_CLIP and abs(approx_kl) < ABS_KL:
            self.fired_reason = "absolute near-zero entropy/clip/kl"
            return True

        if len(self._entropy) == self._window:
            low = ent < self._ratio * median(self._entropy) and clip < self._ratio * median(
                self._clip
            )
            self._streak = self._streak + 1 if low else 0
        # The trailing window includes the current update only after the comparison, so a
        # sharp drop is judged against the healthy past, not against itself.
        self._entropy.append(ent)
        self._clip.append(clip)

        if self._streak >= self._patience:
            self.fired_reason = (
                f"|entropy| and clip_fraction < {self._ratio:.0%} of trailing-{self._window} "
                f"median for {self._patience} consecutive updates"
            )
            return True
        return False
