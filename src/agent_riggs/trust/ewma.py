"""Three-window exponentially weighted moving average for trust."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrustSnapshot:
    """Serializable snapshot of EWMA state."""

    t1: float
    t5: float
    t15: float
    alpha_short: float
    alpha_session: float
    alpha_baseline: float


class TrustEWMA:
    """Three-window EWMA. Three multiplications per update."""

    def __init__(
        self,
        alpha_short: float = 0.4,
        alpha_session: float = 0.08,
        alpha_baseline: float = 0.02,
        initial: float = 1.0,
    ) -> None:
        """``initial`` is the seed for all three windows.

        Security note: consumers scoring an *unknown* subject must seed low
        (see ``TrustConfig.initial_trust``) — the pipeline does. The 1.0
        default exists only for pure-math uses of this class.
        """
        self.alpha_short = alpha_short
        self.alpha_session = alpha_session
        self.alpha_baseline = alpha_baseline
        self.t1 = initial
        self.t5 = initial
        self.t15 = initial

    def update(self, score: float, allow_increase: bool = True) -> tuple[float, float, float]:
        """Update all three windows. Returns (t1, t5, t15).

        With ``allow_increase=False`` (self-reported evidence) each window
        uses ``min(score, window)`` as the effective score, so the update can
        only hold or lower trust — a subject asserting its own success gains
        nothing, while claims against interest still count.
        """
        s1 = score if allow_increase else min(score, self.t1)
        s5 = score if allow_increase else min(score, self.t5)
        s15 = score if allow_increase else min(score, self.t15)
        self.t1 = self.t1 * (1 - self.alpha_short) + s1 * self.alpha_short
        self.t5 = self.t5 * (1 - self.alpha_session) + s5 * self.alpha_session
        self.t15 = self.t15 * (1 - self.alpha_baseline) + s15 * self.alpha_baseline
        return (self.t1, self.t5, self.t15)

    def snapshot(self) -> TrustSnapshot:
        """Serialize current state."""
        return TrustSnapshot(
            t1=self.t1,
            t5=self.t5,
            t15=self.t15,
            alpha_short=self.alpha_short,
            alpha_session=self.alpha_session,
            alpha_baseline=self.alpha_baseline,
        )

    @classmethod
    def from_snapshot(cls, snap: TrustSnapshot) -> TrustEWMA:
        """Restore from a snapshot."""
        ewma = cls(
            alpha_short=snap.alpha_short,
            alpha_session=snap.alpha_session,
            alpha_baseline=snap.alpha_baseline,
        )
        ewma.t1 = snap.t1
        ewma.t5 = snap.t5
        ewma.t15 = snap.t15
        return ewma
