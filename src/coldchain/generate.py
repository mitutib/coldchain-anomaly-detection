"""Generate synthetic temperature readings with labelled faults.

Usage: python -m coldchain.generate [--days 7] [--seed 42] [--out data/readings.csv]
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

STEP_MINUTES = 5

# sensor -> (store, normal temperature, noise)
SENSORS = {
    "meat": ("Store A", 2.0, 0.3),
    "dairy": ("Store A", 4.0, 0.3),
    "deli": ("Store B", 5.0, 0.4),
    "frozen": ("Store B", -18.0, 0.5),
}


@dataclass
class Reading:
    timestamp: datetime
    sensor: str
    store: str
    temperature: float
    fault: int  # 1 = real fault, 0 = normal (defrost cycles included)


def generate(days: int = 7, seed: int = 42) -> list[Reading]:
    rnd = random.Random(seed)
    start = datetime(2026, 1, 5)
    steps = days * 24 * 60 // STEP_MINUTES
    readings: list[Reading] = []

    for sensor, (store, base, noise) in SENSORS.items():
        # about two faults per sensor per week: temperature drifts up over 1-3 hours
        faults = []
        for _ in range(max(2, days * 2 // 7)):
            begin = rnd.randrange(steps // 10, steps - 50)
            faults.append((begin, begin + rnd.randrange(12, 36)))

        for i in range(steps):
            timestamp = start + timedelta(minutes=i * STEP_MINUTES)
            # compressor cycle: a small wave with a ~40 minute period
            t = base + 0.4 * math.sin(2 * math.pi * i / 8) + rnd.gauss(0, noise)
            # scheduled defrost every 6 hours for 20 minutes: an expected spike, not a fault
            if (i * STEP_MINUTES) % 360 < 20:
                t += 4.0
            fault = 0
            for a, b in faults:
                if a <= i < b:
                    t += 8.0 * (i - a + 1) / (b - a)
                    fault = 1
            readings.append(Reading(timestamp, sensor, store, round(t, 2), fault))

    readings.sort(key=lambda r: (r.timestamp, r.sensor))
    return readings


def write_csv(readings: list[Reading], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "sensor", "store", "temperature", "fault"])
        for r in readings:
            w.writerow([r.timestamp.isoformat(sep=" "), r.sensor, r.store, r.temperature, r.fault])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=Path("data/readings.csv"))
    a = p.parse_args()
    readings = generate(a.days, a.seed)
    write_csv(readings, a.out)
    print(f"{len(readings)} readings, {sum(r.fault for r in readings)} faulty -> {a.out}")


if __name__ == "__main__":
    main()
