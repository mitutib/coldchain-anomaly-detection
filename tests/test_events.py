import pytest

from coldchain.events import EventStats, event_stats, find_events


def test_find_events_returns_runs_of_ones():
    assert find_events([0, 1, 1, 0, 0, 1]) == [(1, 3), (5, 6)]
    assert find_events([0, 0]) == []


def test_detected_event_reports_the_delay():
    actual = [0, 1, 1, 1, 1, 0]
    predicted = [0, 0, 0, 1, 1, 0]
    stats = event_stats(actual, predicted, step_minutes=5)
    assert (stats.events, stats.detected, stats.false_alarms) == (1, 1, 0)
    assert stats.delays_minutes == [10]


def test_missed_event_and_false_alarm():
    actual = [0, 1, 1, 0, 0, 0, 0]
    predicted = [0, 0, 0, 0, 1, 1, 0]
    stats = event_stats(actual, predicted, step_minutes=5)
    assert (stats.events, stats.detected, stats.false_alarms) == (1, 0, 1)
    assert stats.delays_minutes == []


def test_an_alarm_that_outlasts_the_fault_is_not_a_false_alarm():
    actual = [0, 1, 1, 0, 0]
    predicted = [0, 0, 1, 1, 0]
    assert event_stats(actual, predicted, step_minutes=5).false_alarms == 0


def test_stats_add_up_across_sensors():
    total = EventStats(2, 1, [10], 0) + EventStats(1, 1, [30], 2)
    assert (total.events, total.detected, total.false_alarms) == (3, 2, 2)
    assert total.detection_rate == pytest.approx(2 / 3)
    assert total.median_delay_minutes == 20


def test_median_delay_is_none_when_nothing_was_detected():
    assert EventStats(1, 0, [], 0).median_delay_minutes is None
