"""Fixed-origin 24-month forecast with training-only temporal calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, normaltest
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

EXPECTED_COLUMNS = ["month", "revenue_usd", "covers_served", "avg_ticket_usd", "market"]
RANDOM_STATE = 42


def load_data(path: Path) -> pd.DataFrame:
    """Reject missing/invalid observations instead of silently changing the 8/2 split."""
    frame = pd.read_csv(path)
    if list(frame.columns) != EXPECTED_COLUMNS:
        raise ValueError(f"Expected exact columns: {EXPECTED_COLUMNS}")
    if frame.isna().any().any():
        raise ValueError("Missing values require an explicit data-quality decision")
    if not frame["market"].eq("consolidated").all():
        raise ValueError("This experiment requires exactly the consolidated monthly series")
    frame["month"] = pd.to_datetime(frame["month"], format="%Y-%m-%d", errors="raise")
    for column in ["revenue_usd", "covers_served", "avg_ticket_usd"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        values = frame[column].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError(f"{column} must be finite and positive")
    if (frame["covers_served"] % 1 != 0).any():
        raise ValueError("covers_served must contain integers")
    frame = frame.sort_values("month").reset_index(drop=True)
    expected = pd.date_range("2016-01-01", "2025-12-01", freq="MS")
    if not pd.DatetimeIndex(frame["month"]).equals(expected):
        raise ValueError("Require all 120 distinct monthly observations for 2016–2025")
    return frame


def split_data(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """First eight calendar years / last two calendar years, never a random split."""
    train = frame.loc[frame["month"] < pd.Timestamp("2024-01-01")].copy()
    test = frame.loc[frame["month"] >= pd.Timestamp("2024-01-01")].copy()
    if len(train) != 96 or len(test) != 24 or train["month"].max() >= test["month"].min():
        raise ValueError("Expected 96 training and 24 strictly later test months")
    return train, test


def calendar_features(dates: pd.Series) -> np.ndarray:
    """Only deterministic, future-known features; no realized covers/ticket/revenue."""
    month = dates.dt.month.to_numpy(dtype=float)
    return np.column_stack([month, np.sin(2 * np.pi * month / 12), np.cos(2 * np.pi * month / 12)])


def time_index(dates: pd.Series) -> np.ndarray:
    return ((dates.dt.year - 2016) * 12 + dates.dt.month - 1).to_numpy().reshape(-1, 1)


class TrendForest:
    """Extrapolatable linear trend plus a small forest on seasonal residuals.

    Both fitted stages use the same training partition; no scaling is needed.
    Hyperparameters are fixed before viewing the test results.
    """

    def fit(self, frame: pd.DataFrame) -> TrendForest:
        self.train_end_ = frame["month"].max()
        self.trend_ = LinearRegression().fit(time_index(frame["month"]), frame["revenue_usd"])
        residuals = frame["revenue_usd"] - self.trend_.predict(time_index(frame["month"]))
        self.forest_ = RandomForestRegressor(
            n_estimators=300,
            max_depth=3,
            min_samples_leaf=3,
            random_state=RANDOM_STATE,
            n_jobs=1,
        ).fit(calendar_features(frame["month"]), residuals)
        return self

    def predict(self, dates: pd.Series) -> np.ndarray:
        trend = self.trend_.predict(time_index(dates))
        return np.maximum(0, trend + self.forest_.predict(calendar_features(dates)))


def seasonal_baseline(train: pd.DataFrame, dates: pd.Series) -> np.ndarray:
    """Repeat the last observed year's seasonality for the entire 24-month horizon."""
    last_year = train.tail(12).set_index(train.tail(12)["month"].dt.month)["revenue_usd"]
    return dates.dt.month.map(last_year).to_numpy(dtype=float)


