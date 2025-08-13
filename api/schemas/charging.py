"""
Esquemas Pydantic para respuestas relacionadas con carga y conectores.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class ConnectorOut(BaseModel):
    """Información resumida de un conector físico del cargador."""
    connector_number: int
    name: str | None
    status: str | None
    error_code: str | None

    model_config = ConfigDict(from_attributes=True)

class MeterValueOut(BaseModel):
    """Salida para cada medición (MeterValue) almacenada en BD."""
    meter_date: datetime
    value: float
    context: Optional[str] = None
    format: Optional[str] = None
    measurand: Optional[str] = None
    phase: Optional[str] = None
    unit: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)