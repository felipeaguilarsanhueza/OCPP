"""
Rutas para consultar conectores de un cargador y cargadores por instalación.

Prefijo: `/chargers`. Protegidas por JWT.
"""
# api/routes/connectors.py

from fastapi import APIRouter, Depends, HTTPException, Path
from typing import List
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from database.db import SessionLocal
from database import crud
from database.models import Connector as ConnectorModel
from core.auth import get_current_user
from api.schemas.facilities import FacilityIn, FacilityOut, ChargerOut

router = APIRouter(prefix="/chargers", tags=["Connectors"])

class ConnectorOut(BaseModel):
    """Salida con información básica de un conector."""
    id: int
    charger_id: int
    connector_number: int
    name: str | None
    status: str | None
    error_code: str | None

    model_config = ConfigDict(from_attributes=True)

@router.get(
    "/{charger_id}/connectors",
    response_model=List[ConnectorOut],
    dependencies=[Depends(get_current_user)]
)
def get_connectors(
    charger_id: int = Path(..., description="ID del cargador")
):
    """Lista conectores asociados a un cargador por su ID interno."""
    db: Session = SessionLocal()
    try:
        # Usa el CRUD que acabamos de definir
        conns = crud.list_connectors(db, charger_id)
        if conns is None:
            raise HTTPException(404, f"Charger {charger_id} not found")
        return conns
    finally:
        db.close()

@router.get(
    "/{facility_id}/chargers",
    response_model=List[ChargerOut],  # crea un Pydantic ChargerOut si no existe
    dependencies=[Depends(get_current_user)]
)
def list_chargers_by_facility(facility_id: int):
    """Lista cargadores asociados a una instalación (facility)."""
    db = SessionLocal()
    try:
        chargers = crud.list_chargers_for_facility(db, facility_id)
        if not chargers:
            raise HTTPException(404, detail="Facility not found or no chargers")
        return chargers
    finally:
        db.close()