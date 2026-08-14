# 🔐 Guía de Implementación: Recuperación y Cambio de Contraseña

## Brasaland Digital - Manual de Implementación Paso a Paso

---

## 📋 Índice

1. [Requisitos Previos](#1-requisitos-previos)
2. [Configuración del Backend (FastAPI)](#2-configuración-del-backend-fastapi)
3. [Configuración del Frontend (Next.js)](#3-configuración-del-frontend-nextjs)
4. [Integración con Resend Email](#4-integración-con-resend-email)
5. [Pruebas y Validación](#5-pruebas-y-validación)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Requisitos Previos

### Cuentas Necesarias
- **Resend**: Cuenta gratuita en [resend.com](https://resend.com)
- **GitHub**: Acceso al monorepo

### Herramientas
- Node.js 18+
- Python 3.11+
- Terminal/VS Code

### Estructura del Proyecto
```
brasaland-monorepo/
├── services/api/           ← Backend FastAPI
├── uis/backoffice/         ← Frontend Next.js
├── packages/shared/        ← Tipos compartidos
└── data/                   ← Base de datos
```

---

## 2. Configuración del Backend (FastAPI)

### Paso 2.1: Instalar Dependencias

```bash
cd services/api

# Agregar dependencias al pyproject.toml
# Editar pyproject.toml y agregar en [project].dependencies:
```

**pyproject.toml:**
```toml
[project]
dependencies = [
  "bcrypt>=4.0,<5.0",
  "fastapi>=0.116,<1.0",
  "httpx>=0.27,<1.0",
  "python-dotenv>=1.0,<2.0",
  "python-jose[cryptography]>=3.3,<4.0",
  "python-multipart>=0.0.20,<1.0",
  "tinydb>=4.8,<5.0",
  "uvicorn>=0.35,<1.0",
]
```

```bash
# Instalar dependencias
pip install -e .
```

### Paso 2.2: Configurar Variables de Entorno

**Crear archivo `services/api/.env`:**
```env
# Brasaland API - Environment Variables

# JWT Secret Key for access tokens (genera con: python3 -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=tu-clave-secreta-aqui-cambiar-en-produccion

# Access token expiration time in minutes
ACCESS_TOKEN_EXPIRE_MINUTES=60

# JWT Secret Key for password reset tokens (DIFERENTE a SECRET_KEY)
PASSWORD_RESET_SECRET_KEY=otra-clave-secreta-diferente-aqui

# Password reset token expiration time in minutes
PASSWORD_RESET_EXPIRE_MINUTES=30

# Resend API Key (obtener de https://resend.com/api-keys)
RESEND_API_KEY=re_tu_api_key_de_resend

# Resend sender email (DEBE estar verificado en Resend)
RESEND_FROM_EMAIL=noreply@tu-dominio.com

# Frontend URL for password reset links
FRONTEND_URL=http://localhost:3000

# TinyDB database path
SUPPLIERS_DB_PATH=data/suppliers.json
```

### Paso 2.3: Crear Servicio de Autenticación

**Crear archivo `services/api/app/domains/auth/service.py`:**

```python
"""
service.py — Brasaland · JWT token creation and verification
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()  # Ensure .env is loaded before reading env vars

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

# --- JWT configuration ---
SECRET_KEY = os.environ.get(
    "SECRET_KEY", "brasa-land-dev-secret-key-change-in-production"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)

# --- Password Reset configuration ---
PASSWORD_RESET_SECRET_KEY = os.environ.get(
    "PASSWORD_RESET_SECRET_KEY", "brasa-reset-dev-secret-change-in-production"
)
PASSWORD_RESET_EXPIRE_MINUTES = int(
    os.environ.get("PASSWORD_RESET_EXPIRE_MINUTES", "30")
)


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(
    data: dict, expires_delta: timedelta | None = None
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns the payload or None if invalid."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def validate_password_policy(password: str) -> None:
    """Validate password meets security policy. Raises HTTP 422 if not."""
    errors: list[str] = []
    if len(password) < 6:
        errors.append("must be at least 6 characters")
    if not any(c.isupper() for c in password):
        errors.append("must contain at least one uppercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("must contain at least one digit")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password {'; '.join(errors)}",
        )


def create_reset_token(user_id: str) -> str:
    """Create a signed JWT password reset token with unique jti."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "purpose": "password_reset",
        "iat": int(now.timestamp()),
        "exp": expire,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, PASSWORD_RESET_SECRET_KEY, algorithm=ALGORITHM)


def decode_reset_token(token: str) -> dict | None:
    """Decode and validate a password reset token. Returns payload or None."""
    try:
        payload = jwt.decode(
            token, PASSWORD_RESET_SECRET_KEY, algorithms=[ALGORITHM]
        )
        if payload.get("purpose") != "password_reset":
            return None
        return payload
    except JWTError:
        return None
```

### Paso 2.4: Crear Esquemas Pydantic

**Crear archivo `services/api/app/domains/auth/schemas.py`:**

```python
"""
schemas.py — Brasaland · Auth Pydantic models
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Schema for login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


class ChangePasswordRequest(BaseModel):
    """Schema for change password request."""
    current_password: str
    new_password: str = Field(..., min_length=6)


class MessageResponse(BaseModel):
    """Schema for generic message response."""
    detail: str


class UserOut(BaseModel):
    """Schema for user output."""
    id: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None


class ProfileOut(BaseModel):
    """Schema for profile output."""
    id: str
    user_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class AuthMeResponse(BaseModel):
    """Schema for /auth/me response."""
    user: UserOut
    profile: Optional[ProfileOut] = None
```

### Paso 2.5: Crear Servicio de Email

**Crear archivo `services/api/app/domains/auth/email_service.py`:**

```python
"""
email_service.py - Brasaland - Email sending via Resend API
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()  # Ensure .env is loaded before reading env vars

import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "noreply@example.com")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

RESET_EMAIL_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Restablece tu contraseña</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f7;font-family:Arial,sans-serif;">
  <div style="max-width:480px;margin:40px auto;background:#ffffff;border-radius:8px;padding:32px;">
    <h1 style="color:#333;font-size:20px;margin-bottom:8px;">Brasaland</h1>
    <p style="color:#555;font-size:14px;line-height:1.6;">Recibimos una solicitud para restablecer tu contraseña.</p>
    <p style="color:#555;font-size:14px;line-height:1.6;">Haz clic en el botón de abajo para crear una nueva contraseña. Este enlace expira en 30 minutos.</p>
    <div style="text-align:center;margin:24px 0;">
      <a href="{reset_link}" style="display:inline-block;padding:12px 32px;background:linear-gradient(135deg,#2dd6a4,#4a8cff);color:#03121f;font-weight:700;font-size:14px;border-radius:999px;text-decoration:none;">Restablecer contraseña</a>
    </div>
    <p style="color:#555;font-size:14px;line-height:1.6;">Si no solicitaste este cambio, puedes ignorar este mensaje de forma segura.</p>
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
    <p style="color:#999;font-size:12px;">Este enlace expirará en 30 minutos por motivos de seguridad.</p>
  </div>
</body>
</html>"""

RESET_EMAIL_TEXT = """Restablece tu contraseña - Brasaland

Recibimos una solicitud para restablecer tu contraseña.
Copia y pega este enlace en tu navegador: {reset_link}

Este enlace expira en 30 minutos.

Si no solicitaste este cambio, puedes ignorar este mensaje de forma segura."""


async def send_reset_email(to_email: str, token: str) -> None:
    """Send password reset email via Resend API."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured - email not sent to %s", to_email)
        return

    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": "Restablece tu contraseña - Brasaland",
        "html": RESET_EMAIL_HTML.format(reset_link=reset_link),
        "text": RESET_EMAIL_TEXT.format(reset_link=reset_link),
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                timeout=10.0,
            )
            if response.status_code != 200:
                logger.warning(
                    "Resend API returned status %s for %s",
                    response.status_code,
                    to_email,
                )
    except Exception as exc:
        logger.warning("Failed to send reset email to %s: %s", to_email, type(exc).__name__)
```

### Paso 2.6: Crear Router de Autenticación

**Crear archivo `services/api/app/domains/auth/router.py`:**

```python
"""
router.py — Brasaland · Authentication endpoints

POST   /auth/login            Authenticate with email/password, return JWT
GET    /auth/me               Get current authenticated user + profile
POST   /auth/forgot-password  Request password reset email
POST   /auth/reset-password   Reset password with token
POST   /auth/change-password  Change password (authenticated)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from tinydb import Query

from app.database import password_resets_table, profiles_table, users_table

from .dependencies import get_current_user
from .email_service import send_reset_email
from .schemas import (
    AuthMeResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ProfileOut,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from .service import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
    hash_password,
    validate_password_policy,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_Q = Query()


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest) -> TokenResponse:
    """Authenticate a user by email and password. Returns a JWT access token."""
    user = users_table.get(_Q.email == data.email)

    if user is None or not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    token = create_access_token(
        data={"sub": str(user.doc_id), "role": user["role"]}
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=AuthMeResponse)
def get_me(current_user: dict = Depends(get_current_user)) -> AuthMeResponse:
    """Return the authenticated user's credentials and linked profile."""
    user_out = UserOut(
        id=str(current_user.doc_id),
        email=current_user["email"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
    )

    profile_doc = profiles_table.get(_Q.user_id == str(current_user.doc_id))
    profile_out = None
    if profile_doc:
        profile_out = ProfileOut(
            id=str(profile_doc.doc_id),
            user_id=profile_doc["user_id"],
            name=profile_doc.get("name"),
            phone=profile_doc.get("phone"),
            address=profile_doc.get("address"),
        )

    return AuthMeResponse(user=user_out, profile=profile_out)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
) -> MessageResponse:
    """Request a password reset email. Always returns the same response to prevent enumeration."""
    normalized_email = data.email.strip().lower()
    user = users_table.get(_Q.email == normalized_email)

    if user is not None:
        user_id = str(user.doc_id)

        # Invalidate any previous reset tokens for this user
        previous_tokens = password_resets_table.search(
            (_Q.user_id == user_id) & (_Q.purpose == "password_reset") & (_Q.used == False)
        )
        for token_doc in previous_tokens:
            password_resets_table.update({"used": True}, doc_ids=[token_doc.doc_id])

        # Generate new reset token
        reset_token = create_reset_token(user_id)
        payload = decode_reset_token(reset_token)
        jti = payload.get("jti", "") if payload else ""
        expires_at = datetime.fromtimestamp(
            payload.get("exp", 0), tz=timezone.utc
        ).isoformat() if payload else ""

        # Store token metadata in TinyDB
        password_resets_table.insert({
            "user_id": user_id,
            "jti": jti,
            "purpose": "password_reset",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at,
            "used": False,
        })

        # Send email in background
        background_tasks.add_task(send_reset_email, normalized_email, reset_token)

    # Always return the same message regardless of email existence
    return MessageResponse(
        detail="Si el email existe, recibirás un enlace de recuperación."
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(data: ResetPasswordRequest) -> MessageResponse:
    """Reset password using a valid token."""
    # Decode and validate token
    payload = decode_reset_token(data.token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    # Verify purpose
    if payload.get("purpose") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    user_id = payload.get("sub")
    jti = payload.get("jti")

    if not user_id or not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    # Find token record in TinyDB
    token_doc = password_resets_table.get(
        (_Q.jti == jti) & (_Q.user_id == user_id) & (_Q.purpose == "password_reset")
    )

    if token_doc is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o ya utilizado",
        )

    if token_doc.get("used", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o ya utilizado",
        )

    # Validate new password policy
    validate_password_policy(data.new_password)

    # Update password
    user = users_table.get(doc_id=int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    users_table.update(
        {"hashed_password": hash_password(data.new_password)},
        doc_ids=[int(user_id)],
    )

    # Mark token as used
    password_resets_table.update({"used": True}, doc_ids=[token_doc.doc_id])

    return MessageResponse(detail="Contraseña actualizada correctamente.")


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Change password for authenticated user."""
    # Verify current password
    if not verify_password(data.current_password, current_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta",
        )

    # Check that new password is different
    if verify_password(data.new_password, current_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña no puede ser igual a la actual",
        )

    # Validate new password policy
    validate_password_policy(data.new_password)

    # Update password
    users_table.update(
        {"hashed_password": hash_password(data.new_password)},
        doc_ids=[current_user.doc_id],
    )

    return MessageResponse(detail="Contraseña cambiada correctamente.")
```

### Paso 2.7: Crear Archivos Faltantes

**Crear `services/api/app/domains/procurement/suppliers/__init__.py`:**
```python
"""
suppliers — Brasaland · Supplier directory module
"""
```

**Crear `services/api/app/domains/procurement/suppliers/schemas.py`:**
```python
"""
schemas.py — Brasaland · Supplier Pydantic models
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    """Schema for creating a new supplier."""
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    nit: Optional[str] = None
    notes: Optional[str] = None


class SupplierResponse(BaseModel):
    """Schema for supplier detail response."""
    id: str
    name: str
    category: str
    status: str = "active"
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    nit: Optional[str] = None
    notes: Optional[str] = None
    tariff: Optional[float] = None
    currency: str = "COP"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SupplierListResponse(BaseModel):
    """Schema for supplier list response."""
    suppliers: list[SupplierResponse]
    total: int


class SupplierRateUpdate(BaseModel):
    """Schema for updating supplier tariff."""
    tariff: float = Field(..., ge=0)
    currency: str = "COP"


class SupplierStatusUpdate(BaseModel):
    """Schema for updating supplier status."""
    status: str = Field(..., pattern="^(active|suspended)$")
```

**Crear `services/api/app/domains/procurement/suppliers/service.py`:**
```python
"""
service.py — Brasaland · Supplier CRUD operations
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.database import suppliers_table

from .schemas import SupplierCreate, SupplierRateUpdate, SupplierResponse, SupplierStatusUpdate


def _doc_to_response(doc: dict) -> SupplierResponse:
    """Convert a TinyDB document to a SupplierResponse."""
    return SupplierResponse(
        id=doc.get("id", ""),
        name=doc.get("name", ""),
        category=doc.get("category", ""),
        status=doc.get("status", "active"),
        contact_email=doc.get("contact_email"),
        contact_phone=doc.get("contact_phone"),
        address=doc.get("address"),
        nit=doc.get("nit"),
        notes=doc.get("notes"),
        tariff=doc.get("tariff"),
        currency=doc.get("currency", "COP"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


def create_supplier(data: SupplierCreate) -> SupplierResponse:
    """Create a new supplier and return the response."""
    supplier_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": supplier_id,
        "name": data.name,
        "category": data.category,
        "status": "active",
        "contact_email": data.contact_email,
        "contact_phone": data.contact_phone,
        "address": data.address,
        "nit": data.nit,
        "notes": data.notes,
        "created_at": now,
        "updated_at": now,
    }
    suppliers_table.insert(doc)
    return _doc_to_response(doc)


def get_all_suppliers(
    country: Optional[str] = None,
    category: Optional[str] = None,
) -> list[SupplierResponse]:
    """Return all suppliers, optionally filtered by country and category."""
    results = []
    for doc in suppliers_table.all():
        if country and doc.get("country") != country:
            continue
        if category and doc.get("category") != category:
            continue
        results.append(_doc_to_response(doc))
    return results


def get_supplier_by_id(supplier_id: str) -> Optional[SupplierResponse]:
    """Return a single supplier by ID, or None if not found."""
    for doc in suppliers_table.all():
        if doc.get("id") == supplier_id:
            return _doc_to_response(doc)
    return None


def update_rate(supplier_id: str, data: SupplierRateUpdate) -> Optional[SupplierResponse]:
    """Update a supplier's tariff. Returns the updated supplier or None."""
    for doc in suppliers_table.all():
        if doc.get("id") == supplier_id:
            doc["tariff"] = data.tariff
            doc["currency"] = data.currency
            doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            suppliers_table.write_back([doc])
            return _doc_to_response(doc)
    return None


def update_status(supplier_id: str, data: SupplierStatusUpdate) -> Optional[SupplierResponse]:
    """Update a supplier's status (active/suspended). Returns the updated supplier or None."""
    for doc in suppliers_table.all():
        if doc.get("id") == supplier_id:
            doc["status"] = data.status
            doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            suppliers_table.write_back([doc])
            return _doc_to_response(doc)
    return None


def delete_supplier(supplier_id: str) -> bool:
    """Delete a supplier by ID. Returns True if deleted, False if not found."""
    for doc in suppliers_table.all():
        if doc.get("id") == supplier_id:
            suppliers_table.remove(doc)
            return True
    return False
```

---

## 3. Configuración del Frontend (Next.js)

### Paso 3.1: Agregar Rutas Públicas al Middleware

**Editar `uis/backoffice/src/middleware.ts`:**

```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const publicRoutes = [
  '/login',
  '/register',
  '/forgot-password',  // ← AGREGAR ESTA LÍNEA
  '/reset-password',   // ← AGREGAR ESTA LÍNEA
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Allow public routes
  if (publicRoutes.some(route => pathname.startsWith(route))) {
    return NextResponse.next();
  }

  // Check for auth token
  const token = request.cookies.get('auth-token')?.value;
  
  if (!token) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};
```

### Paso 3.2: Crear Página de Olvidé Mi Contraseña

**Crear archivo `uis/backoffice/src/app/forgot-password/page.tsx`:**

```tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { forgotPassword } from '@/lib/auth/api';

const MailIcon = () => (
  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-6 h-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
);

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '2rem 1rem',
  } as React.CSSProperties,
  card: {
    width: '100%',
    maxWidth: '400px',
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '1rem',
    padding: '2rem 1.75rem',
  } as React.CSSProperties,
  logo: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.75rem',
    marginBottom: '1.5rem',
  } as React.CSSProperties,
  logoIcon: {
    width: '42px',
    height: '42px',
    borderRadius: '12px',
    background: 'linear-gradient(135deg, #ff8c42, #ff6b35)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  } as React.CSSProperties,
  title: {
    fontFamily: 'var(--font-jakarta), sans-serif',
    fontSize: '1.75rem',
    fontWeight: 800,
    marginBottom: '0.35rem',
    textAlign: 'center' as const,
  } as React.CSSProperties,
  subtitle: {
    color: 'var(--muted)',
    fontSize: '0.92rem',
    textAlign: 'center' as const,
    marginBottom: '1.75rem',
  } as React.CSSProperties,
  fieldGroup: {
    display: 'grid',
    gap: '0.9rem',
    marginBottom: '1.25rem',
  } as React.CSSProperties,
  label: {
    display: 'block',
    color: 'var(--muted)',
    fontSize: '0.82rem',
    fontWeight: 600,
    marginBottom: '0.35rem',
  } as React.CSSProperties,
  inputWrapper: {
    position: 'relative' as const,
  } as React.CSSProperties,
  inputIcon: {
    position: 'absolute' as const,
    left: '0.75rem',
    top: '50%',
    transform: 'translateY(-50%)',
    color: 'var(--muted)',
    opacity: 0.6,
    fontSize: '0.9rem',
  } as React.CSSProperties,
  input: {
    width: '100%',
    padding: '0.65rem 0.75rem 0.65rem 2.25rem',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid var(--border)',
    borderRadius: '0.65rem',
    color: 'var(--fg)',
    fontSize: '0.92rem',
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
  } as React.CSSProperties,
  inputError: {
    borderColor: 'var(--danger)',
    boxShadow: '0 0 0 2px rgba(255,125,125,0.2)',
  } as React.CSSProperties,
  submitButton: {
    width: '100%',
    padding: '0.8rem',
    border: '0',
    borderRadius: '999px',
    background: 'linear-gradient(135deg, #2dd6a4, #4a8cff)',
    color: '#03121f',
    fontFamily: 'inherit',
    fontWeight: 700,
    fontSize: '0.95rem',
    cursor: 'pointer',
    transition: 'transform 0.2s ease, opacity 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
  } as React.CSSProperties,
  backButton: {
    display: 'block',
    width: '100%',
    textAlign: 'center' as const,
    marginTop: '1rem',
    color: 'var(--muted)',
    textDecoration: 'none',
    fontSize: '0.85rem',
  } as React.CSSProperties,
  successBox: {
    textAlign: 'center' as const,
    padding: '2rem 1rem',
  } as React.CSSProperties,
  successIcon: {
    width: '64px',
    height: '64px',
    borderRadius: '50%',
    background: 'rgba(45, 214, 164, 0.15)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 1.5rem',
  } as React.CSSProperties,
  errorMessage: {
    background: 'rgba(255, 125, 125, 0.1)',
    border: '1px solid rgba(255, 125, 125, 0.3)',
    borderRadius: '0.5rem',
    padding: '0.75rem',
    marginBottom: '1rem',
    color: 'var(--danger)',
    fontSize: '0.85rem',
    textAlign: 'center' as const,
  } as React.CSSProperties,
};

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await forgotPassword(email);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Error al enviar el enlace. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <div style={styles.logo}>
            <div style={styles.logoIcon}>🔥</div>
            <span style={styles.title}>Brasaland</span>
          </div>
          <div style={styles.successBox}>
            <div style={styles.successIcon}>
              <CheckIcon />
            </div>
            <h2 style={{...styles.title, fontSize: '1.25rem', marginBottom: '0.75rem'}}>
              Revisa tu correo
            </h2>
            <p style={{...styles.subtitle, marginBottom: '1.5rem'}}>
              Si existe una cuenta con <strong>{email}</strong>, recibirás un enlace para restablecer tu contraseña.
            </p>
            <Link href="/login" style={styles.backButton}>
              ← Volver al login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <div style={styles.logoIcon}>🔥</div>
          <span style={styles.title}>Brasaland</span>
        </div>
        
        <h1 style={styles.title}>¿Olvidaste tu contraseña?</h1>
        <p style={styles.subtitle}>
          Ingresa tu correo electrónico y te enviaremos un enlace para restablecerla.
        </p>

        {error && <div style={styles.errorMessage}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={styles.fieldGroup}>
            <div>
              <label style={styles.label}>Correo electrónico</label>
              <div style={styles.inputWrapper}>
                <span style={styles.inputIcon}><MailIcon /></span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@brasaland.com"
                  required
                  style={styles.input}
                  autoFocus
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              ...styles.submitButton,
              opacity: loading ? 0.7 : 1,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Enviando...' : 'Enviar enlace de recuperación'}
          </button>
        </form>

        <Link href="/login" style={styles.backButton}>
          ← Volver al login
        </Link>
      </div>
    </div>
  );
}
```

### Paso 3.3: Crear Página de Restablecer Contraseña

**Crear archivo `uis/backoffice/src/app/reset-password/page.tsx`:**

```tsx
'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { resetPassword } from '@/lib/auth/api';

const LockIcon = () => (
  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-6 h-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
);

const XIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '2rem 1rem',
  } as React.CSSProperties,
  card: {
    width: '100%',
    maxWidth: '400px',
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '1rem',
    padding: '2rem 1.75rem',
  } as React.CSSProperties,
  logo: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.75rem',
    marginBottom: '1.5rem',
  } as React.CSSProperties,
  logoIcon: {
    width: '42px',
    height: '42px',
    borderRadius: '12px',
    background: 'linear-gradient(135deg, #ff8c42, #ff6b35)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  } as React.CSSProperties,
  title: {
    fontFamily: 'var(--font-jakarta), sans-serif',
    fontSize: '1.75rem',
    fontWeight: 800,
    marginBottom: '0.35rem',
    textAlign: 'center' as const,
  } as React.CSSProperties,
  subtitle: {
    color: 'var(--muted)',
    fontSize: '0.92rem',
    textAlign: 'center' as const,
    marginBottom: '1.75rem',
  } as React.CSSProperties,
  fieldGroup: {
    display: 'grid',
    gap: '0.9rem',
    marginBottom: '1.25rem',
  } as React.CSSProperties,
  label: {
    display: 'block',
    color: 'var(--muted)',
    fontSize: '0.82rem',
    fontWeight: 600,
    marginBottom: '0.35rem',
  } as React.CSSProperties,
  inputWrapper: {
    position: 'relative' as const,
  } as React.CSSProperties,
  inputIcon: {
    position: 'absolute' as const,
    left: '0.75rem',
    top: '50%',
    transform: 'translateY(-50%)',
    color: 'var(--muted)',
    opacity: 0.6,
    fontSize: '0.9rem',
  } as React.CSSProperties,
  input: {
    width: '100%',
    padding: '0.65rem 0.75rem 0.65rem 2.25rem',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid var(--border)',
    borderRadius: '0.65rem',
    color: 'var(--fg)',
    fontSize: '0.92rem',
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
  } as React.CSSProperties,
  inputError: {
    borderColor: 'var(--danger)',
    boxShadow: '0 0 0 2px rgba(255,125,125,0.2)',
  } as React.CSSProperties,
  submitButton: {
    width: '100%',
    padding: '0.8rem',
    border: '0',
    borderRadius: '999px',
    background: 'linear-gradient(135deg, #2dd6a4, #4a8cff)',
    color: '#03121f',
    fontFamily: 'inherit',
    fontWeight: 700,
    fontSize: '0.95rem',
    cursor: 'pointer',
    transition: 'transform 0.2s ease, opacity 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
  } as React.CSSProperties,
  backButton: {
    display: 'block',
    width: '100%',
    textAlign: 'center' as const,
    marginTop: '1rem',
    color: 'var(--muted)',
    textDecoration: 'none',
    fontSize: '0.85rem',
  } as React.CSSProperties,
  successBox: {
    textAlign: 'center' as const,
    padding: '2rem 1rem',
  } as React.CSSProperties,
  successIcon: {
    width: '64px',
    height: '64px',
    borderRadius: '50%',
    background: 'rgba(45, 214, 164, 0.15)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 1.5rem',
  } as React.CSSProperties,
  errorMessage: {
    background: 'rgba(255, 125, 125, 0.1)',
    border: '1px solid rgba(255, 125, 125, 0.3)',
    borderRadius: '0.5rem',
    padding: '0.75rem',
    marginBottom: '1rem',
    color: 'var(--danger)',
    fontSize: '0.85rem',
    textAlign: 'center' as const,
  } as React.CSSProperties,
  strengthMeter: {
    display: 'flex',
    gap: '0.25rem',
    marginTop: '0.5rem',
  } as React.CSSProperties,
  strengthBar: {
    flex: 1,
    height: '4px',
    borderRadius: '2px',
    background: 'var(--border)',
    transition: 'background 0.2s ease',
  } as React.CSSProperties,
  strengthText: {
    fontSize: '0.75rem',
    marginTop: '0.25rem',
    color: 'var(--muted)',
  } as React.CSSProperties,
  requirement: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    fontSize: '0.8rem',
    marginBottom: '0.25rem',
  } as React.CSSProperties,
  requirementMet: {
    color: '#2dd6a4',
  } as React.CSSProperties,
  requirementNotMet: {
    color: 'var(--muted)',
  } as React.CSSProperties,
};

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const getPasswordStrength = (pwd: string) => {
    let strength = 0;
    if (pwd.length >= 6) strength++;
    if (pwd.length >= 8) strength++;
    if (/[A-Z]/.test(pwd)) strength++;
    if (/[0-9]/.test(pwd)) strength++;
    return strength;
  };

  const strength = getPasswordStrength(password);
  const strengthColors = ['#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#2dd6a4'];
  const strengthLabels = ['Muy débil', 'Débil', 'Media', 'Fuerte', 'Muy fuerte'];

  const passwordRequirements = [
    { label: 'Mínimo 6 caracteres', met: password.length >= 6 },
    { label: 'Una letra mayúscula', met: /[A-Z]/.test(password) },
    { label: 'Un número', met: /[0-9]/.test(password) },
  ];

  useEffect(() => {
    if (!token) {
      setError('Token no válido. Solicita un nuevo enlace de recuperación.');
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Las contraseñas no coinciden');
      return;
    }

    if (password.length < 6) {
      setError('La contraseña debe tener al menos 6 caracteres');
      return;
    }

    if (!/[A-Z]/.test(password)) {
      setError('La contraseña debe contener al menos una mayúscula');
      return;
    }

    if (!/[0-9]/.test(password)) {
      setError('La contraseña debe contener al menos un número');
      return;
    }

    if (!token) {
      setError('Token no válido');
      return;
    }

    setLoading(true);

    try {
      await resetPassword(token, password);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Error al restablecer la contraseña. El enlace puede haber expirado.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <div style={styles.logo}>
            <div style={styles.logoIcon}>🔥</div>
            <span style={styles.title}>Brasaland</span>
          </div>
          <div style={styles.successBox}>
            <div style={styles.successIcon}>
              <CheckIcon />
            </div>
            <h2 style={{...styles.title, fontSize: '1.25rem', marginBottom: '0.75rem'}}>
              ¡Contraseña actualizada!
            </h2>
            <p style={{...styles.subtitle, marginBottom: '1.5rem'}}>
              Tu contraseña ha sido cambiada exitosamente. Ya puedes iniciar sesión.
            </p>
            <Link href="/login" style={{...styles.submitButton, textDecoration: 'none'}}>
              Ir al login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <div style={styles.logoIcon}>🔥</div>
          <span style={styles.title}>Brasaland</span>
        </div>
        
        <h1 style={styles.title}>Nueva contraseña</h1>
        <p style={styles.subtitle}>
          Ingresa tu nueva contraseña a continuación.
        </p>

        {error && <div style={styles.errorMessage}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={styles.fieldGroup}>
            <div>
              <label style={styles.label}>Nueva contraseña</label>
              <div style={styles.inputWrapper}>
                <span style={styles.inputIcon}><LockIcon /></span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  style={styles.input}
                  autoFocus
                />
              </div>
              
              {password && (
                <>
                  <div style={styles.strengthMeter}>
                    {[0, 1, 2, 3, 4].map((i) => (
                      <div
                        key={i}
                        style={{
                          ...styles.strengthBar,
                          background: i < strength ? strengthColors[strength - 1] : 'var(--border)',
                        }}
                      />
                    ))}
                  </div>
                  <div style={{...styles.strengthText, color: strengthColors[strength - 1] || 'var(--muted)'}}>
                    {strengthLabels[strength - 1] || ''}
                  </div>
                </>
              )}

              <div style={{marginTop: '0.75rem'}}>
                {passwordRequirements.map((req, index) => (
                  <div
                    key={index}
                    style={{
                      ...styles.requirement,
                      ...(req.met ? styles.requirementMet : styles.requirementNotMet),
                    }}
                  >
                    {req.met ? <CheckIcon /> : <XIcon />}
                    <span>{req.label}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label style={styles.label}>Confirmar contraseña</label>
              <div style={styles.inputWrapper}>
                <span style={styles.inputIcon}><LockIcon /></span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  style={{
                    ...styles.input,
                    borderColor: confirmPassword && password !== confirmPassword ? 'var(--danger)' : 'var(--border)',
                  }}
                />
              </div>
              {confirmPassword && password !== confirmPassword && (
                <p style={{fontSize: '0.75rem', color: 'var(--danger)', marginTop: '0.25rem'}}>
                  Las contraseñas no coinciden
                </p>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !token}
            style={{
              ...styles.submitButton,
              opacity: loading || !token ? 0.7 : 1,
              cursor: loading || !token ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Guardando...' : 'Restablecer contraseña'}
          </button>
        </form>

        <Link href="/login" style={styles.backButton}>
          ← Volver al login
        </Link>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div style={{textAlign: 'center', padding: '2rem'}}>Cargando...</div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
```

### Paso 3.4: Crear Página de Cambiar Contraseña (Perfil)

**Crear archivo `uis/backoffice/src/app/account/change-password/page.tsx`:**

```tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { changePassword } from '@/lib/auth/api';

const LockIcon = () => (
  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-6 h-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
);

const XIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '2rem 1rem',
  } as React.CSSProperties,
  card: {
    width: '100%',
    maxWidth: '400px',
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '1rem',
    padding: '2rem 1.75rem',
  } as React.CSSProperties,
  logo: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.75rem',
    marginBottom: '1.5rem',
  } as React.CSSProperties,
  logoIcon: {
    width: '42px',
    height: '42px',
    borderRadius: '12px',
    background: 'linear-gradient(135deg, #ff8c42, #ff6b35)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  } as React.CSSProperties,
  title: {
    fontFamily: 'var(--font-jakarta), sans-serif',
    fontSize: '1.75rem',
    fontWeight: 800,
    marginBottom: '0.35rem',
    textAlign: 'center' as const,
  } as React.CSSProperties,
  subtitle: {
    color: 'var(--muted)',
    fontSize: '0.92rem',
    textAlign: 'center' as const,
    marginBottom: '1.75rem',
  } as React.CSSProperties,
  fieldGroup: {
    display: 'grid',
    gap: '0.9rem',
    marginBottom: '1.25rem',
  } as React.CSSProperties,
  label: {
    display: 'block',
    color: 'var(--muted)',
    fontSize: '0.82rem',
    fontWeight: 600,
    marginBottom: '0.35rem',
  } as React.CSSProperties,
  inputWrapper: {
    position: 'relative' as const,
  } as React.CSSProperties,
  inputIcon: {
    position: 'absolute' as const,
    left: '0.75rem',
    top: '50%',
    transform: 'translateY(-50%)',
    color: 'var(--muted)',
    opacity: 0.6,
    fontSize: '0.9rem',
  } as React.CSSProperties,
  input: {
    width: '100%',
    padding: '0.65rem 0.75rem 0.65rem 2.25rem',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid var(--border)',
    borderRadius: '0.65rem',
    color: 'var(--fg)',
    fontSize: '0.92rem',
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
  } as React.CSSProperties,
  inputError: {
    borderColor: 'var(--danger)',
    boxShadow: '0 0 0 2px rgba(255,125,125,0.2)',
  } as React.CSSProperties,
  submitButton: {
    width: '100%',
    padding: '0.8rem',
    border: '0',
    borderRadius: '999px',
    background: 'linear-gradient(135deg, #2dd6a4, #4a8cff)',
    color: '#03121f',
    fontFamily: 'inherit',
    fontWeight: 700,
    fontSize: '0.95rem',
    cursor: 'pointer',
    transition: 'transform 0.2s ease, opacity 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
  } as React.CSSProperties,
  backButton: {
    display: 'block',
    width: '100%',
    textAlign: 'center' as const,
    marginTop: '1rem',
    color: 'var(--muted)',
    textDecoration: 'none',
    fontSize: '0.85rem',
  } as React.CSSProperties,
  successBox: {
    textAlign: 'center' as const,
    padding: '2rem 1rem',
  } as React.CSSProperties,
  successIcon: {
    width: '64px',
    height: '64px',
    borderRadius: '50%',
    background: 'rgba(45, 214, 164, 0.15)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 1.5rem',
  } as React.CSSProperties,
  errorMessage: {
    background: 'rgba(255, 125, 125, 0.1)',
    border: '1px solid rgba(255, 125, 125, 0.3)',
    borderRadius: '0.5rem',
    padding: '0.75rem',
    marginBottom: '1rem',
    color: 'var(--danger)',
    fontSize: '0.85rem',
    textAlign: 'center' as const,
  } as React.CSSProperties,
  strengthMeter: {
    display: 'flex',
    gap: '0.25rem',
    marginTop: '0.5rem',
  } as React.CSSProperties,
  strengthBar: {
    flex: 1,
    height: '4px',
    borderRadius: '2px',
    background: 'var(--border)',
    transition: 'background 0.2s ease',
  } as React.CSSProperties,
  strengthText: {
    fontSize: '0.75rem',
    marginTop: '0.25rem',
    color: 'var(--muted)',
  } as React.CSSProperties,
  requirement: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    fontSize: '0.8rem',
    marginBottom: '0.25rem',
  } as React.CSSProperties,
  requirementMet: {
    color: '#2dd6a4',
  } as React.CSSProperties,
  requirementNotMet: {
    color: 'var(--muted)',
  } as React.CSSProperties,
};

export default function ChangePasswordPage() {
  const router = useRouter();
  const { user } = useAuth();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const getPasswordStrength = (pwd: string) => {
    let strength = 0;
    if (pwd.length >= 6) strength++;
    if (pwd.length >= 8) strength++;
    if (/[A-Z]/.test(pwd)) strength++;
    if (/[0-9]/.test(pwd)) strength++;
    return strength;
  };

  const strength = getPasswordStrength(newPassword);
  const strengthColors = ['#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#2dd6a4'];
  const strengthLabels = ['Muy débil', 'Débil', 'Media', 'Fuerte', 'Muy fuerte'];

  const passwordRequirements = [
    { label: 'Mínimo 6 caracteres', met: newPassword.length >= 6 },
    { label: 'Una letra mayúscula', met: /[A-Z]/.test(newPassword) },
    { label: 'Un número', met: /[0-9]/.test(newPassword) },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden');
      return;
    }

    if (currentPassword === newPassword) {
      setError('La nueva contraseña no puede ser igual a la actual');
      return;
    }

    setLoading(true);

    try {
      await changePassword(currentPassword, newPassword);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Error al cambiar la contraseña. Verifica tu contraseña actual.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <div style={styles.logo}>
            <div style={styles.logoIcon}>🔥</div>
            <span style={styles.title}>Brasaland</span>
          </div>
          <div style={styles.successBox}>
            <div style={styles.successIcon}>
              <CheckIcon />
            </div>
            <h2 style={{...styles.title, fontSize: '1.25rem', marginBottom: '0.75rem'}}>
              ¡Contraseña cambiada!
            </h2>
            <p style={{...styles.subtitle, marginBottom: '1.5rem'}}>
              Tu contraseña ha sido actualizada exitosamente.
            </p>
            <Link href="/account/profile" style={{...styles.submitButton, textDecoration: 'none'}}>
              Volver al perfil
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <div style={styles.logoIcon}>🔥</div>
          <span style={styles.title}>Brasaland</span>
        </div>
        
        <h1 style={styles.title}>Cambiar contraseña</h1>
        <p style={styles.subtitle}>
          Actualiza tu contraseña para mantener tu cuenta segura.
        </p>

        {error && <div style={styles.errorMessage}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={styles.fieldGroup}>
            <div>
              <label style={styles.label}>Contraseña actual</label>
              <div style={styles.inputWrapper}>
                <span style={styles.inputIcon}><LockIcon /></span>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  style={styles.input}
                  autoFocus
                />
              </div>
            </div>

            <div>
              <label style={styles.label}>Nueva contraseña</label>
              <div style={styles.inputWrapper}>
                <span style={styles.inputIcon}><LockIcon /></span>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  style={styles.input}
                />
              </div>
              
              {newPassword && (
                <>
                  <div style={styles.strengthMeter}>
                    {[0, 1, 2, 3, 4].map((i) => (
                      <div
                        key={i}
                        style={{
                          ...styles.strengthBar,
                          background: i < strength ? strengthColors[strength - 1] : 'var(--border)',
                        }}
                      />
                    ))}
                  </div>
                  <div style={{...styles.strengthText, color: strengthColors[strength - 1] || 'var(--muted)'}}>
                    {strengthLabels[strength - 1] || ''}
                  </div>
                </>
              )}

              <div style={{marginTop: '0.75rem'}}>
                {passwordRequirements.map((req, index) => (
                  <div
                    key={index}
                    style={{
                      ...styles.requirement,
                      ...(req.met ? styles.requirementMet : styles.requirementNotMet),
                    }}
                  >
                    {req.met ? <CheckIcon /> : <XIcon />}
                    <span>{req.label}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label style={styles.label}>Confirmar nueva contraseña</label>
              <div style={styles.inputWrapper}>
                <span style={styles.inputIcon}><LockIcon /></span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  style={{
                    ...styles.input,
                    borderColor: confirmPassword && newPassword !== confirmPassword ? 'var(--danger)' : 'var(--border)',
                  }}
                />
              </div>
              {confirmPassword && newPassword !== confirmPassword && (
                <p style={{fontSize: '0.75rem', color: 'var(--danger)', marginTop: '0.25rem'}}>
                  Las contraseñas no coinciden
                </p>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              ...styles.submitButton,
              opacity: loading ? 0.7 : 1,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Guardando...' : 'Cambiar contraseña'}
          </button>
        </form>

        <Link href="/account/profile" style={styles.backButton}>
          ← Volver al perfil
        </Link>
      </div>
    </div>
  );
}
```

### Paso 3.5: Agregar Enlace en Página de Login

**Editar `uis/backoffice/src/app/login/page.tsx`:**

Agregar este enlace debajo del checkbox "Recordarme":

```tsx
<div style={styles.checkboxRow}>
  <label style={styles.checkboxLabel}>
    <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
    Recordarme
  </label>
  <Link href="/forgot-password" style={styles.forgotLink}>
    ¿Olvidaste tu contraseña?
  </Link>
</div>
```

---

## 4. Integración con Resend Email

### Paso 4.1: Crear Cuenta en Resend

1. Ve a [resend.com](https://resend.com) y crea una cuenta gratuita
2. Verifica tu email

### Paso 4.2: Obtener API Key

1. En el dashboard, ve a **API Keys**
2. Haz clic en **Create API Key**
3. Copia la clave (empieza con `re_...`)
4. Agrégala a tu archivo `.env`:
   ```
   RESEND_API_KEY=re_tu_clave_aqui
   ```

### Paso 4.3: Verificar Dominio (Opcional pero Recomendado)

1. En el dashboard, ve a **Domains**
2. Haz clic en **Add Domain**
3. Ingresa tu dominio (ej: `brasaland.com`)
4. Configura los registros DNS que Resend te indique:
   - **TXT record** para verificación
   - **CNAME record** para DKIM
   - **MX record** para devolución de correo
5. Espera a que se verifique (puede tomar hasta 48 horas)
6. Una vez verificado, configura el email remitente en `.env`:
   ```
   RESEND_FROM_EMAIL=noreply@brasaland.com
   ```

### Paso 4.4: Probar Envío

```bash
# Inicia el servidor
cd services/api
uvicorn app.main:app --reload

# En otro terminal, prueba el endpoint
curl -X POST http://localhost:8000/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "tu-email@gmail.com"}'
```

---

## 5. Pruebas y Validación

### Prueba 1: Flujo Completo de Recuperación

```bash
# 1. Solicitar reseteo
curl -X POST http://localhost:8000/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@brasaland.com"}'

# Respuesta esperada:
# {"detail":"Si el email existe, recibirás un enlace de recuperación."}

# 2. Revisa tu correo y copia el token del enlace

# 3. Restablecer contraseña (reemplaza TOKEN con el real)
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token": "TOKEN", "new_password": "NuevaClave123"}'

# Respuesta esperada:
# {"detail":"Contraseña actualizada correctamente."}

# 4. Login con nueva contraseña
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@brasaland.com", "password": "NuevaClave123"}'

# Respuesta esperada:
# {"access_token": "eyJ...", "token_type": "bearer"}
```

### Prueba 2: Cambio de Contraseña (Autenticado)

```bash
# 1. Login para obtener token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@brasaland.com", "password": "NuevaClave123"}' | jq -r '.access_token')

# 2. Cambiar contraseña
curl -X POST http://localhost:8000/auth/change-password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"current_password": "NuevaClave123", "new_password": "OtraClave456"}'

# Respuesta esperada:
# {"detail":"Contraseña cambiada correctamente."}
```

### Prueba 3: Validaciones de Error

```bash
# Token inválido
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token": "token_invalido", "new_password": "Clave123"}'

# Respuesta esperada:
# {"detail":"Token inválido o expirado"}

# Contraseña débil
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token": "TOKEN_VALIDO", "new_password": "123"}'

# Respuesta esperada:
# {"detail":"Password must be at least 6 characters; must contain at least one uppercase letter"}
```

---

## 6. Troubleshooting

### Problema 1: "RESEND_API_KEY not configured"

**Solución:** Verifica que tu `.env` tenga la API key de Resend:
```bash
cat services/api/.env | grep RESEND
```

### Problema 2: "Token inválido o expirado"

**Soluciones:**
1. Verifica que `PASSWORD_RESET_SECRET_KEY` esté configurado en `.env`
2. El token expira en 30 minutos por defecto
3. Asegúrate de que el token no haya sido usado anteriormente

### Problema 3: "Password must be at least 6 characters"

**Solución:** La contraseña debe cumplir:
- Mínimo 6 caracteres
- Al menos una letra mayúscula
- Al menos un número

### Problema 4: Emails no se envían

**Soluciones:**
1. Verifica que el dominio esté verificado en Resend
2. Revisa los logs del servidor para errores
3. Asegúrate de que `RESEND_FROM_EMAIL` esté en el dominio verificado

### Problema 5: Base de datos no se encuentra

**Solución:** Verifica la ruta en `.env`:
```bash
cat services/api/.env | grep SUPPLIERS_DB_PATH
```

Debe ser relativo a `services/api/`:
```
SUPPLIERS_DB_PATH=data/suppliers.json
```

---

## 📚 Recursos Adicionales

- **Resend Docs:** [https://resend.com/docs](https://resend.com/docs)
- **FastAPI Docs:** [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Next.js Docs:** [https://nextjs.org/docs](https://nextjs.org/docs)

---

**¡Listo!** 🎉 Con esta guía deberías poder implementar toda la funcionalidad de recuperación y cambio de contraseña manualmente.

¿Necesitas ayuda con algún paso específico?
