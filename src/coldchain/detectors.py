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


def sustained_threshold(values: list[float], threshold: float, n: int) -> list[int]:
    """Flag a reading once the value has stayed above the threshold for `n` consecutive readings.

    A short spike such as a defrost cycle never reaches `n`; a drift that lasts does.
    """
    result: list[int] = []
    streak = 0
    for v in values:
        streak = streak + 1 if v > threshold else 0
        result.append(1 if streak >= n else 0)
    return result


class DefrostAwareDetector:
    """Defrost-aware detection, one reading at a time.

    A defrost starts with a sudden jump; a fault drifts up slowly. After a jump of at least
    `jump` degrees, alarms are held back for `hold` readings. A jump during an active alarm
    does not silence it.
    """

    def __init__(self, threshold: float, n: int, jump: float = 2.5, hold: int = 6):
        self.threshold, self.n, self.jump, self.hold = threshold, n, jump, hold
        self.previous: float | None = None
        self.streak = 0
        self.held = 0
        self.alarming = False

    def update(self, value: float) -> bool:
        if self.held:
            self.held -= 1
        if self.previous is not None and value - self.previous >= self.jump and not self.alarming:
            self.held = self.hold
        self.streak = self.streak + 1 if value > self.threshold else 0
        self.alarming = self.streak >= self.n and not self.held
        self.previous = value
        return self.alarming


def defrost_aware(
    values: list[float], threshold: float, n: int, jump: float = 2.5, hold: int = 6
) -> list[int]:
    detector = DefrostAwareDetector(threshold, n, jump, hold)
    return [int(detector.update(v)) for v in values]
