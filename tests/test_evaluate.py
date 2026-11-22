from datetime import datetime, timedelta

from coldchain.evaluate import Row, best_params, split_by_time, training_set


def rows(n):
    start = datetime(2026, 1, 5)
    return [Row(start + timedelta(minutes=5 * i), float(i), 0) for i in range(n)]


def test_split_keeps_time_order_and_does_not_overlap():
    tune, test = split_by_time({"meat": rows(10)}, tune_fraction=0.7)
    assert len(tune["meat"]) == 7 and len(test["meat"]) == 3
    assert tune["meat"][-1].timestamp < test["meat"][0].timestamp


def test_split_uses_one_cutoff_for_every_sensor():
    data = {"meat": rows(10), "dairy": rows(10)}
    _, test = split_by_time(data, tune_fraction=0.5)
    assert test["meat"][0].timestamp == test["dairy"][0].timestamp


def test_best_params_picks_the_highest_score():
    grid = [{"n": 1}, {"n": 2}, {"n": 3}]
    assert best_params(grid, score=lambda p: -abs(p["n"] - 2)) == {"n": 2}


def test_best_params_keeps_the_first_candidate_on_a_tie():
    grid = [{"n": 1}, {"n": 2}]
    assert best_params(grid, score=lambda p: 1.0) == {"n": 1}


def test_training_set_stacks_every_sensor():
    data = {"meat": rows(10), "dairy": rows(10)}
    X, y = training_set(data)
    assert X.shape[0] == 20 and y.shape == (20,)
