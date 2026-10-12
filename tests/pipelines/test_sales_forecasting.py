"""Actual academy data; no simulated sales or test-target leakage."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

try:
    import joblib
    from brasaland_sales.experiment import (
        TrendForest,
        calendar_features,
        calibrate_band,
        load_data,
        normalized_gini,
        population_stability,
        regression_metrics,
        run,
        seasonal_baseline,
        split_data,
    )
except ModuleNotFoundError as error:
    if error.name in {"joblib", "brasaland_sales"}:
        pytest.skip(
            "Sales tests require the isolated uv experiment environment",
            allow_module_level=True,
        )
    raise


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/raw/brasaland_sales.csv"


@pytest.fixture
def frame():
    return load_data(DATA)


def test_dataset_matches_pinned_official_source():
    manifest = json.loads((ROOT / "docs/sales-forecasting/source.json").read_text())
    assert (
        hashlib.sha256(DATA.read_bytes()).hexdigest()
        == manifest["files"]["data/raw/brasaland_sales.csv"]["sha256"]
    )


def test_exact_eight_two_year_split(frame):
    train, test = split_data(frame)
    assert len(train) == 96 and len(test) == 24
    assert set(train.month.dt.year) == set(range(2016, 2024))
    assert set(test.month.dt.year) == {2024, 2025}
    assert train.month.max() < test.month.min()
    assert train.month.max() == pd.Timestamp("2023-12-01")
    assert test.month.min() == pd.Timestamp("2024-01-01")


@pytest.mark.parametrize(
    "fault", ["missing_month", "duplicate", "null", "negative", "schema"]
)
def test_invalid_official_series_rejected(frame, tmp_path, fault):
    damaged = frame.copy()
    if fault == "missing_month":
        damaged = damaged.drop(index=10)
    elif fault == "duplicate":
        damaged.loc[10, "month"] = damaged.loc[9, "month"]
    elif fault == "null":
        damaged.loc[10, "revenue_usd"] = np.nan
    elif fault == "negative":
        damaged.loc[10, "revenue_usd"] = -1
    else:
        damaged = damaged.rename(columns={"month": "date"})
    path = tmp_path / "invalid.csv"
    damaged.to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_data(path)


def test_unsorted_csv_is_sorted_before_split(frame, tmp_path):
    path = tmp_path / "reversed.csv"
    frame.iloc[::-1].to_csv(path, index=False)
    pd.testing.assert_frame_equal(load_data(path), frame)


def test_calendar_transform_known_values_and_no_contemporaneous_features(frame):
    features = calendar_features(frame.month.iloc[:3])
    np.testing.assert_allclose(features[:, 0], [1, 2, 3])
    np.testing.assert_allclose(features[0, 1:], [0.5, np.sqrt(3) / 2])
    assert features.shape == (3, 3)


def test_fitted_trend_residuals_and_future_predictions_ignore_test_targets(frame):
    train, test = split_data(frame)
    model = TrendForest().fit(train)
    assert model.train_end_ < test.month.min()
    # Verify fitted trend against independent least-squares calculation.
    time = np.arange(96)
    slope, intercept = np.polyfit(time, train.revenue_usd, 1)
    np.testing.assert_allclose(model.trend_.coef_[0], slope)
    np.testing.assert_allclose(model.trend_.intercept_, intercept)
    predicted = model.predict(test.month)
    corrupted = test.copy()
    corrupted[["revenue_usd", "covers_served", "avg_ticket_usd"]] = 1e12
    np.testing.assert_array_equal(predicted, model.predict(corrupted.month))
    np.testing.assert_array_equal(
        predicted, TrendForest().fit(train).predict(test.month)
    )


def test_band_has_training_only_folds_and_same_24_month_horizon(frame):
    train, test = split_data(frame)
    width, folds = calibrate_band(train)
    assert width > 0 and len(folds) == 2
    for fold in folds:
        assert fold["train_end"] < fold["validation_start"]
        assert fold["validation_end"] < str(test.month.min().date())
        assert fold["horizon_months"] == 24
    assert [f["validation_end"] for f in folds] == ["2021-12-01", "2023-12-01"]
    # Verify the width from the independently collected historical residuals.
    errors = []
    for end in [48, 72]:
        prediction = (
            TrendForest()
            .fit(train.iloc[:end])
            .predict(train.iloc[end : end + 24].month)
        )
        errors.extend(
            abs(train.iloc[end : end + 24].revenue_usd.to_numpy() - prediction)
        )
    assert width == sorted(errors)[44]  # ceil((48 + 1) * .9) - 1


def test_seasonal_baseline_never_uses_test_year(frame):
    train, test = split_data(frame)
    predicted = seasonal_baseline(train, test.month)
    np.testing.assert_array_equal(predicted[:12], train.tail(12).revenue_usd)
    np.testing.assert_array_equal(predicted[12:], train.tail(12).revenue_usd)


def test_metrics_formulas_and_drift_bins():
    actual, prediction = np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 4.0])
    metrics = regression_metrics(actual, prediction)
    assert metrics["mse_usd2"] == pytest.approx(1 / 3)
    assert metrics["mae_usd"] == pytest.approx(1 / 3)
    assert metrics["r2"] == pytest.approx(0.5)
    assert normalized_gini(actual, actual) == pytest.approx(1)
    assert normalized_gini(actual, -actual) == pytest.approx(-1)
    assert normalized_gini(actual, np.ones(3)) == pytest.approx(0)
    assert normalized_gini(np.ones(3), prediction) is None
    reference = np.arange(1.0, 97.0)
    unchanged = population_stability(reference, reference)
    shifted = population_stability(reference, reference + 1000)
    assert unchanged["value"] == pytest.approx(0)
    assert shifted["value"] > 0.25
    assert unchanged["train_bin_edges"] == shifted["train_bin_edges"]
    assert population_stability(np.ones(5), np.ones(5))["value"] == 0


def test_artifacts_roundtrip_and_k2_not_substituted(tmp_path, frame):
    report = run(DATA, tmp_path)
    assert report["k2_score"] is None
    assert report["train"]["rows"] == 96 and report["test"]["rows"] == 24
    predictions = pd.read_csv(tmp_path / "test_predictions.csv")
    assert len(predictions) == 24
    model = joblib.load(tmp_path / "model.joblib")
    np.testing.assert_allclose(
        model.predict(frame.tail(24).month), predictions.prediction_usd
    )
    assert (tmp_path / "forecast.png").stat().st_size > 1000
    # Exercise the entire entrypoint with changed future outcomes and covariates.
    # Fitted predictions, seasonal baseline and calibration must remain identical.
    changed = frame.copy()
    changed.loc[
        changed.month >= "2024-01-01",
        ["revenue_usd", "covers_served", "avg_ticket_usd"],
    ] *= 2
    changed_path = tmp_path / "changed_test.csv"
    changed.to_csv(changed_path, index=False)
    changed_report = run(changed_path, tmp_path / "changed")
    changed_predictions = pd.read_csv(tmp_path / "changed/test_predictions.csv")
    for column in [
        "prediction_usd",
        "seasonal_baseline_usd",
        "estimated_lower_usd",
        "estimated_upper_usd",
    ]:
        np.testing.assert_array_equal(predictions[column], changed_predictions[column])
    assert changed_report["band"]["half_width_usd"] == report["band"]["half_width_usd"]
    assert changed_report["model"]["mse_usd2"] != report["model"]["mse_usd2"]
