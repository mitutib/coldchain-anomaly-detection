from coldchain.detectors import (
    DefrostAwareDetector,
    defrost_aware,
    fixed_threshold,
    rolling_zscore,
    sustained_threshold,
)
from coldchain.events import find_events
from coldchain.generate import generate


def test_fixed_threshold():
    assert fixed_threshold([1.0, 7.0, 6.0], threshold=6.0) == [0, 1, 0]


def test_zscore_catches_a_jump():
    values = [4.0, 4.1, 3.9, 4.0, 4.1, 3.9, 4.0, 4.1, 12.0]
    assert rolling_zscore(values, window=8)[-1] == 1


def test_zscore_is_silent_without_history():
    assert rolling_zscore([4.0, 50.0, 4.0], window=8) == [0, 0, 0]


def test_generation_is_reproducible():
    assert generate(days=1, seed=1) == generate(days=1, seed=1)
    assert sum(r.fault for r in generate(days=7)) > 0


def test_sustained_threshold_ignores_a_short_spike():
    # defrost: three readings above the threshold, then back to normal
    values = [4.0, 4.0, 9.0, 9.0, 9.0, 4.0, 4.0]
    assert sustained_threshold(values, threshold=7.0, n=4) == [0, 0, 0, 0, 0, 0, 0]


def test_sustained_threshold_fires_after_n_consecutive_readings():
    values = [4.0, 9.0, 9.0, 9.0, 9.0, 9.0, 4.0]
    assert sustained_threshold(values, threshold=7.0, n=4) == [0, 0, 0, 0, 1, 1, 0]


def test_sustained_threshold_restarts_the_count_after_a_gap():
    values = [9.0, 9.0, 4.0, 9.0, 9.0, 9.0]
    assert sustained_threshold(values, threshold=7.0, n=3) == [0, 0, 0, 0, 0, 1]


def test_longer_datasets_get_more_faults():
    def fault_count(days):
        readings = [r.fault for r in generate(days=days) if r.sensor == "meat"]
        return len(find_events(readings))

    assert fault_count(7) == 2
    assert fault_count(28) >= 6      # eight are planted; a few may overlap


def test_defrost_aware_ignores_a_sudden_short_spike():
    values = [4.0, 4.0, 8.0, 8.0, 8.0, 8.0, 4.0, 4.0]
    assert defrost_aware(values, threshold=5.5, n=2) == [0] * 8


def test_defrost_aware_catches_a_slow_drift_early():
    values = [4.0, 4.5, 5.0, 5.6, 6.2, 6.8]
    assert defrost_aware(values, threshold=5.5, n=2) == [0, 0, 0, 0, 1, 1]


def test_defrost_aware_alarms_when_a_sudden_jump_does_not_come_back():
    values = [4.0, 4.0] + [9.0] * 8
    assert defrost_aware(values, threshold=5.5, n=2, hold=4) == [0, 0, 0, 0, 0, 0, 1, 1, 1, 1]


def test_defrost_aware_keeps_alarming_when_a_defrost_starts_during_a_fault():
    values = [4.0, 6.0, 6.0, 6.0, 10.0, 10.0, 6.0]
    assert defrost_aware(values, threshold=5.0, n=2) == [0, 0, 1, 1, 1, 1, 1]


def test_streaming_detector_keeps_state_between_readings():
    detector = DefrostAwareDetector(threshold=5.5, n=2, hold=4)
    readings = [4.0, 4.0, 9.0, 9.0, 9.0, 9.0, 9.0, 4.0]
    assert [detector.update(v) for v in readings] == [False] * 6 + [True, False]
