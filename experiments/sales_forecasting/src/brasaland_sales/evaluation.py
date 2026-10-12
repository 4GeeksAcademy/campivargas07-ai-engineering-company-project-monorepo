"""Training-only evaluation of the existing TrendForest at a fixed 24-month horizon."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from brasaland_sales.evaluation_report import render_report
from brasaland_sales.experiment import (
    RANDOM_STATE,
    TrendForest,
    load_data,
    regression_metrics,
    seasonal_baseline,
)

ORIGINS = (48, 54, 60, 66, 72)
LEARNING_SIZES = (24, 30, 36, 42, 48)
HORIZON = 24


def training_history(frame: pd.DataFrame) -> pd.DataFrame:
    """Discard the final holdout before deriving any evaluation statistic or feature."""
    history = frame.loc[frame["month"] < pd.Timestamp("2024-01-01")].copy()
    history = history.sort_values("month").reset_index(drop=True)
    if not pd.DatetimeIndex(history["month"]).equals(
        pd.date_range("2016-01-01", "2023-12-01", freq="MS")
    ):
        raise ValueError("Evaluation requires exactly the 96 monthly training observations")
    values = history["revenue_usd"].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Training revenues must be finite and positive")
    return history


def error_metrics(actual: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    values = regression_metrics(actual, prediction)
    return {
        "mae_usd": values["mae_usd"],
        "rmse_usd": values["rmse_usd"],
        "mean_error_usd": float(np.mean(prediction - actual)),
    }


def evaluate_window(frame: pd.DataFrame, origin: int, training_months: int | None = None) -> dict:
    """Fit a fresh model using only observations strictly preceding this origin.

    Expanding history for CV; most recent fixed-size history for learning curves.
    Targets following the origin are used only after predictions are frozen.
    """
    history = training_history(frame)
    if origin not in ORIGINS:
        raise ValueError(f"origin must be one of {ORIGINS}")
    size = origin if training_months is None else training_months
    if size < 24 or size > origin:
        raise ValueError("Training size must be between 24 and the origin")
    fitted = history.iloc[origin - size : origin].copy()
    validation = history.iloc[origin : origin + HORIZON].copy()
    model = TrendForest().fit(fitted)
    prediction = model.predict(validation["month"])
    baseline = seasonal_baseline(fitted, validation["month"])
    actual = validation["revenue_usd"].to_numpy()
    return {
        "origin_months": origin,
        "train_start": str(fitted["month"].min().date()),
        "train_end": str(model.train_end_.date()),
        "validation_start": str(validation["month"].min().date()),
        "validation_end": str(validation["month"].max().date()),
        "train_rows": len(fitted),
        "validation_rows": len(validation),
        "horizon_months": HORIZON,
        "train": error_metrics(fitted["revenue_usd"].to_numpy(), model.predict(fitted["month"])),
        "validation": error_metrics(actual, prediction),
        "baseline_validation": error_metrics(actual, baseline),
        "trend_slope_usd_per_month": float(model.trend_.coef_[0]),
        "trend_intercept_usd": float(model.trend_.intercept_),
        "forest_feature_importances": model.forest_.feature_importances_.tolist(),
        "train_december_mean_error_usd": float(
            np.mean(
                model.predict(fitted.loc[fitted["month"].dt.month == 12, "month"])
                - fitted.loc[fitted["month"].dt.month == 12, "revenue_usd"].to_numpy()
            )
        ),
        "predictions": [
            {
                "month": str(date.date()),
                "actual_usd": float(y),
                "prediction_usd": float(p),
                "baseline_usd": float(b),
                "error_usd": float(p - y),
            }
            for date, y, p, b in zip(validation["month"], actual, prediction, baseline)
        ],
    }


def summarize(records: list[dict]) -> dict:
    """Equal weight per fold; sample standard deviation (ddof=1), descriptive only."""
    result: dict[str, dict] = {}
    for partition in ("train", "validation", "baseline_validation"):
        result[partition] = {}
        for metric in ("mae_usd", "rmse_usd", "mean_error_usd"):
            values = [record[partition][metric] for record in records]
            result[partition][metric] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=1)),
            }
    return result


def evaluate(frame: pd.DataFrame) -> dict:
    """Use only 2016–2023; neither holdout targets nor their hash enter results."""
    history = training_history(frame)
    folds = [evaluate_window(history, origin) for origin in ORIGINS]
    learning = [
        evaluate_window(history, origin, size) for size in LEARNING_SIZES for origin in ORIGINS
    ]
    summaries = [
        {
            "train_rows": size,
            "scores": summarize([row for row in learning if row["train_rows"] == size]),
        }
        for size in LEARNING_SIZES
    ]
    return {
        "training_sha256": hashlib.sha256(
            history[["month", "revenue_usd"]].to_csv(index=False).encode()
        ).hexdigest(),
        "random_state": RANDOM_STATE,
        "horizon_months": HORIZON,
        "evaluation_start": "2016-01-01",
        "evaluation_end": "2023-12-01",
        "final_holdout_used": False,
        "std_convention": "sample standard deviation, ddof=1; descriptive, overlapping folds",
        "signed_error_convention": "prediction - actual; negative = underprediction",
        "folds": folds,
        "cv_summary": summarize(folds),
        "learning_windows": learning,
        "learning_summary": summaries,
    }


def save_artifacts(result: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    for group, filename in [
        ("folds", "cv_scores.csv"),
        ("learning_windows", "learning_scores.csv"),
    ]:
        rows = []
        predictions = []
        for record in result[group]:
            row = {
                key: value
                for key, value in record.items()
                if key
                not in {
                    "predictions",
                    "train",
                    "validation",
                    "baseline_validation",
                    "forest_feature_importances",
                }
            }
            for partition in ("train", "validation", "baseline_validation"):
                row.update(
                    {f"{partition}_{key}": value for key, value in record[partition].items()}
                )
            rows.append(row)
            predictions.extend(
                [
                    {
                        "origin_months": record["origin_months"],
                        "train_rows": record["train_rows"],
                        **p,
                    }
                    for p in record["predictions"]
                ]
            )
        pd.DataFrame(rows).to_csv(output / filename, index=False, float_format="%.6f")
        pd.DataFrame(predictions).to_csv(
            output / filename.replace("scores", "predictions"), index=False, float_format="%.6f"
        )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for metric in ("mae_usd", "rmse_usd"):
        fig, ax = plt.subplots(figsize=(9, 5))
        sizes = [row["train_rows"] for row in result["learning_summary"]]
        for partition, label, color in [
            ("train", "Entrenamiento", "#1565c0"),
            ("validation", "Validación: horizonte fijo de 24 meses", "#d84315"),
        ]:
            mean = np.array(
                [row["scores"][partition][metric]["mean"] for row in result["learning_summary"]]
            )
            std = np.array(
                [row["scores"][partition][metric]["std"] for row in result["learning_summary"]]
            )
            ax.plot(sizes, mean, marker="o", label=label, color=color)
            ax.fill_between(
                sizes,
                np.maximum(0, mean - std),
                mean + std,
                color=color,
                alpha=0.15,
                label=f"{label}: ±1 DE descriptiva; folds solapados",
            )
        ax.set(
            xlabel="Meses recientes usados para ajustar en cada origen",
            ylabel=f"{metric.split('_')[0].upper()} (USD)",
            xticks=sizes,
            title="Brasaland · curva de aprendizaje · solo historia 2016–2023",
        )
        ax.legend(fontsize=8)
        ax.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(
            output / f"learning_curve_{metric.split('_')[0]}.png",
            dpi=160,
            metadata={"Software": "Brasaland regression evaluation"},
        )
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/raw/brasaland_sales.csv"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/eval/sales_forecasting/evaluation")
    )
    parser.add_argument("--report", type=Path, default=Path("data/eval/evaluation_report.md"))
    args = parser.parse_args()
    result = evaluate(load_data(args.dataset))
    render_report(result, args.output, args.report)
    save_artifacts(result, args.output)
    print(json.dumps(result["cv_summary"], indent=2))
