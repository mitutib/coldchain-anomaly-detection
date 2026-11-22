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


def defrost_aware(
    values: list[float], threshold: float, n: int, jump: float = 2.5, hold: int = 6
) -> list[int]:
    """Sustained threshold that recognises a defrost cycle by its shape instead of waiting it out.

    A defrost starts with a sudden jump between two consecutive readings; a fault drifts up slowly.
    After a jump of at least `jump` degrees, alarms are held back for `hold` readings. If the
    temperature is still high after that, it was not a defrost and the alarm fires.
    A jump that happens while an alarm is already active does not silence it.
    """
    result: list[int] = []
    streak = 0
    hold_until = 0
    for i, v in enumerate(values):
        alarming = bool(result and result[-1])
        if i > 0 and v - values[i - 1] >= jump and not alarming:
            hold_until = i + hold
        streak = streak + 1 if v > threshold else 0
        result.append(1 if streak >= n and i >= hold_until else 0)
    return result
