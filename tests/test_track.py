import mlflow
import pytest

from coldchain.evaluate import evaluate_all, load
from coldchain.generate import generate, write_csv
from coldchain.track import MODEL_NAME, log_outcomes


@pytest.fixture(scope="module")
def tracked(tmp_path_factory):
    folder = tmp_path_factory.mktemp("tracking")
    path = folder / "readings.csv"
    write_csv(generate(days=10), path)
    uri = f"sqlite:///{folder}/mlflow.db"
    outcomes = evaluate_all(load(path), tune_fraction=0.7)
    log_outcomes(outcomes, data_path=path, tracking_uri=uri, artifact_root=str(folder / "artifacts"))
    return mlflow.MlflowClient(tracking_uri=uri), outcomes


def runs(client):
    experiment = client.get_experiment_by_name("coldchain-detectors")
    return {r.info.run_name: r for r in client.search_runs([experiment.experiment_id])}


def test_one_run_per_detector(tracked):
    client, outcomes = tracked
    assert set(runs(client)) == {o.name for o in outcomes}


def test_run_records_parameters_and_metrics(tracked):
    client, outcomes = tracked
    outcome = next(o for o in outcomes if o.name == "defrost aware")
    run = runs(client)["defrost aware"]
    assert run.data.params["n"] == str(outcome.params["n"])
    assert run.data.metrics["f1"] == pytest.approx(outcome.result.f1)
    assert run.data.metrics["faults_total"] == outcome.result.events.events


def test_runs_are_tagged_with_the_data_they_used(tracked):
    client, _ = tracked
    hashes = {r.data.tags["data_sha256"] for r in runs(client).values()}
    assert len(hashes) == 1 and len(hashes.pop()) == 64


def test_the_learned_model_is_registered(tracked):
    client, _ = tracked
    versions = client.search_model_versions(f"name='{MODEL_NAME}'")
    assert len(versions) == 1
    assert versions[0].run_id == runs(client)["gradient boosting"].info.run_id
