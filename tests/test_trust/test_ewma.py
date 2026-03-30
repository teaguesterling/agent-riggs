from __future__ import annotations

import pytest

from agent_riggs.trust.ewma import TrustEWMA


def test_initial_values() -> None:
    ewma = TrustEWMA()
    assert ewma.t1 == 1.0
    assert ewma.t5 == 1.0
    assert ewma.t15 == 1.0


def test_update_with_perfect_score() -> None:
    ewma = TrustEWMA()
    t1, t5, t15 = ewma.update(1.0)
    assert t1 == 1.0
    assert t5 == 1.0
    assert t15 == 1.0


def test_update_with_zero_score() -> None:
    ewma = TrustEWMA()
    t1, t5, t15 = ewma.update(0.0)
    assert t1 == pytest.approx(0.6)
    assert t5 == pytest.approx(0.92)
    assert t15 == pytest.approx(0.98)


def test_repeated_failures_converge_toward_zero() -> None:
    ewma = TrustEWMA()
    for _ in range(50):
        ewma.update(0.0)
    assert ewma.t1 < 0.01
    assert ewma.t5 < 0.05
    assert ewma.t15 > 0.1


def test_recovery_after_failures() -> None:
    ewma = TrustEWMA()
    for _ in range(10):
        ewma.update(0.0)
    low_t1 = ewma.t1
    for _ in range(10):
        ewma.update(1.0)
    assert ewma.t1 > low_t1


def test_custom_alphas() -> None:
    ewma = TrustEWMA(alpha_short=1.0, alpha_session=1.0, alpha_baseline=1.0)
    t1, t5, t15 = ewma.update(0.5)
    assert t1 == pytest.approx(0.5)
    assert t5 == pytest.approx(0.5)
    assert t15 == pytest.approx(0.5)


def test_snapshot_and_restore() -> None:
    ewma = TrustEWMA()
    ewma.update(0.5)
    ewma.update(0.8)
    snapshot = ewma.snapshot()

    restored = TrustEWMA.from_snapshot(snapshot)
    assert restored.t1 == pytest.approx(ewma.t1)
    assert restored.t5 == pytest.approx(ewma.t5)
    assert restored.t15 == pytest.approx(ewma.t15)
