"""Evaluate every detector and record the results in MLflow.

Usage: python -m coldchain.track [data/readings.csv] [--tracking-uri sqlite:///mlflow.db]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn

from coldchain.evaluate import Outcome, evaluate_all, load
from coldchain.model import FEATURE_NAMES

EXPERIMENT = "coldchain-detectors"
MODEL_NAME = "coldchain-fault-model"
# skops refuses types it does not know; this one is the tree structure of our own model
TRUSTED_TYPES = ["sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"]


def log_outcomes(
    outcomes: list[Outcome], data_path: Path, tracking_uri: str, artifact_root: str | None = None
) -> None:
    mlflow.set_tracking_uri(tracking_uri)
    if mlflow.get_experiment_by_name(EXPERIMENT) is None:
        mlflow.create_experiment(EXPERIMENT, artifact_location=artifact_root)
    mlflow.set_experiment(EXPERIMENT)
    data_hash = hashlib.sha256(Path(data_path).read_bytes()).hexdigest()

    for o in outcomes:
        with mlflow.start_run(run_name=o.name):
            mlflow.set_tag("data_sha256", data_hash)
            mlflow.log_params(o.params)
            events = o.result.events
            mlflow.log_metrics(
                {
                    "precision": o.result.precision,
                    "recall": o.result.recall,
                    "f1": o.result.f1,
                    "faults_total": events.events,
                    "faults_caught": events.detected,
                    "false_alarms": events.false_alarms,
                }
            )
            if events.median_delay_minutes is not None:
                mlflow.log_metric("median_delay_minutes", events.median_delay_minutes)
            if o.model is not None:
                mlflow.log_param("features", ",".join(FEATURE_NAMES))
                mlflow.sklearn.log_model(
                    o.model, name="model", registered_model_name=MODEL_NAME, skops_trusted_types=TRUSTED_TYPES
                )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("path", nargs="?", type=Path, default=Path("data/readings.csv"))
    p.add_argument("--tune-fraction", type=float, default=0.7)
    p.add_argument("--tracking-uri", default="sqlite:///mlflow.db")
    args = p.parse_args()
    if not args.path.exists():
        sys.exit(f"{args.path} not found: run  python -m coldchain.generate  first")
    outcomes = evaluate_all(load(args.path), args.tune_fraction)
    log_outcomes(outcomes, args.path, args.tracking_uri)
    print(f"logged {len(outcomes)} runs to {args.tracking_uri}")


if __name__ == "__main__":
    main()
