# Evidencia de validación — 2026-10-12

Base revisada: PR #25 abierta, head remoto `96e75cdc776fac2f43fb531e70f73d76828af8a6`.
Trabajo en checkout aislado de `feature/brasaland-sales-regression`.

| Comprobación | Resultado |
| --- | --- |
| Nuevas pruebas `tests/pipelines/test_sales_forecasting.py`, entorno uv del experimento | **14 passed** |
| Backend + pipeline previo + script nocturno, PostgreSQL 16 desechable | **211 passed, 0 skipped** |
| `npm run typecheck`, raíz | PASS |
| Ruff en nuevo módulo, entrypoint y pruebas | PASS |
| Mypy con configuración del experimento, módulo y entrypoint | PASS |
| `uv build --project experiments/sales_forecasting --python 3.12` | wheel y sdist OK |
| Dos ejecuciones completas del experimento | Los cuatro artefactos idénticos byte por byte |
| Gráfica | Inspeccionada: reales, modelo, baseline, ejes USD y banda etiquetada |

Las regresiones existentes se ejecutaron con el entorno propio de la API:

```bash
uv sync --project services/api --extra dev --python 3.12 --frozen
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/api:. \
  SUPPLIERS_DB_PATH=/tmp/brasaland-sales-tests-users-pg.json \
  TEST_DATABASE_URL=postgresql://sales_test:sales_test_local@localhost:15432/sales_regression_test \
  services/api/.venv/bin/python -m pytest \
  services/api/tests tests/pipelines/test_pipeline.py tests/scripts -q
```

La URL corresponde exclusivamente al contenedor temporal de pruebas creado para
esta entrega, eliminado al terminar; no es configuración de producción. No se
modificó `services/api/pyproject.toml` ni su lockfile. Las pruebas de ventas se
ejecutan por separado en su entorno; si faltan `brasaland_sales` o `joblib`, se
omiten explícitamente en vez de romper la colección de pruebas del backend.

Se observaron los mismos 88 avisos de deprecación de SQLite y aviso de logging de
Prefect al cerrar presentes en la base; todas las pruebas terminaron correctamente.
No hubo cambios en UI; no se levantó servidor frontend ni se alteraron sus builds.

SHA-256 de artefactos reproducidos:

| Artefacto | SHA-256 |
| --- | --- |
| `metrics.json` | `d0221c8ed0d057512ffd6fd5080d8746979c5d2d1d5a761f6597967340f16c5d` |
| `test_predictions.csv` | `3469b72734ad00c879d61216a69c5337da2ec72c14a87d4792b974efadc81759` |
| `forecast.png` | `4f794b3fd73780a3eb6c207a4350ca7a38d5b126f9d6b6d99ceb9b529eb48a6c` |
| `model.joblib` | `f8ce28f941d1f225a24da04741542f729292077b5991671780c09e4b203ecdfa` |
