from coldchain.detectors import fixed_threshold, rolling_zscore
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
