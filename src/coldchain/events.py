"""Event-level evaluation: how many faults were caught, how fast, and how many alarms were false.

Per-reading metrics treat every five-minute reading separately. What matters operationally is the
fault as a whole: was it caught at all, and how long after it started.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


def find_events(labels: list[int]) -> list[tuple[int, int]]:
    """Return the [start, end) index ranges of consecutive ones."""
    events: list[tuple[int, int]] = []
    start = None
    for i, label in enumerate(labels):
        if label and start is None:
            start = i
        elif not label and start is not None:
            events.append((start, i))
            start = None
    if start is not None:
        events.append((start, len(labels)))
    return events


@dataclass
class EventStats:
    events: int = 0
    detected: int = 0
    delays_minutes: list[float] = field(default_factory=list)
    false_alarms: int = 0

    def __add__(self, other: EventStats) -> EventStats:
        return EventStats(
            self.events + other.events,
            self.detected + other.detected,
            self.delays_minutes + other.delays_minutes,
            self.false_alarms + other.false_alarms,
        )

    @property
    def detection_rate(self) -> float:
        return self.detected / self.events if self.events else 0.0

    @property
    def median_delay_minutes(self) -> float | None:
        return median(self.delays_minutes) if self.delays_minutes else None


def event_stats(actual: list[int], predicted: list[int], step_minutes: int) -> EventStats:
    """Compare one sensor's alarms with its labelled faults."""
    if len(actual) != len(predicted):
        raise ValueError("inputs have different lengths")
    faults = find_events(actual)
    stats = EventStats(events=len(faults))

    for start, end in faults:
        first_alarm = next((i for i in range(start, end) if predicted[i]), None)
        if first_alarm is not None:
            stats.detected += 1
            stats.delays_minutes.append((first_alarm - start) * step_minutes)

    # an alarm is false only if it does not touch any fault
    for start, end in find_events(predicted):
        if not any(actual[start:end]):
            stats.false_alarms += 1
    return stats
