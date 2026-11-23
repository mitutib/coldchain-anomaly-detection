import random

import pytest

from coldchain.drift import psi


def sample(mean, spread, n=5000, seed=0):
    rnd = random.Random(seed)
    return [rnd.gauss(mean, spread) for _ in range(n)]


def test_same_distribution_has_almost_no_drift():
    assert psi(sample(0, 1, seed=1), sample(0, 1, seed=2)) < 0.02


def test_a_shifted_distribution_drifts():
    assert psi(sample(0, 1), sample(1, 1)) > 0.25


def test_a_wider_distribution_drifts():
    assert psi(sample(0, 1), sample(0, 2)) > 0.25


def test_identical_samples_have_zero_drift():
    values = sample(0, 1)
    assert psi(values, values) == pytest.approx(0.0)


def test_values_outside_the_reference_range_are_counted():
    reference = [float(i % 10) for i in range(1000)]
    current = [50.0] * 1000
    assert psi(reference, current) > 1


def test_empty_input_is_rejected():
    with pytest.raises(ValueError):
        psi([], [1.0])