def calibrate_band(train: pd.DataFrame, coverage: float = 0.9) -> tuple[float, list[dict]]:
    """Two disjoint 24-month rolling-origin validations contained in training.

    Pooled absolute errors and a finite-sample upper empirical quantile estimate
    variability. Time dependence prevents claiming exchangeable conformal coverage.
    """
    if not 0 < coverage < 1:
        raise ValueError("coverage must be between zero and one")
    errors: list[float] = []
    folds = []
    for end in (48, 72):
        fit_frame, validation = train.iloc[:end], train.iloc[end : end + 24]
        if len(validation) != 24 or fit_frame["month"].max() >= validation["month"].min():
            raise ValueError("Calibration requires strictly future 24-month training folds")
        model = TrendForest().fit(fit_frame)
        prediction = model.predict(validation["month"])
        errors.extend(np.abs(validation["revenue_usd"].to_numpy() - prediction).tolist())
        folds.append(
            {
                "train_start": str(fit_frame["month"].min().date()),
                "train_end": str(model.train_end_.date()),
                "validation_start": str(validation["month"].min().date()),
                "validation_end": str(validation["month"].max().date()),
                "horizon_months": 24,
                "rmse_usd": float(
                    np.sqrt(mean_squared_error(validation["revenue_usd"], prediction))
                ),
            }
        )
    rank = min(len(errors), math.ceil((len(errors) + 1) * coverage))
    return float(np.sort(errors)[rank - 1]), folds


def regression_metrics(actual: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    mse = float(mean_squared_error(actual, prediction))
    return {
        "mse_usd2": mse,
        "rmse_usd": float(np.sqrt(mse)),
        "mae_usd": float(mean_absolute_error(actual, prediction)),
        "r2": float(r2_score(actual, prediction)),
        "mape_percent": float(np.mean(np.abs((actual - prediction) / actual)) * 100),
    }


def population_stability(reference: np.ndarray, current: np.ndarray) -> dict:
    """Distribution drift, NOT regression error. Bin edges fitted on train only."""
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, 11)))
    if len(edges) < 2:
        edges = np.array([-np.inf, np.inf])
    else:
        edges[0], edges[-1] = -np.inf, np.inf
    ref_count, _ = np.histogram(reference, bins=edges)
    cur_count, _ = np.histogram(current, bins=edges)
    ref_share = np.maximum(ref_count / len(reference), 1e-6)
    cur_share = np.maximum(cur_count / len(current), 1e-6)
    ref_share /= ref_share.sum()
    cur_share /= cur_share.sum()
    value = float(np.sum((cur_share - ref_share) * np.log(cur_share / ref_share)))
    return {
        "value": value,
        "reference": "train actual revenue",
        "current": "test actual revenue",
        "train_bin_edges": ["-inf", *edges[1:-1].tolist(), "+inf"],
        "smoothing": 1e-6,
        "high_drift_heuristic": value >= 0.25,
    }


def normalized_gini(actual: np.ndarray, prediction: np.ndarray) -> float | None:
    """Normalized concentration/ranking score, with average treatment of tied scores."""

    def concentration(scores: np.ndarray) -> float:
        grouped = pd.DataFrame({"actual": actual, "score": scores})
        grouped["actual"] = grouped.groupby("score")["actual"].transform("mean")
        ordered = grouped.sort_values("score", ascending=False)["actual"].to_numpy()
        n = len(ordered)
        return float((np.cumsum(ordered).sum() / ordered.sum() - (n + 1) / 2) / n)

    denominator = concentration(actual)
    return concentration(prediction) / denominator if denominator else None


