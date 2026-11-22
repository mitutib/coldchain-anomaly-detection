"""Tune every detector on the first part of the data and report on the rest.

Usage: python -m coldchain.evaluate [data/readings.csv] [--tune-fraction 0.7]

The split is by time, never random: parameters are chosen on the past and judged on the future,
which is the only situation the detector will ever be in once deployed.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np

from coldchain.detectors import defrost_aware, fixed_threshold, rolling_zscore, sustained_threshold
from coldchain.events import EventStats, event_stats
from coldchain.generate import SENSORS, STEP_MINUTES
from coldchain.metrics import f1, precision, recall
from coldchain.model import build_features, to_alarms, train


@dataclass
class Row:
    timestamp: datetime
    temperature: float
    fault: int


Data = dict[str, list[Row]]
Detector = Callable[[str, list[float]], list[int]]

# name -> (builder taking the tuned parameters, grid of candidates)
OFFSETS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
DETECTORS: dict[str, tuple[Callable[..., Detector], list[dict]]] = {
    "fixed threshold": (
        lambda offset: lambda sensor, v: fixed_threshold(v, SENSORS[sensor][1] + offset),
        [{"offset": o} for o in OFFSETS],
    ),
    "rolling z-score": (
        lambda limit: lambda sensor, v: rolling_zscore(v, limit=limit),
        [{"limit": x} for x in (2.5, 3.0, 3.5, 4.0)],
    ),
    "sustained threshold": (
        lambda offset, n: lambda sensor, v: sustained_threshold(v, SENSORS[sensor][1] + offset, n),
        [{"offset": o, "n": n} for o in OFFSETS for n in range(2, 9)],
    ),
    "defrost aware": (
        lambda offset, n: lambda sensor, v: defrost_aware(v, SENSORS[sensor][1] + offset, n),
        [{"offset": o, "n": n} for o in OFFSETS for n in range(1, 5)],
    ),
}


def load(path: Path) -> Data:
    data: Data = defaultdict(list)
    with path.open() as f:
        for row in csv.DictReader(f):  # file is already sorted by timestamp
            data[row["sensor"]].append(
                Row(datetime.fromisoformat(row["timestamp"]), float(row["temperature"]), int(row["fault"]))
            )
    return data


def split_by_time(data: Data, tune_fraction: float) -> tuple[Data, Data]:
    """Split every sensor at the same moment: earlier readings to tune on, later ones to test on."""
    timestamps = sorted({r.timestamp for rows in data.values() for r in rows})
    cutoff = timestamps[int(len(timestamps) * tune_fraction)]
    tune = {s: [r for r in rows if r.timestamp < cutoff] for s, rows in data.items()}
    test = {s: [r for r in rows if r.timestamp >= cutoff] for s, rows in data.items()}
    return tune, test


def best_params(grid: list[dict], score: Callable[[dict], float]) -> dict:
    """Return the candidate with the highest score; the first one wins a tie."""
    return max(grid, key=score)


@dataclass
class Result:
    precision: float
    recall: float
    f1: float
    events: EventStats


def run(detector: Detector, data: Data) -> Result:
    actual: list[int] = []
    predicted: list[int] = []
    events = EventStats()
    for sensor, rows in data.items():
        labels = [r.fault for r in rows]
        alarms = detector(sensor, [r.temperature for r in rows])
        actual += labels
        predicted += alarms
        events += event_stats(labels, alarms, STEP_MINUTES)
    return Result(precision(actual, predicted), recall(actual, predicted), f1(actual, predicted), events)


def training_set(data: Data) -> tuple[np.ndarray, np.ndarray]:
    """Features and labels of every sensor, stacked."""
    X = np.vstack([build_features([r.temperature for r in rows], SENSORS[s][1]) for s, rows in data.items()])
    y = np.array([r.fault for rows in data.values() for r in rows])
    return X, y


def model_detector(model, threshold: float, n: int) -> Detector:
    def detect(sensor: str, values: list[float]) -> list[int]:
        scores = model.predict_proba(build_features(values, SENSORS[sensor][1]))[:, 1]
        return to_alarms(scores, threshold, n)

    return detect


def fit_model(tune: Data) -> tuple[Detector, dict]:
    """Fit on the earlier part of the tuning data, choose the alarm rule on the later part, then refit on all of it."""
    fit, validate = split_by_time(tune, 5 / 7)
    model = train(*training_set(fit))
    grid = [{"threshold": t, "n": n} for t in (0.3, 0.5, 0.7, 0.9) for n in (1, 2, 3)]
    params = best_params(grid, lambda c: run(model_detector(model, **c), validate).f1)
    return model_detector(train(*training_set(tune)), **params), params


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("path", nargs="?", type=Path, default=Path("data/readings.csv"))
    p.add_argument("--tune-fraction", type=float, default=0.7)
    args = p.parse_args()
    if not args.path.exists():
        sys.exit(f"{args.path} not found: run  python -m coldchain.generate  first")

    tune, test = split_by_time(load(args.path), args.tune_fraction)
    days = len(next(iter(test.values()))) * STEP_MINUTES / 1440
    print(f"tuned on {sum(map(len, tune.values()))} readings, tested on {sum(map(len, test.values()))} ({days:.1f} days)\n")
    print(f"{'detector':<21}{'parameters':<24}{'precision':>9}{'recall':>8}{'F1':>6}{'caught':>8}{'delay':>9}{'false alarms':>14}")

    tuned: list[tuple[str, Detector, dict]] = []
    for name, (build, grid) in DETECTORS.items():
        params = best_params(grid, lambda c: run(build(**c), tune).f1)
        tuned.append((name, build(**params), params))
    tuned.append(("gradient boosting", *fit_model(tune)))

    for name, detector, params in tuned:
        r = run(detector, test)
        delay = r.events.median_delay_minutes
        print(
            f"{name:<21}{', '.join(f'{k}={v}' for k, v in params.items()):<24}"
            f"{r.precision:>9.2f}{r.recall:>8.2f}{r.f1:>6.2f}"
            f"{f'{r.events.detected}/{r.events.events}':>8}"
            f"{'-' if delay is None else f'{delay:.0f} min':>9}"
            f"{r.events.false_alarms:>14}"
        )


if __name__ == "__main__":
    main()
