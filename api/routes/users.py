"""
Rutas de usuario autenticado (perfil y etiquetas RFID).

Prefijo: `/users`. Protegidas por JWT.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import List
from sqlalchemy.orm import Session
from core.auth import get_current_user, get_db
from database import crud

router = APIRouter(prefix="/users", tags=["Users"])

class UpdateProfileIn(BaseModel):
    """Payload para actualizar nombre de usuario."""
    username: str

class ProfileOut(BaseModel):
    """Respuesta con datos de perfil y etiquetas RFID."""
    id: int
    email: str
    username: str
    rfid_tags: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class RFIDTagIn(BaseModel):
    """Entrada para agregar una etiqueta RFID al usuario."""
    id_tag: str

class RFIDTagOut(BaseModel):
    """Salida con la etiqueta RFID recién agregada."""
    id_tag: str

    model_config = ConfigDict(from_attributes=True)

@router.get("/profile", response_model=ProfileOut)
def get_profile(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene el perfil del usuario autenticado, incluyendo sus etiquetas RFID.
    """
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    tags = [tag.id_tag for tag in user.rfid_tags]
    return ProfileOut(
        id=user.id,
        email=user.email,
        username=user.username,
        rfid_tags=tags
    )

@router.put("/profile", response_model=ProfileOut)
def update_profile(
    data: UpdateProfileIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualiza el nombre de usuario del perfil autenticado.
    """
    user = crud.update_user_name(db, current_user.id, data.username)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    tags = [tag.id_tag for tag in user.rfid_tags]
    return ProfileOut(
        id=user.id,
        email=user.email,
        username=user.username,
        rfid_tags=tags
    )

@router.get("/history", response_model=List[dict])
def payment_history(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista el historial de pagos asociados al usuario.
    """
    return crud.list_payments_for_user(db, current_user.id)

@router.get("/rfid", response_model=List[str])
def list_rfid_tags(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista las etiquetas RFID registradas por el usuario.
    """
    tags = crud.list_rfid_tags_for_user(db, current_user.id)
    return [tag.id_tag for tag in tags]

@router.post("/rfid", response_model=RFIDTagOut, status_code=201)
def add_rfid_tag(
    tag_in: RFIDTagIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Agrega una nueva etiqueta RFID al usuario autenticado.
    """
    tag = crud.add_rfid_tag_to_user(db, current_user.id, tag_in.id_tag)
    return RFIDTagOut(id_tag=tag.id_tag)
