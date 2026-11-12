# Verificación de la integración final

La rama parte de `main` en `37a60ef` e incorpora la aprobación de RFP (#37), la auditoría OWASP (#40) y las prácticas NIST (#41). Se conservaron los modelos y el repositorio de eventos SSE al resolver los conflictos con aprobación. Las rutas de revisión aplican el control de acceso de los tickets de recepción. Los aprobadores asignados pueden consultar su revisión.

## Resultados

| Comprobación | Evidencia |
|---|---|
| Regresiones API y pipelines | 315 pruebas aprobadas con PostgreSQL 16 desechable, incluidos los tests de integración que requieren `TEST_DATABASE_URL`. |
| Frontend | 107 pruebas del backoffice y 4 de la web. Typecheck y build de las cuatro interfaces completados. |
| Arranque y navegación | Chrome con Next.js y FastAPI locales. Registro sintético, login y navegación mediante menú entre Resumen, Inventario, Incidencias, Proveedores, RFPs, Aprobaciones, Conocimiento y Chat. |
| RAG | Qdrant 1.16.3 real con los 14 fragmentos del corpus. La consulta se hizo en la pantalla de Conocimiento. Embeddings y generación del modelo simulados por un servidor HTTP local. |
| Chat | A través del proxy Next.js se observaron fragmentos antes de completar la generación, interrupción con parcial visible y una nueva respuesta. Proveedor simulado. |
| RFP | PDF sintético → recepción → borrador → aprobación → documento final en PostgreSQL. Modelo simulado y aprobador de demo. Una segunda cuenta recibió 404 al intentar leer la revisión o el documento, o iniciar una aprobación de un ticket ajeno. |
| Compose | Validación estática de la configuración mediante `docker compose config --quiet`. La sesión de navegador usó Next.js y FastAPI locales con PostgreSQL y Qdrant en contenedores aislados. |

## Cómo repetir las comprobaciones

Con las dependencias del proyecto y una base de prueba configuradas:

```bash
uv sync --project services/api --locked --extra dev
uv run --project services/api --no-sync python -m pytest -q services/api/tests tests/pipelines
npm ci
npm run typecheck:uis
npm run test:uis
npm run build:uis
```

`TEST_DATABASE_URL` debe apuntar a una base desechable. Las pruebas pueden crear y eliminar tablas. La ausencia de esa variable omite los casos de integración PostgreSQL.

Con la API local iniciada, una cuenta de demo y un PDF sintético nuevo:

```bash
uv run --project services/api --no-sync python scripts/rfp_e2e.py /ruta/a/rfp-sintetica.pdf
```

El script pide las credenciales en el terminal y deja el ticket listo para revisar. Para cerrar una RFP sintética en una instancia de prueba se puede pasar `--approve` con una cuenta autorizada para sus departamentos. En el backoffice, la recepción enlaza con la aprobación del mismo ticket.

## Pendiente antes de grabar

El recorrido debe repetirse desde el `main` integrado con credenciales válidas del proveedor configurado por Carlos y un Qdrant indexado para ese contrato. Las pruebas locales de esta rama no validan la fidelidad ni la cancelación del proveedor externo. La toma final requiere confirmar la fuente y el texto que devuelve el agente real. Los riesgos operativos abiertos se conservan en los informes OWASP y NIST.
