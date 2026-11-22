import numpy as np

from coldchain.model import FEATURE_NAMES, build_features, to_alarms, train


def test_one_row_of_features_per_reading():
    X = build_features([4.0] * 30, setpoint=4.0)
    assert X.shape == (30, len(FEATURE_NAMES))


def test_a_flat_series_at_the_setpoint_gives_zero_features():
    assert not build_features([4.0] * 30, setpoint=4.0).any()


def test_features_only_look_at_the_past():
    values = [4.0 + 0.1 * i for i in range(40)]
    changed = values[:25] + [99.0] * 15
    before = build_features(values, setpoint=4.0)
    after = build_features(changed, setpoint=4.0)
    assert np.array_equal(before[:25], after[:25])


def test_features_do_not_depend_on_the_setpoint_level():
    fridge = build_features([4.0, 4.5, 5.0, 6.0], setpoint=4.0)
    freezer = build_features([-18.0, -17.5, -17.0, -16.0], setpoint=-18.0)
    assert np.allclose(fridge, freezer)


def test_to_alarms_needs_consecutive_high_scores():
    scores = [0.1, 0.9, 0.2, 0.9, 0.9, 0.9]
    assert to_alarms(scores, threshold=0.5, n=2) == [0, 0, 0, 0, 1, 1]


def test_model_learns_a_sustained_rise():
    normal = [4.0] * 60
    fault = [4.0] * 20 + [4.0 + 0.3 * i for i in range(1, 21)] + [4.0] * 20
    labels = [0] * 20 + [1] * 20 + [0] * 20
    X = np.vstack([build_features(normal, 4.0), build_features(fault, 4.0)])
    y = np.array([0] * 60 + labels)
    model = train(X, y)
    scores = model.predict_proba(build_features(fault, 4.0))[:, 1]
    assert scores[35] > 0.5 and scores[5] < 0.5
