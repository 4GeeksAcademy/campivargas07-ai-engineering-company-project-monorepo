# Experimento de ventas Brasaland

Entorno Python independiente de `services/api`: no instala modelos en la API,
no añade endpoints, workers ni dashboard. Python 3.12 y dependencias fijadas por
`uv.lock`. Ejecutar desde la raíz del monorepo:

```bash
uv sync --project experiments/sales_forecasting --frozen
uv run --project experiments/sales_forecasting --frozen python scripts/train_sales_model.py
uv run --project experiments/sales_forecasting --frozen pytest tests/pipelines/test_sales_forecasting.py -q
uv run --project experiments/sales_forecasting --frozen ruff check experiments/sales_forecasting/src scripts/train_sales_model.py tests/pipelines/test_sales_forecasting.py
uv run --project experiments/sales_forecasting --frozen mypy --config-file experiments/sales_forecasting/pyproject.toml experiments/sales_forecasting/src scripts/train_sales_model.py
uv build --project experiments/sales_forecasting
```

El script admite `--dataset` y `--output`. Abortar ante ausencia de datos, esquema
incorrecto, meses faltantes/duplicados, valores ausentes o no positivos. No hay
fallback sintético ni descarga implícita. Los tests requieren este entorno;
las regresiones del backend se ejecutan por separado con su propio entorno.

Resultados, fuente, fórmulas y explicación para el profesor:
[informe](../../docs/sales-forecasting/README.md).
