# Brasaland — Operaciones y soporte con IA

Brasaland es el proyecto transversal de Ingeniería de IA de Carlos Vargas para 4Geeks Academy. El backoffice reúne operaciones de restaurante, consultas a los manuales y procesamiento de solicitudes de propuesta (RFP).

El agente de soporte consulta la base de conocimiento para responder preguntas de los encargados. El chat transmite la respuesta mientras se genera y permite interrumpirla para redirigir la consulta. Las RFPs recorren recepción, generación de borradores y revisión humana. Los controles de seguridad están documentados en los informes [OWASP](docs/security/owasp-top10-audit.md) y [NIST](docs/security/nist-security-practices.md).

## Arranque local

Requisitos: Docker con Compose y una base PostgreSQL de desarrollo. Usa una base aislada para crear cuentas de demo y cargar PDFs sintéticos.

1. Copia `.env.example` a `.env` si todavía no existe. Configura `DATABASE_URL`, un `SECRET_KEY` y un `PASSWORD_RESET_SECRET_KEY` distinto. Mantén las credenciales en el entorno local.
2. Para usar el agente, configura los campos `RAG_*` en ese archivo siguiendo [el diseño RAG](docs/rag/rag-design.md). El backend usa Qdrant en el contenedor correspondiente.
3. Arranca los servicios e indexa los manuales una vez que el backend esté disponible.

   ```bash
   docker compose up -d --build
   docker compose exec backend python -m data.process.rag
   ```

4. Abre [el backoffice](http://localhost:3001), registra una cuenta de demo e inicia sesión. La [web pública](http://localhost:3000) y la [documentación de la API](http://localhost:8000/docs) se sirven por separado.

El arranque de la API inicializa las tablas de aplicación y los checkpoints de RFP en PostgreSQL. La cuenta de base de datos de desarrollo debe poder crearlos. Para la revisión de RFP, configura los responsables de los departamentos con `RFP_APPROVER_MAP` o la asignación de aprobadores del backend. Consulta el [contrato de aprobación](docs/rfp/rfp_approval_and_final.md).

## Recorrido del backoffice

| Menú | Función |
|---|---|
| Resumen | Indicadores de muestra por local y alertas de inventario |
| Inventario | Catálogo, registro de entradas y salidas e historial |
| Incidencias | Gestión y análisis de incidencias |
| Proveedores | Directorio y operaciones de compras |
| Conocimiento | Preguntas sobre manuales de Brasaland |
| Chat | Conversación con el agente de soporte en tiempo real |
| RFPs | Recepción de PDFs, notificaciones SSE, borradores y evaluaciones |
| Aprobaciones RFP | Revisión por departamento y documento final |
| Cuenta | Perfil y gestión de contraseña |

Desde una RFP con borradores, **Abrir aprobación de este ticket** lleva a su revisión con el identificador ya seleccionado.

## Capstone

- [Guion, tomas y checklist de entrega](docs/capstone/guion-y-grabacion.md)
- Vídeo del proyecto: enlace pendiente de grabación y publicación.
- [Evidencia técnica de integración](docs/capstone/verificacion.md)

Usa `docker compose down` para detener el entorno de desarrollo conservando sus datos.
