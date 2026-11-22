"""Run every detector on the dataset and print a results table. Usage: python -m coldchain.evaluate"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

from coldchain.detectors import fixed_threshold, rolling_zscore, sustained_threshold
from coldchain.generate import SENSORS
from coldchain.metrics import f1, precision, recall

DETECTORS = {
    "fixed threshold (+3C)": lambda sensor, v: fixed_threshold(v, SENSORS[sensor][1] + 3.0),
    "rolling z-score": lambda sensor, v: rolling_zscore(v),
    "sustained threshold (5x)": lambda sensor, v: sustained_threshold(v, SENSORS[sensor][1] + 3.0, n=5),
}


def load(path: Path) -> dict[str, list[tuple[float, int]]]:
    by_sensor: dict[str, list[tuple[float, int]]] = defaultdict(list)
    with path.open() as f:
        for row in csv.DictReader(f):  # file is already sorted by timestamp
            by_sensor[row["sensor"]].append((float(row["temperature"]), int(row["fault"])))
    return by_sensor


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/readings.csv")
    if not path.exists():
        sys.exit(f"{path} not found: run  python -m coldchain.generate  first")
    data = load(path)

    print(f"{'detector':<28}{'precision':>10}{'recall':>10}{'F1':>8}")
    for name, detector in DETECTORS.items():
        actual, predicted = [], []
        for sensor, rows in data.items():
            actual += [fault for _, fault in rows]
            predicted += detector(sensor, [t for t, _ in rows])
        print(f"{name:<28}{precision(actual, predicted):>10.2f}{recall(actual, predicted):>10.2f}{f1(actual, predicted):>8.2f}")


if __name__ == "__main__":
    main()
