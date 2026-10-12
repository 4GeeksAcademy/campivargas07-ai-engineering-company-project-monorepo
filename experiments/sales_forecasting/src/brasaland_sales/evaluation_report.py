"""Render a reproducible evaluation narrative from training-only evidence."""

import os
from pathlib import Path

import numpy as np


def render_report(result: dict, output: Path, report_path: Path) -> None:
    cv = result["cv_summary"]
    small, large = result["learning_summary"][0], result["learning_summary"][-1]
    reduction = 100 * (
        1
        - large["scores"]["validation"]["rmse_usd"]["mean"]
        / small["scores"]["validation"]["rmse_usd"]["mean"]
    )
    december = [
        p["error_usd"] for f in result["folds"] for p in f["predictions"] if p["month"][5:7] == "12"
    ]
    december_mean = float(np.mean(december))
    train_december = float(np.mean([f["train_december_mean_error_usd"] for f in result["folds"]]))
    improving = all(
        large["scores"][part]["rmse_usd"]["mean"] < small["scores"][part]["rmse_usd"]["mean"]
        for part in ("train", "validation")
    )
    if improving and all(error < 0 for error in december):
        diagnosis = "Underfitting estructural provisional de la estacionalidad creciente"
        explanation = (
            "Ambas curvas mejoran con más historia y todos los errores de diciembre en "
            "validación son negativos. La tendencia crece, pero el forest de calendario "
            "aprende un efecto aditivo fijo sin interacción con el nivel temporal. "
            "Este patrón es compatible con sesgo estructural de amplitud estacional y "
            "estimación de tendencia con poca historia, no una prueba de sobreajuste "
            "generalizado. La clasificación es provisional: las curvas no separan "
            "causalmente sesgo y varianza por sí solas."
        )
        action = (
            "Evaluar una variante multiplicativa: ajustar tendencia solo dentro de cada "
            "fold y entrenar el forest sobre ingreso/tendencia − 1, reconstruyendo ingreso "
            "como tendencia × (1 + residuo relativo predicho). Esto permitiría crecer la "
            "amplitud estacional con el nivel de ventas. No se implementa la corrección "
            "ni se promete mejora en esta tarea de evaluación."
        )
    else:
        diagnosis = "Diagnóstico de underfitting/overfitting no concluyente con estas curvas"
        explanation = "Una brecha aislada no distingue sobreajuste de cambio temporal; auditar residuos antes de decidir."
        action = "Auditar errores por mes y nivel temporal en las mismas ventanas antes de cambiar parámetros."
    result["diagnosis"] = {
        "label": diagnosis,
        "provisional": True,
        "learning_validation_rmse_reduction_percent": reduction,
        "december_validation_mean_error_usd": december_mean,
        "december_train_mean_error_usd": train_december,
        "action": action,
    }

    def number(value: float) -> str:
        return f"{value:,.2f}"

    def spread(scores: dict, partition: str, metric: str) -> str:
        value = scores[partition][metric]
        return f"{number(value['mean'])} ± {number(value['std'])}"

    rows = []
    for f in result["folds"]:
        numbers = [
            f[part][metric]
            for part in ("train", "validation", "baseline_validation")
            for metric in ("mae_usd", "rmse_usd")
        ]
        rows.append(
            f"| {f['origin_months']} | {f['train_start']}–{f['train_end']} / {f['train_rows']} "
            f"| {f['validation_start']}–{f['validation_end']} / {f['validation_rows']} | "
            + " | ".join(number(v) for v in numbers)
            + f" | {number(f['validation']['mean_error_usd'])} |"
        )
    summaries = [
        f"| {label} | "
        + " | ".join(
            spread(cv, part, metric) for metric in ("mae_usd", "rmse_usd", "mean_error_usd")
        )
        + " |"
        for part, label in [
            ("train", "Entrenamiento"),
            ("validation", "Validación"),
            ("baseline_validation", "Baseline en validación"),
        ]
    ]
    learning = [
        f"| {row['train_rows']} | "
        + " | ".join(
            spread(row["scores"], part, metric)
            for metric in ("mae_usd", "rmse_usd")
            for part in ("train", "validation")
        )
        + " |"
        for row in result["learning_summary"]
    ]
    relative = Path(os.path.relpath(output, report_path.parent)).as_posix()
    report = f"""# Evaluación de un Modelo de Regresión — Brasaland

## Método y contexto

Continuación de PR #26 (`0b0b705`). Se reutiliza `TrendForest` sin cambiarlo:
tendencia lineal más RandomForestRegressor de residuos estacionales, calendario,
300 árboles, profundidad 3, mínimo 3 por hoja y semilla 42. **No tiene lags ni
medias móviles**; esta diferencia con la consigna genérica se conserva porque
evaluamos el modelo existente, sin adaptar la clase a `learning_curve`.

Objetivo: `revenue_usd`, ingresos mensuales consolidados de 14 sedes en USD.
Rige el [contexto específico de ventas](../../docs/sales-forecasting/CONTEXT-brasaland.en.md);
el documento general en español describe incidentes. El CSV oficial permanece
intacto: no se generan datos ni se suman monedas diferentes.

Se descarta 2024–2025 antes de derivar estadística alguna. Solo se usan los 96
meses de 2016–2023: cinco orígenes tras 48, 54, 60, 66 y 72 meses, entrenamiento
expansivo anterior al origen y validación de **24 meses**. Tendencia y forest
nuevos en cada ajuste. Predicciones emitidas simultáneamente, sin ver ventas
intermedias. Todas las validaciones terminan antes de 2024. Baseline: repetir
los últimos 12 meses observados para los dos años futuros. No hay selección
de parámetros con validación o test, imputación ni escalado nuevo.

Las validaciones se solapan: 120 posiciones evaluadas pero solo 48 meses
distintos de 2020–2023. Cada fold tiene el mismo peso. **Media ± DE muestral,
`ddof=1`, es dispersión descriptiva**, no intervalo de confianza ni cinco
réplicas independientes. No se usa un splitter aleatorio o con otro horizonte.

## Métrica principal y negocio

**RMSE es principal**: penaliza más los errores grandes que pueden producir
faltantes, compras urgentes o exceso de ingredientes perecederos y desperdicio
en picos de ventas. MAE acompaña como error monetario absoluto promedio para
planificación. Los errores de ingresos en USD no son costes de ingredientes;
faltan márgenes y recetas para traducirlos a compras.

El contexto no fija costes de sobreestimar frente a subestimar. No se inventa
una función de costes ni se afirma qué dirección es más cara. Error firmado =
predicción − real: negativo = subestimación, positivo = sobreestimación; puede
cancelar errores opuestos y no reemplaza MAE/RMSE.

## Resultados por fold (USD)

| Origen (meses) | Entrenamiento: fechas / n | Validación: fechas / n | Train MAE | Train RMSE | Val MAE | Val RMSE | Baseline MAE | Baseline RMSE | Error firmado val |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

| Partición | MAE media ± DE (USD) | RMSE media ± DE (USD) | Error firmado media ± DE (USD) |
| --- | ---: | ---: | ---: |
{chr(10).join(summaries)}

## Curvas de aprendizaje

Últimos 24, 30, 36, 42 y 48 meses anteriores a **cada mismo origen**. Las cinco
ventanas de validación no cambian al variar tamaño. 48 es el máximo común
porque el primer origen solo tiene 48 meses disponibles. Se mezclan longitud
y recencia de historia; con 30/42 meses cambia la cobertura relativa de las
temporadas. No es muestreo aleatorio ni la misma construcción expansiva de CV.

| Meses de ajuste | Train MAE ± DE | Val MAE ± DE | Train RMSE ± DE | Val RMSE ± DE |
| ---: | ---: | ---: | ---: | ---: |
{chr(10).join(learning)}

![Curva MAE]({relative}/learning_curve_mae.png)

![Curva RMSE]({relative}/learning_curve_rmse.png)

De 24 a 48 meses, RMSE de validación cae **{number(reduction)}%**; también cae
el error de entrenamiento. En CV expansiva, comparar orígenes no aísla tamaño:
cambian período validado y nivel de ingresos. Las curvas fijan las ventanas
para complementar esa comparación.

## Diagnóstico y acción

**Diagnóstico: {diagnosis}.**

{explanation}

Error medio de diciembre: entrenamiento **{number(train_december)} USD**,
validación **{number(december_mean)} USD**. Los 10 residuos de diciembre de los
folds incluyen meses repetidos. La brecha train/validación debe interpretarse
junto al crecimiento y cambio temporal; por sí sola no demuestra overfitting.

**Acción concreta:** {action}

**Verificación propuesta:** comparar la variante con el modelo actual en los
mismos cinco orígenes de 24 meses y tamaños de las curvas, reajustando desde
cero y aprendiendo cada transformación solo con su entrenamiento. Exigir menor
RMSE medio sin empeorar MAE y menor magnitud del error de diciembre, registrando
cada fold y su dispersión. Una corrección seleccionada necesitará una validación
futura independiente. **No reutilizar el test 2024–2025 ya reportado en #26.**

## Limitaciones

Serie pequeña educativa, generada previamente por la academia: no valida
rendimiento en ventas reales. Folds solapados, historia compartida y pocas
temporadas; la dispersión sombreada no es un intervalo de confianza. Sin
costes asimétricos, detalle por sede o conversión COP→USD original auditable.
No se cambia el modelo ni se promete precisión de una corrección no probada.

## Reproducción y artefactos

Desde la raíz:

```bash
uv sync --project experiments/sales_forecasting --frozen
uv run --project experiments/sales_forecasting --frozen python scripts/evaluate_sales_model.py
uv run --project experiments/sales_forecasting --frozen pytest tests/pipelines/test_sales_forecasting.py tests/pipelines/test_sales_model_evaluation.py -q
```

El entrypoint regenera este informe, [métricas]({relative}/metrics.json),
[folds]({relative}/cv_scores.csv), [valores de curvas]({relative}/learning_scores.csv),
[predicciones CV]({relative}/cv_predictions.csv),
[predicciones de curvas]({relative}/learning_predictions.csv) y las dos figuras.
Admite `--dataset`, `--output` y `--report`. No sobrescribe los artefactos de #26.
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
