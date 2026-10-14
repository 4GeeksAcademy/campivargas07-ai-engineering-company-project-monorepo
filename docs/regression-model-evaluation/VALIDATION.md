# Validación — Evaluación de regresión (2026-10-12)

Base verificada: PR #26 abierta, rama `feature/brasaland-sales-regression`, head
`0b0b705a799a049c7381a88636264f0189b8b76d`. Trabajo en checkout aislado en
`feature/regression-model-eval`, preservando el workspace original del usuario.

| Check | Resultado |
| --- | --- |
| Ambos archivos pytest en el entorno uv existente | **30 passed, 0 skipped**: 18 previos + 12 nuevos |
| Ruff de módulos nuevos, entrypoint y tests | PASS |
| Mypy de paquete completo y entrypoint nuevo | PASS |
| Build Python 3.12 | wheel y sdist OK |
| `npm run typecheck`, raíz | PASS |
| Dos ejecuciones completas del evaluador | Siete artefactos idénticos byte por byte |
| Informe regenerado en otra ubicación | Igual salvo enlaces relativos adaptados al destino |
| Curvas MAE y RMSE | Inspeccionadas; ejes USD, tamaños, entrenamiento/validación y DE descriptiva |

Las pruebas nuevas verifican cinco folds ordenados de 24 meses anteriores a
2024, mismos orígenes y validaciones para cinco tamaños, métricas y DE muestral,
30 instancias nuevas con parámetros originales, y rechazo de historia incompleta.
Por cada origen, alterar ingresos posteriores conserva coeficientes ajustados,
importancias, métricas de train, predicciones y baseline. Alterar todos los
objetivos/comensales/ticket del test final conserva íntegro el resultado de CV y
curvas, incluido el hash efectivo del entrenamiento. Otra prueba genera informe
y artefactos y comprueba preservación del experimento previo.

Los cuatro archivos anteriores de #26 (`metrics.json`, `model.joblib`,
`forecast.png`, `test_predictions.csv`) se compararon byte por byte contra
`git show 0b0b705:<ruta>`: **intactos**. El CSV oficial, su contexto, el módulo
original y sus pruebas tampoco se modifican. No hay cambios en API, workers,
UI, infraestructura ni dependencias; las pruebas pertinentes son las dos suites
del experimento y el typecheck raíz. No se atribuye a esta entrega una nueva
ejecución de las 211 regresiones backend previamente reportadas por #26.

SHA-256 de los nuevos artefactos repetidos:

| Archivo | SHA-256 |
| --- | --- |
| `metrics.json` | `271e3170c5528c366ae751dc95565a029f5ca6c8364c19a7e6027191cde441ed` |
| `cv_scores.csv` | `5d878db9ed8bf9bb2c93556219ab3050a813063836b93bda6432498485c55a3a` |
| `cv_predictions.csv` | `87e24800e6143f6757b2c1e28fda714d0e4098f826e515eb76cdf8ad0efaa07f` |
| `learning_scores.csv` | `05fa7a321c02906679368ab6c01dc19ebf647874acee12723e3f59722f82fd42` |
| `learning_predictions.csv` | `ec70ab25d1b912ecab21007b7bebdde1fd3383c44c66056ce6356e4bd4b94599` |
| `learning_curve_mae.png` | `8742ad4457848f8018a2567b89951cac32610385428eac58c83bbf38bf6ffe1e` |
| `learning_curve_rmse.png` | `75d181b17a392f25bb2a3a6ac0ed5d8ad801ffa7a52218578d4469ce12acf3af` |

Los comandos completos de reproducción y checks están en [README.md](README.md).
