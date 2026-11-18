# Brasaland — Operaciones y soporte con IA

Brasaland es el proyecto transversal de Ingeniería de IA de Carlos Vargas para 4Geeks Academy. El backoffice reúne operaciones de restaurante, consultas a los manuales y procesamiento de solicitudes de propuesta (RFP).

El agente de soporte consulta la base de conocimiento para responder preguntas de los encargados. El chat transmite la respuesta mientras se genera y permite interrumpirla para redirigir la consulta. Las RFPs recorren recepción, generación de borradores y revisión humana. Los controles de seguridad están documentados en los informes [OWASP](docs/security/owasp-top10-audit.md) y [NIST](docs/security/nist-security-practices.md).

## Arranque local

Requisitos: Docker con Compose y una base PostgreSQL de desarrollo. Usa una base aislada para crear cuentas de demo y cargar PDFs sintéticos.

1. Copia `.env.example` a `.env`. Configura `DATABASE_URL` con una PostgreSQL accesible, `SECRET_KEY` y un `PASSWORD_RESET_SECRET_KEY` distinto. Mantén estas credenciales fuera del repositorio.
2. Arranca los servicios:

   ```bash
   docker compose up -d --build
   ```

3. Comprueba que el backend esté disponible:

   ```bash
   curl http://localhost:8000/health
   ```

   Debe responder `{"status":"ok"}`.

4. Abre el [backoffice](http://localhost:3001/login) e inicia sesión con el acceso de prueba indicado abajo. No es necesario registrar otra cuenta. Si `demo@brasaland.co` no existe en una base nueva, créala una sola vez desde [Registro](http://localhost:3001/register).

5. Opcional: para probar Conocimiento y Chat, configura los campos `RAG_*` siguiendo [el diseño RAG](docs/rag/rag-design.md) e indexa los manuales:

   ```bash
   docker compose exec backend python -m data.process.rag
   ```

La [web pública](http://localhost:3000) y la [documentación de la API](http://localhost:8000/docs) se sirven por separado.

## Acceso de prueba

- URL: http://localhost:3001/login
- Usuario: `demo@brasaland.co`
- Contraseña: `DemoBrasaland2026!`

Esta cuenta sirve únicamente para demostraciones locales. Tiene rol de usuario, no privilegios administrativos, y no debe reutilizarse en un entorno compartido o de producción.

El arranque de la API inicializa las tablas de aplicación y los checkpoints de RFP en PostgreSQL. La cuenta de base de datos de desarrollo debe poder crearlos. Para la revisión de RFP, configura los responsables de los departamentos con `RFP_APPROVER_MAP` o la asignación de aprobadores del backend. Consulta el [contrato de aprobación](docs/rfp/rfp_approval_and_final.md).

Si el entorno usa puertos distintos, usa la URL expuesta por esa ejecución. La sesión de desarrollo temporal no comparte necesariamente usuarios con una base o un contenedor nuevo.

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

