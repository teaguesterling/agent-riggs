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
    ) -> None:
        self.alpha_short = alpha_short
        self.alpha_session = alpha_session
        self.alpha_baseline = alpha_baseline
        self.t1 = 1.0
        self.t5 = 1.0
        self.t15 = 1.0

    def update(self, score: float) -> tuple[float, float, float]:
        """Update all three windows. Returns (t1, t5, t15)."""
        self.t1 = self.t1 * (1 - self.alpha_short) + score * self.alpha_short
        self.t5 = self.t5 * (1 - self.alpha_session) + score * self.alpha_session
        self.t15 = self.t15 * (1 - self.alpha_baseline) + score * self.alpha_baseline
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
