# Evaluación del modelo existente de Brasaland

Continuación aislada de PR #26, base `0b0b705`, rama nueva
`feature/regression-model-eval`. No modifica ni fusiona #26 ni #25.

El [informe regenerable](../../data/eval/evaluation_report.md) contiene método,
resultados por fold, curvas MAE/RMSE, diagnóstico provisional, acción concreta
y limitaciones. Se evalúa `TrendForest` existente con sus mismos parámetros:
calendario, tendencia lineal y forest estacional; sin añadir lags, medias móviles,
escalado o nuevas dependencias. Se reutiliza el entorno uv y su lockfile.

Desde la raíz:

```bash
uv sync --project experiments/sales_forecasting --frozen
uv run --project experiments/sales_forecasting --frozen python scripts/evaluate_sales_model.py
uv run --project experiments/sales_forecasting --frozen pytest tests/pipelines/test_sales_forecasting.py tests/pipelines/test_sales_model_evaluation.py -q
uv run --project experiments/sales_forecasting --frozen ruff check experiments/sales_forecasting/src/brasaland_sales/evaluation.py experiments/sales_forecasting/src/brasaland_sales/evaluation_report.py scripts/evaluate_sales_model.py tests/pipelines/test_sales_model_evaluation.py
uv run --project experiments/sales_forecasting --frozen mypy --config-file experiments/sales_forecasting/pyproject.toml experiments/sales_forecasting/src scripts/evaluate_sales_model.py
uv build --project experiments/sales_forecasting --python 3.12
npm run typecheck
```

Solo se evalúa 2016–2023. Cinco orígenes tras 48/54/60/66/72 meses,
24 meses de validación desde cada origen. Curvas: últimas 24/30/36/42/48
observaciones antes de cada mismo origen, con ventanas de validación idénticas.
Media ± DE muestral (`ddof=1`) descriptiva: los folds están solapados.

Artefactos independientes bajo `data/eval/sales_forecasting/evaluation/`:

- `metrics.json`: cinco folds, 25 ajustes de curvas, predicciones, resúmenes y diagnóstico.
- `cv_scores.csv`, `learning_scores.csv`: fechas, tamaños y métricas de cada ajuste.
- `cv_predictions.csv`, `learning_predictions.csv`: predicción/real/baseline y error firmado.
- `learning_curve_mae.png`, `learning_curve_rmse.png`: entrenamiento y validación.

El CLI admite `--dataset`, `--output` y `--report`. No carga el modelo serializado
anterior: construye una instancia nueva por ajuste. No lee las métricas ni
predicciones finales de #26 para decidir diagnóstico o acción; descarta los
objetivos de 2024–2025 antes de calcular estadísticas. El hash efectivo refleja
solo fechas e ingresos del entrenamiento, no los valores del test final.

Resultados CV: RMSE **27.857,76 ± 3.524,87 USD**, MAE
**24.124,08 ± 3.285,93 USD**. Baseline: RMSE
**56.949,34 ± 4.923,29 USD**, MAE **48.022,11 ± 4.080,88 USD**.
Diagnóstico provisional: **underfitting estructural de la estacionalidad creciente**;
la evidencia y verificación de una posible variante multiplicativa se explican
en el informe, sin implementar o prometer esa mejora.

Evidencia de checks y preservación de artefactos: [VALIDATION.md](VALIDATION.md).
