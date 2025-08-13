"""
Esquemas Pydantic para autenticación y usuarios.
"""
from pydantic import BaseModel, EmailStr, Field
from pydantic import ConfigDict
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    """Token de acceso JWT y tipo."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Datos contenidos en el token JWT."""
    email: Optional[EmailStr] = None


class UserCreate(BaseModel):
    """
    Datos para registro de nuevo usuario.
    Acepta 'name' en el body y lo asigna a username.
    """
    email: EmailStr
    password: str
    username: str = Field(..., alias="name")

    # Permitir poblar usando el alias 'name'
    model_config = ConfigDict(populate_by_name=True)


class UserOut(BaseModel):
    """
    Respuesta tras registro o consulta de usuario.
    """
    id: int
    email: EmailStr
    username: str
    created_at: Optional[datetime]

    # Habilita ORM mode para Pydantic v2
    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserOut):
    """
    Modelo de usuario interno, incluye el hash de contraseña.
    """
    password_hash: str


class UserLogin(BaseModel):
    """
    Datos de login (form-data).
    """
    username: EmailStr
    password: str

    model_config = ConfigDict(from_attributes=True)
