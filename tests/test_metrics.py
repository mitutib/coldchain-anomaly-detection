import pytest

from coldchain.metrics import confusion_matrix, f1, precision, recall

ACTUAL = [1, 1, 0, 0, 1, 0]
PREDICTED = [1, 0, 0, 1, 1, 0]


def test_confusion_matrix():
    assert confusion_matrix(ACTUAL, PREDICTED) == {"tp": 2, "fp": 1, "fn": 1, "tn": 2}


def test_precision_recall_f1():
    assert precision(ACTUAL, PREDICTED) == pytest.approx(2 / 3)
    assert recall(ACTUAL, PREDICTED) == pytest.approx(2 / 3)
    assert f1(ACTUAL, PREDICTED) == pytest.approx(2 / 3)


def test_no_positive_predictions_does_not_divide_by_zero():
    assert precision([1, 0], [0, 0]) == 0.0
    assert f1([1, 0], [0, 0]) == 0.0


def test_length_mismatch():
    with pytest.raises(ValueError):
        confusion_matrix([1], [1, 0])
