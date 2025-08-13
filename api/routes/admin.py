"""
Rutas administrativas y utilidades de configuración manual.

Importante: considera proteger estas rutas con `get_current_admin`.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database.db import SessionLocal
from database import models
from database.models import Operator  # Import Operator for toggle_admin
from pydantic import BaseModel

router = APIRouter()


def get_db():
    """Dependencia: inyecta una sesión de base de datos por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. Listar cargadores
@router.get("/charge_points")
def get_charge_points(db: Session = Depends(get_db)):
    """Lista todos los registros de cargadores (tabla `chargers`)."""
    return db.query(models.ChargePoint).all()

# 2. Registrar cargador
class ChargerCreate(BaseModel):
    """Payload para crear un nuevo cargador en BD manualmente."""
    id: str
    vendor: str
    model: str

@router.post("/charge_points")
def register_cp(data: ChargerCreate, db: Session = Depends(get_db)):
    """Crea un cargador si no existe un registro con el mismo `id`."""
    existing = db.query(models.ChargePoint).filter_by(id=data.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Cargador ya registrado")

    cp = models.ChargePoint(id=data.id, vendor=data.vendor, model=data.model)
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp

# 3. Agregar RFID
@router.post("/whitelist")
def add_whitelist_entry(cp_id: str, id_tag: str, db: Session = Depends(get_db)):
    """Agrega un `idTag` (RFID) a la whitelist de un cargador."""
    entry = models.WhitelistEntry(charge_point_id=cp_id, id_tag=id_tag)
    db.add(entry)
    db.commit()
    return {"message": f"Tag {id_tag} agregado a whitelist del CP {cp_id}"}

# 4. Ver whitelist
@router.get("/whitelist/{cp_id}")
def list_whitelist(cp_id: str, db: Session = Depends(get_db)):
    """Lista las entradas de whitelist para un cargador."""
    return db.query(models.WhitelistEntry).filter_by(charge_point_id=cp_id).all()

# 5. Registrar operador
class OperatorCreate(BaseModel):
    """Payload para crear un operador (usuario) manualmente."""
    username: str
    email: str
    password_hash: str

@router.post("/operators")
def create_operator(data: OperatorCreate, db: Session = Depends(get_db)):
    """Crea un operador usando un hash de contraseña ya calculado."""
    user = models.Operator(
        username=data.username,
        email=data.email,
        password_hash=data.password_hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# 6. Consultar sesiones de carga
@router.get("/sessions")
def get_sessions(db: Session = Depends(get_db)):
    """Lista sesiones de carga, ordenadas por inicio descendente."""
    return db.query(models.ChargingSession).order_by(
        models.ChargingSession.start_time.desc()
    ).all()

# 7. Limpieza de mensajes viejos (opcional)
@router.delete("/cleanup/meter_values")
def delete_old_meter_values(db: Session = Depends(get_db)):
    """Elimina `MeterValues` con más de 30 días de antigüedad."""
    from datetime import datetime, timedelta
    threshold = datetime.utcnow() - timedelta(days=30)
    deleted = db.query(models.OcppMessage)\
                .filter(models.OcppMessage.action == "MeterValues")\
                .filter(models.OcppMessage.timestamp < threshold)\
                .delete()
    db.commit()
    return {"deleted": deleted}

# 8. Toggle admin
class ToggleAdminIn(BaseModel):
    """Entrada para alternar el rol admin de un usuario."""
    user_id: int
    make_admin: bool

@router.post("/toggle_admin")
def toggle_admin(
    data: ToggleAdminIn,
    db: Session = Depends(get_db),
    # could add admin master token dependency here
):
    """Activa/Desactiva el flag `is_admin` de un usuario.`"""
    user = db.query(Operator).filter_by(id=data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_admin = data.make_admin
    db.commit()
    db.refresh(user)
    return {"user_id": user.id, "is_admin": user.is_admin}
