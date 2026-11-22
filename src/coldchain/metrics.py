"""Evaluation metrics for binary classification (1 = anomaly)."""
from __future__ import annotations


def confusion_matrix(actual: list[int], predicted: list[int]) -> dict[str, int]:
    if len(actual) != len(predicted):
        raise ValueError("inputs have different lengths")
    m = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for a, p in zip(actual, predicted):
        if a and p:
            m["tp"] += 1
        elif p:
            m["fp"] += 1
        elif a:
            m["fn"] += 1
        else:
            m["tn"] += 1
    return m


def precision(actual: list[int], predicted: list[int]) -> float:
    m = confusion_matrix(actual, predicted)
    return m["tp"] / (m["tp"] + m["fp"]) if m["tp"] + m["fp"] else 0.0


def recall(actual: list[int], predicted: list[int]) -> float:
    m = confusion_matrix(actual, predicted)
    return m["tp"] / (m["tp"] + m["fn"]) if m["tp"] + m["fn"] else 0.0


def f1(actual: list[int], predicted: list[int]) -> float:
    p, r = precision(actual, predicted), recall(actual, predicted)
    return 2 * p * r / (p + r) if p + r else 0.0
