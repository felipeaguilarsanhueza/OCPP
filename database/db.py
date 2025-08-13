"""
Configuración base de SQLAlchemy para la aplicación.

Define la URL de conexión, `engine`, fábrica de sesiones (`SessionLocal`) y la
clase base declarativa para los modelos ORM.
"""
# database/db.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Lee DATABASE_URL de entorno (Railway). Fallback local a Postgres.
import os
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ocpp_db"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()
