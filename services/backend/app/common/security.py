"""security.py — Brasaland · Autenticación JWT (reutilizable entre dominios)

- Hash de contraseñas con bcrypt (passlib)
- Creación y validación de tokens JWT (python-jose)
- Dependencia get_current_user: protege endpoints de escritura
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.domains.auth.models import Usuario

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def hash_password(plain: str) -> str:
    """Hash de contraseña con bcrypt."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica una contraseña plana contra su hash."""
    return pwd_context.verify(plain, hashed)


def create_access_token(email: str, rol: str) -> str:
    """Crea un JWT firmado con expiración configurable."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": email, "rol": rol, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Usuario:
    """Dependencia de FastAPI: valida el Bearer token y devuelve el Usuario.

    Protege POST/PUT/DELETE. Lanza 401 si el token es inválido,
    el usuario no existe o está inactivo.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise credentials_error
    except JWTError as exc:
        raise credentials_error from exc

    user = db.query(Usuario).filter(Usuario.email == email).first()
    if user is None or not user.activo:
        raise credentials_error
    return user