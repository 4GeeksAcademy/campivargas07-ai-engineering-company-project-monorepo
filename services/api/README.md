# services/api

Servicio FastAPI para analizar CSVs de incidencias de Brasaland y exportar el ultimo resultado generado.

## Requisitos

- Python 3.11+

## Instalacion

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Ejecucion

```bash
cd services/api
uvicorn app.main:app --reload
```

## Endpoints

### Incidents
- POST /api/incidents/analyze
- GET /api/incidents/results/export

### Authentication
- POST /api/auth/login - User login
- POST /api/auth/register - User registration

### Password Recovery
- POST /api/auth/forgot-password - Request password reset (sends email via Resend)
- POST /api/auth/reset-password - Reset password using token from email
- POST /api/auth/change-password - Change password (requires authentication)

## Environment Variables

See `.env.example` for all required environment variables. Key variables:

- `SECRET_KEY` - JWT secret for access tokens
- `PASSWORD_RESET_SECRET_KEY` - JWT secret for reset tokens (different from SECRET_KEY)
- `RESEND_API_KEY` - API key for Resend email service
- `RESEND_FROM_EMAIL` - Sender email (must be verified in Resend)
- `FRONTEND_URL` - Frontend URL for password reset links

## Password Policy

- Minimum 6 characters
- At least 1 uppercase letter
- At least 1 digit