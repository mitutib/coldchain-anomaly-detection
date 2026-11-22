"""Anomaly detectors. Each takes one sensor's values in time order and returns 0/1 per reading."""
from __future__ import annotations

from collections import deque
from statistics import mean, pstdev


def fixed_threshold(values: list[float], threshold: float) -> list[int]:
    """Simplest baseline: anything above a fixed threshold is an anomaly."""
    return [1 if v > threshold else 0 for v in values]


def rolling_zscore(values: list[float], window: int = 36, limit: float = 3.0) -> list[int]:
    """Flag a value more than `limit` standard deviations away from the mean of the last `window` readings.

    The current reading is not part of the window it is compared against.
    """
    history: deque[float] = deque(maxlen=window)
    result: list[int] = []
    for v in values:
        if len(history) < window:
            result.append(0)  # not enough history to decide
        else:
            m, s = mean(history), pstdev(history)
            result.append(1 if s > 0 and abs(v - m) / s > limit else 0)
        history.append(v)
    return result