def residual_normality(actual: np.ndarray, prediction: np.ndarray) -> dict:
    """Course K2: D'Agostino-Pearson on held-out residuals, never an error score.

    A large p-value does not prove normality, zero bias or independence. With
    only 24 serial observations, the standard p-value is exploratory.
    """
    actual = np.asarray(actual, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    if actual.ndim != 1 or actual.shape != prediction.shape or len(actual) < 8:
        raise ValueError("K2 requires matching one-dimensional arrays and at least eight residuals")
    residuals = actual - prediction
    if not np.isfinite(residuals).all() or np.ptp(residuals) == 0:
        raise ValueError("K2 requires finite, nonconstant residuals")
    result = normaltest(residuals, nan_policy="raise")
    return {
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "n_residuals": len(residuals),
        "alpha": 0.05,
        "reject_normality": bool(result.pvalue < 0.05),
        "definition": "D'Agostino-Pearson K² = Z_skewness² + Z_kurtosis² on test actual - prediction",
        "caveat": "Exploratory under temporal dependence; does not test zero bias or independence",
    }


def run(dataset: Path, output: Path) -> dict:
    frame = load_data(dataset)
    train, test = split_data(frame)
    width, folds = calibrate_band(train)
    model = TrendForest().fit(train)
    # Freeze all fitted parameters and band before consuming test targets.
    prediction = model.predict(test["month"])
    baseline = seasonal_baseline(train, test["month"])
    actual = test["revenue_usd"].to_numpy()
    lower, upper = np.maximum(0, prediction - width), prediction + width
    model_metrics = regression_metrics(actual, prediction)
    baseline_metrics = regression_metrics(actual, baseline)
    k2 = residual_normality(actual, prediction)
    report = {
        "software": {
            "python": platform.python_version(),
            **{
                package: version(package)
                for package in ["numpy", "pandas", "scikit-learn", "scipy", "matplotlib", "joblib"]
            },
        },
        "random_state": RANDOM_STATE,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "target": "consolidated monthly revenue_usd",
        "currency": "USD",
        "forecast_origin": "2023-12-31",
        "horizon_months": 24,
        "train": {"start": "2016-01-01", "end": "2023-12-01", "rows": len(train)},
        "test": {"start": "2024-01-01", "end": "2025-12-01", "rows": len(test)},
        "model": model_metrics,
        "baseline": baseline_metrics,
        "beats_baseline_rmse": model_metrics["rmse_usd"] < baseline_metrics["rmse_usd"],
        "psi_diagnostic": population_stability(train["revenue_usd"].to_numpy(), actual),
        "normalized_gini_diagnostic": normalized_gini(actual, prediction),
        "k2_score": k2["statistic"],
        "k2_normality": k2,
        "k2_status": "Confirmed in the official reference solution of the original regression activity",
        "kendall_tau_b_diagnostic": float(kendalltau(actual, prediction).statistic),
        "band": {
            "label": "Estimated variability, nominal 90%; coverage not guaranteed",
            "half_width_usd": width,
            "calibration_folds": folds,
            "test_pointwise_coverage": float(np.mean((actual >= lower) & (actual <= upper))),
        },
        "trend_slope_usd_per_month": float(model.trend_.coef_[0]),
        "forest_feature_importances": dict(
            zip(
                ["month_number", "month_sin", "month_cos"],
                model.forest_.feature_importances_.tolist(),
            )
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(
        {
            "month": test["month"].dt.strftime("%Y-%m-%d"),
            "actual_usd": actual,
            "prediction_usd": prediction,
            "seasonal_baseline_usd": baseline,
            "estimated_lower_usd": lower,
            "estimated_upper_usd": upper,
        }
    )
    table.to_csv(output / "test_predictions.csv", index=False, float_format="%.6f")
    (output / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    joblib.dump(model, output / "model.joblib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(test["month"], actual, label="Ventas observadas", marker="o")
    ax.plot(test["month"], prediction, label="Tendencia + Random Forest")
    ax.plot(test["month"], baseline, label="Baseline estacional (último año)", linestyle="--")
    ax.fill_between(
        test["month"],
        lower,
        upper,
        alpha=0.2,
        label="Variabilidad estimada (90% nominal; sin garantía)",
    )
    ax.set(
        title="Brasaland · prueba 2024–2025 · origen fijo: cierre de 2023",
        ylabel="Ventas mensuales consolidadas (USD)",
        xlabel="Mes",
    )
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(
        output / "forecast.png", dpi=160, metadata={"Software": "Brasaland sales experiment"}
    )
    plt.close(fig)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/raw/brasaland_sales.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/eval/sales_forecasting"))
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.output), indent=2))
