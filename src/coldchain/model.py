"""A learned detector: window features per reading, a gradient boosting classifier on top.

Every feature is computed from the current reading and the ones before it, so the model can run
online and nothing leaks from the future. Temperatures are taken relative to the sensor's setpoint,
which lets one model serve fridges and freezers alike.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from coldchain.detectors import sustained_threshold

FEATURE_NAMES = [
    "offset",          # degrees above the setpoint right now
    "mean_30min",      # average offset over the last 6 readings
    "mean_60min",
    "min_30min",       # stays high only if the temperature did not come back down
    "rise_15min",      # change over the last 3 readings
    "rise_30min",
    "rise_60min",
    "max_jump_30min",  # largest step between consecutive readings: a defrost shows up here
    "std_60min",
]


def _window(a: np.ndarray, i: int, size: int) -> np.ndarray:
    return a[max(0, i - size + 1) : i + 1]


def build_features(values: list[float], setpoint: float) -> np.ndarray:
    offset = np.asarray(values, dtype=float) - setpoint
    step = np.diff(offset, prepend=offset[0])
    X = np.zeros((len(offset), len(FEATURE_NAMES)))
    for i in range(len(offset)):
        last_30, last_60 = _window(offset, i, 6), _window(offset, i, 12)
        X[i] = [
            offset[i],
            last_30.mean(),
            last_60.mean(),
            last_30.min(),
            offset[i] - offset[max(0, i - 3)],
            offset[i] - offset[max(0, i - 6)],
            offset[i] - offset[max(0, i - 12)],
            _window(step, i, 6).max(),
            last_60.std(),
        ]
    return X


def train(X: np.ndarray, y: np.ndarray) -> HistGradientBoostingClassifier:
    # faults are about 2% of the readings: weigh the classes so they are not ignored
    model = HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.1, max_depth=4, class_weight="balanced", random_state=0
    )
    return model.fit(X, y)


def to_alarms(scores: list[float], threshold: float, n: int) -> list[int]:
    """Turn fault probabilities into alarms: `n` consecutive scores above the threshold."""
    return sustained_threshold(list(scores), threshold, n)
