## Analizador de Incidencias — Brasaland

### Contenido del PR
- **Script CLI** (`scripts/analyze.py`): validación, métricas y exportación CSV
- **Backend FastAPI** (`services/api/`): endpoints POST /api/incidents/analyze y GET /api/incidents/results/export
- **Frontend Next.js** (`uis/backoffice/`): carga de CSV, resumen visual y descarga de resultados
- **Lógica compartida** (`services/api/app/domains/analytics/incidents/analysis.py`): sin duplicación entre script y API
- **Script de inicio** (`scripts/start-all.sh`): levanta API + UI juntos
- **Limpieza**: removidos node_modules, __pycache__ y egg-info del tracking de git

---

### Evidencia 1: Output de consola (script CLI con CSV de 100 filas)

```txt
============================================================
  BRASALAND - INCIDENT REPORT ANALYSIS
  Source file: incidents-brasaland.csv
============================================================

TOTAL RECORDS IN FILE .......... 100
  |- Valid records ................ 96
  '- Invalid / incomplete .......... 4

INVALID RECORDS BREAKDOWN
  |- Missing location_id......... 1
  |- Invalid or missing category. 1
  |- Empty description........... 1
  '- Closed case, no score....... 1

BREAKDOWN BY CATEGORY (valid records)
  |- CUSTOMER_COMPLAINT........... 29  (30.2%)
  |- EQUIPMENT.................... 17  (17.7%)
  |- SUPPLY....................... 22  (22.9%)
  |- FOOD_QUALITY................. 19  (19.8%)
  '- STAFF........................  9  ( 9.4%)

BREAKDOWN BY STATUS (valid records)
  |- OPEN............................... 32  (33.3%)
  |- CLOSED............................. 50  (52.1%)
  '- DISCARDED.......................... 14  (14.6%)

SATISFACTION INDEX (closed cases)
  Scored cases: 50 of 50
  Average score: 3.46 / 5.00
  |- Score 1 (Very dissatisfied) ..... 4
  |- Score 2 (Dissatisfied) .......... 6
  |- Score 3 (Neutral) ............... 12
  |- Score 4 (Satisfied) ............. 19
  '- Score 5 (Very satisfied) ........ 9
```

---

### Evidencia 2: Interfaz Web — Vista superior

![Web Interface — Top View](https://raw.githubusercontent.com/4GeeksAcademy/campivargas07-ai-engineering-company-project-monorepo/feature/incident-analyzer/docs/screenshot-web-top.png)

### Evidencia 3: Interfaz Web — Análisis completo

![Web Interface — Full Analysis](https://raw.githubusercontent.com/4GeeksAcademy/campivargas07-ai-engineering-company-project-monorepo/feature/incident-analyzer/docs/screenshot-web-analysis.png)

> **Nota**: Las capturas muestran la interfaz web en `/incidents` procesando el CSV de 100 registros de Brasaland con KPIs, tablas de categorías, estados y distribución de satisfacción.
