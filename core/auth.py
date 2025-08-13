"""
Autenticación y autorización de la API.

Define helpers para:
- Verificar contraseña y autenticar usuarios.
- Emitir JWT de usuario y de administrador.
- Dependencias de FastAPI (`get_current_user`, `get_current_admin`).
"""
# core/auth.py

import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Operator
from config.settings import settings

dpwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
SECRET_KEY = settings.SECRET_KEY

# Leer tu clave maestra y caducidad de admin del .env
ADMIN_MASTER_KEY = settings.ADMIN_MASTER_KEY
ADMIN_TOKEN_EXPIRE_DAYS = settings.ADMIN_TOKEN_EXPIRE_DAYS

def get_db():
    """Dependencia de FastAPI: entrega una sesión de BD y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña en texto plano contra su hash almacenado."""
    return dpwd_context.verify(plain_password, hashed_password)

def authenticate_user(db: Session, email: str, password: str) -> Optional[Operator]:
    """Busca un usuario por email y valida la contraseña."""
    user = db.query(Operator).filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Genera un JWT de usuario con expiración configurable."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_admin_token() -> str:
    """
    Genera un JWT de administrador con expiración larga.
    """
    expire = datetime.utcnow() + timedelta(days=ADMIN_TOKEN_EXPIRE_DAYS)
    payload = {"sub": "admin@local", "role": "admin", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Operator:
    """Devuelve el usuario autenticado; acepta también token maestro/admin."""
    # 1) Chequea si es tu master admin key
    if token == ADMIN_MASTER_KEY:
        # Puedes devolver aquí un objeto Operator «fantasma» con is_admin=True
        fake_admin = Operator(
            id=0,
            username="__admin__",
            email="admin@local",
            password_hash="",
            is_admin=True
        )
        return fake_admin

    # 2) Si no, decodifica como JWT normal
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        role: str | None = payload.get("role")
        if role == "admin":
            # Token admin emitido por create_admin_token
            fake_admin = Operator(
                id=0,
                username="__admin__",
                email="admin@local",
                password_hash="",
                is_admin=True
            )
            return fake_admin

        email: str | None = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(Operator).filter_by(email=email).first()
    if not user:
        raise credentials_exception
    return user


def get_current_admin(
    current_user: Operator = Depends(get_current_user)
) -> Operator:
    """Valida que el usuario actual tenga rol de administrador."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    return current_user

def get_user_or_admin(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Operator:
    """Atajo para obtener usuario autenticado o admin (mismo validador)."""
    return get_current_user(token=token, db=db)