"""Measure how far a batch of readings has moved from the data the thresholds were tuned on.

Usage: python -m coldchain.drift reference.csv current.csv
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from coldchain.evaluate import load
from coldchain.generate import SENSORS

STABLE, MODERATE = 0.1, 0.25


def psi(reference: list[float], current: list[float], bins: int = 10) -> float:
    """Population stability index between two samples.

    Bin edges are the reference quantiles, so every bin holds about the same share of the
    reference. Below 0.1 is usually read as stable, above 0.25 as a real shift.
    """
    if not reference or not current:
        raise ValueError("both samples need at least one value")
    ordered = sorted(reference)
    edges = [ordered[len(ordered) * i // bins] for i in range(1, bins)]

    def shares(values: list[float]) -> list[float]:
        counts = [0] * bins
        for v in values:
            counts[sum(v >= e for e in edges)] += 1
        # an empty bin would make the logarithm blow up
        return [max(c / len(values), 1e-4) for c in counts]

    return sum((c - r) * math.log(c / r) for r, c in zip(shares(reference), shares(current), strict=True))


def offsets(path: Path) -> list[float]:
    """Every reading as degrees above its sensor's setpoint."""
    return [r.temperature - SENSORS[s][1] for s, rows in load(path).items() for r in rows]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("reference", type=Path)
    p.add_argument("current", type=Path)
    args = p.parse_args()
    value = psi(offsets(args.reference), offsets(args.current))
    verdict = "stable" if value < STABLE else "moderate shift" if value < MODERATE else "drifted"
    print(f"PSI {value:.3f}: {verdict}")


if __name__ == "__main__":
    main()
