"""
Esquemas Pydantic para instalaciones (facilities) y cargadores.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime

# --- Facility schemas (ya los tenías, los repito por contexto) ---

class FacilityIn(BaseModel):
    """Entrada para crear/actualizar una instalación."""
    name: str
    latitude: float
    longitude: float
    description: Optional[str] = None

class FacilityOut(BaseModel):
    """Salida con datos completos de una instalación."""
    id: int
    name: str
    latitude: float
    longitude: float
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Nuevo: Charger schema para listar chargers de una facility ---

class ChargerOut(BaseModel):
    """Salida resumida de un cargador asociado a una instalación."""
    id: int
    code: str
    brand: Optional[str] = None
    charger_model: Optional[str] = None
    location: Optional[str] = None
    facility_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)