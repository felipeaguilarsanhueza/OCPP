"""
Carga de configuración desde variables de entorno usando Pydantic.

Lee `.env` en desarrollo para poblar claves como SECRET_KEY, ALGORITHM, etc.
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Esquema de variables de entorno requeridas por la app."""
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    ADMIN_MASTER_KEY: str
    ADMIN_TOKEN_EXPIRE_DAYS: int

    # Base de datos (Railway expone `DATABASE_URL` para Postgres)
    DATABASE_URL: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
