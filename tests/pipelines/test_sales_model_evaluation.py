"""Temporal evaluation invariants on the actual official dataset."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from brasaland_sales.evaluation import (
    HORIZON,
    LEARNING_SIZES,
    ORIGINS,
    evaluate,
    evaluate_window,
    training_history,
)
from brasaland_sales.experiment import load_data

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def frame():
    return load_data(ROOT / "data/raw/brasaland_sales.csv")


@pytest.fixture(scope="module")
def results(frame):
    return evaluate(frame)


def test_five_ordered_folds_and_fixed_horizon(results):
    folds = results["folds"]
    assert [f["origin_months"] for f in folds] == [48, 54, 60, 66, 72]
    assert [f["train_rows"] for f in folds] == list(ORIGINS)
    assert len(folds) == 5
    for f in folds:
        assert f["train_end"] < f["validation_start"]
        assert f["horizon_months"] == f["validation_rows"] == HORIZON == 24
        assert f["validation_end"] < "2024-01-01"
        assert len(f["predictions"]) == 24
    assert [f["validation_start"] for f in folds] == [
        "2020-01-01",
        "2020-07-01",
        "2021-01-01",
        "2021-07-01",
        "2022-01-01",
    ]
    months = {p["month"] for f in folds for p in f["predictions"]}
    assert len(months) == 48  # Explicitly dependent, overlapping windows.


@pytest.mark.parametrize("origin", ORIGINS)
def test_post_origin_targets_do_not_change_fit_or_predictions(frame, origin):
    original = evaluate_window(frame, origin)
    changed = frame.copy()
    changed.loc[origin:, "revenue_usd"] *= 7
    mutated = evaluate_window(changed, origin)
    for key in [
        "trend_slope_usd_per_month",
        "trend_intercept_usd",
        "forest_feature_importances",
        "train",
    ]:
        assert original[key] == mutated[key]
    for before, after in zip(original["predictions"], mutated["predictions"]):
        assert before["prediction_usd"] == after["prediction_usd"]
        assert before["baseline_usd"] == after["baseline_usd"]
    assert original["validation"] != mutated["validation"]


def test_final_holdout_does_not_affect_any_evaluation_result(frame, results):
    changed = frame.copy()
    changed.loc[
        changed.month >= "2024-01-01",
        ["revenue_usd", "covers_served", "avg_ticket_usd"],
    ] *= 13
    assert evaluate(changed) == results
    assert results["final_holdout_used"] is False


def test_learning_sizes_share_origins_and_validation_dates(results):
    assert len(results["learning_windows"]) == 25
    expected = {f["origin_months"]: f for f in results["folds"]}
    for record in results["learning_windows"]:
        assert record["train_rows"] in LEARNING_SIZES
        fold = expected[record["origin_months"]]
        assert record["train_end"] == fold["train_end"]
        assert record["validation_start"] == fold["validation_start"]
        assert record["validation_end"] == fold["validation_end"]
        assert record["validation_rows"] == 24
        start = pd.Timestamp(record["train_start"])
        end = pd.Timestamp(record["train_end"])
        assert (end.year - start.year) * 12 + end.month - start.month + 1 == record[
            "train_rows"
        ]


def test_metrics_and_sample_std_are_correct(results):
    folds = results["folds"]
    for fold in folds:
        errors = np.array([p["error_usd"] for p in fold["predictions"]])
        assert fold["validation"]["rmse_usd"] == pytest.approx(
            np.sqrt(np.mean(errors**2))
        )
        assert fold["validation"]["mae_usd"] == pytest.approx(np.mean(abs(errors)))
        assert fold["validation"]["mean_error_usd"] == pytest.approx(np.mean(errors))
    values = [f["validation"]["rmse_usd"] for f in folds]
    score = results["cv_summary"]["validation"]["rmse_usd"]
    assert score["mean"] == pytest.approx(np.mean(values))
    assert score["std"] == pytest.approx(np.std(values, ddof=1))


def test_every_adjustment_uses_new_model_and_original_parameters(frame, monkeypatch):
    import brasaland_sales.evaluation as module
    from brasaland_sales.experiment import TrendForest

    instances = []

    class SpyForest(TrendForest):
        def fit(self, data):
            instances.append(self)
            return super().fit(data)

    monkeypatch.setattr(module, "TrendForest", SpyForest)
    evaluate(frame)
    assert len(instances) == len({id(m) for m in instances}) == 30
    for m in instances:
        params = m.forest_.get_params()
        assert (
            params["n_estimators"],
            params["max_depth"],
            params["min_samples_leaf"],
            params["random_state"],
        ) == (300, 3, 3, 42)
        assert m.train_end_ < pd.Timestamp("2024-01-01")


def test_invalid_history_is_not_silently_used(frame):
    with pytest.raises(ValueError, match="96 monthly"):
        training_history(frame.drop(index=10))
    with pytest.raises(ValueError, match="origin"):
        evaluate_window(frame, 84)
    with pytest.raises(ValueError, match="Training size"):
        evaluate_window(frame, 48, 54)


def test_report_and_artifacts_preserve_previous_experiment(results, tmp_path):
    import copy
    import hashlib
    import json

    from brasaland_sales.evaluation import save_artifacts
    from brasaland_sales.evaluation_report import render_report

    previous = ROOT / "data/eval/sales_forecasting"
    names = ["metrics.json", "test_predictions.csv", "forecast.png", "model.joblib"]
    hashes = {n: hashlib.sha256((previous / n).read_bytes()).hexdigest() for n in names}
    report = tmp_path / "evaluation_report.md"
    output = tmp_path / "sales_forecasting/evaluation"
    data = copy.deepcopy(results)
    render_report(data, output, report)
    save_artifacts(data, output)
    assert (
        json.loads((output / "metrics.json").read_text())["final_holdout_used"] is False
    )
    assert len(pd.read_csv(output / "cv_scores.csv")) == 5
    assert len(pd.read_csv(output / "learning_scores.csv")) == 25
    assert len(pd.read_csv(output / "cv_predictions.csv")) == 120
    assert len(pd.read_csv(output / "learning_predictions.csv")) == 600
    for metric in ["mae", "rmse"]:
        assert (output / f"learning_curve_{metric}.png").stat().st_size > 1000
    text = report.read_text()
    assert "Diagnóstico:" in text and "Acción concreta:" in text and "ddof=1" in text
    assert "costes" in text and "2024–2025" in text
    assert hashes == {
        n: hashlib.sha256((previous / n).read_bytes()).hexdigest() for n in names
    }
