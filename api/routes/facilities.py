"""
Rutas para gestionar instalaciones (facilities) y listar cargadores.

GET de list y detalle son públicos; creación/edición/borrado requieren JWT.
"""
# api/routes/facilities.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from core.auth import get_db, get_current_user
from database import crud
from api.schemas.facilities import FacilityIn, FacilityOut, ChargerOut

router = APIRouter(tags=["Facilities"])

@router.post(
    "/",
    response_model=FacilityOut,
    status_code=201,
    dependencies=[Depends(get_current_user)]
)
def create_facility(data: FacilityIn, db: Session = Depends(get_db)):
    return crud.create_facility(db, **data.dict())

@router.get(
    "/",
    response_model=List[FacilityOut],
)
def list_facilities(db: Session = Depends(get_db)):
    # << ¡SIN Depends(get_current_user)! >>
    return crud.list_facilities(db)

@router.get(
    "/{facility_id}",
    response_model=FacilityOut,
)
def get_facility(facility_id: int, db: Session = Depends(get_db)):
    # << ¡Público también! >>
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(404, "Facility not found")
    return facility

@router.put(
    "/{facility_id}",
    response_model=FacilityOut,
    dependencies=[Depends(get_current_user)]
)
def update_facility(facility_id: int, data: FacilityIn, db: Session = Depends(get_db)):
    facility = crud.update_facility(db, facility_id, **data.dict())
    if not facility:
        raise HTTPException(404, "Facility not found")
    return facility

@router.delete(
    "/{facility_id}",
    status_code=204,
    dependencies=[Depends(get_current_user)]
)
def delete_facility(facility_id: int, db: Session = Depends(get_db)):
    success = crud.delete_facility(db, facility_id)
    if not success:
        raise HTTPException(404, "Facility not found")

@router.get(
    "/{facility_id}/chargers",
    response_model=List[ChargerOut]
)
def list_chargers_by_facility(facility_id: int, db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(404, "Facility not found")
    return crud.list_chargers_for_facility(db, facility_id)
