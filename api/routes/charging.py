"""
Rutas para control de carga OCPP (arranque/parada remota, configuración, etc.).

Prefijo: `/charging`. Protegidas por JWT y operan sobre conexiones activas via `ConnectionManager`.
"""
# api/routes/charging.py

from fastapi import APIRouter, HTTPException, Body, Query, Depends
from pydantic import BaseModel
from ocpp.v16 import call
from core.connection_manager import manager
from sqlalchemy.orm import Session
from core.auth import get_current_user, get_db
from database import crud
from database.models import PaymentIntent
from typing import List
from api.schemas.charging import MeterValueOut
from database.models import ChargeTransaction, Connector, Charger


router = APIRouter(
    tags=["Charging"],
    prefix="/charging",
    dependencies=[Depends(get_current_user)]
)

class RemoteStartIn(BaseModel):
    """Entrada para la orden de arranque remoto de transacción."""
    cp_id: str
    connector_id: int = 1
    id_tag: str | None = None
    payment_intent_id: str | None = None

@router.post("/remote_start")
async def remote_start(
    data: RemoteStartIn,
    db: Session = Depends(get_db)
):
    """Envía `RemoteStartTransaction` al cargador conectado indicado."""
    # Validación básica
    if not data.cp_id or (not data.id_tag and not data.payment_intent_id):
        raise HTTPException(status_code=400, detail="Debe especificar cp_id y (id_tag o payment_intent_id)")

    cp = manager.get(data.cp_id)
    if cp is None:
        raise HTTPException(status_code=404, detail="Charge point no conectado")

    # Si viene payment_intent, verificar que esté pagado
    effective_id_tag = data.id_tag
    if data.payment_intent_id:
        pi = db.query(PaymentIntent).filter_by(intent_id=data.payment_intent_id).first()
        if not pi or pi.status != "paid":
            raise HTTPException(status_code=400, detail="Payment intent inválido o no pagado")
        effective_id_tag = data.payment_intent_id

    # Marcamos que esperamos arrancar esta tx
    cp.allow_remote_start()

    # Envío de la orden OCPP
    req = call.RemoteStartTransactionPayload(
        id_tag=effective_id_tag,
        connector_id=data.connector_id
    )
    try:
        resp = await cp.call(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Si no lo aceptan, limpiamos el flag
    if resp.status != "Accepted":
        cp.pending_remote_start = False
        raise HTTPException(status_code=400, detail=f"Inicio remoto rechazado: {resp.status}")

    return {"status": resp.status}


@router.post("/remote_stop")
async def remote_stop_transaction(
    cp_id: str = Query(...),
    transaction_id: int = Query(...)
):
    """Envía `RemoteStopTransaction` para la transacción activa indicada."""
    cp = manager.get(cp_id)
    if cp is None:
        raise HTTPException(status_code=404, detail=f"Cargador '{cp_id}' no conectado.")

    # Verificamos que coincide con la tx activa
    if cp.active_transaction != transaction_id:
        raise HTTPException(
            status_code=400,
            detail=f"Transaction ID {transaction_id} no coincide con active_transaction {cp.active_transaction}"
        )

    # Marcamos que esperamos parar esta tx
    cp.pending_remote_stop = True

    payload = call.RemoteStopTransactionPayload(transaction_id=transaction_id)
    try:
        resp = await cp.call(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": resp.status}


@router.get("/active_transaction")
def get_active_transaction(
    cp_id: str = Query(..., description="Código del charge point"),
    connector_id: int = Query(..., description="Número de conector"),
    db: Session = Depends(get_db)
):
    """Recupera el `transaction_id` activo desde memoria o base de datos."""
    # 1) Priorizar la tx real en memoria
    cp = manager.get(cp_id)
    if cp and cp.active_transaction:
        return {"transaction_id": cp.active_transaction}

    # 2) Buscar la última tx real en BD (id_tag != NULL)
    real_tx = (
        db.query(ChargeTransaction)
          .join(Connector, ChargeTransaction.connector_id == Connector.id)
          .join(Charger,   ChargeTransaction.charger_id   == Charger.id)
          .filter(Charger.code == cp_id)
          .filter(Connector.connector_number == connector_id)
          .filter(ChargeTransaction.end_time.is_(None))
          .filter(ChargeTransaction.id_tag.is_not(None))
          .order_by(ChargeTransaction.start_time.desc())
          .first()
    )
    if real_tx:
        return {"transaction_id": real_tx.transaction_id or real_tx.id}

    # 3) Fallback genérico (incluye placeholders)
    any_tx = crud.get_active_transaction(db, charger_code=cp_id, connector_number=connector_id)
    if any_tx:
        return {"transaction_id": any_tx.transaction_id or any_tx.id}

    # 4) Ninguna tx activa
    raise HTTPException(
        status_code=404,
        detail=f"No hay transacción activa para cp_id='{cp_id}' conector={connector_id}"
    )

@router.get("/connected")
def get_connected_charge_points():
    """Lista códigos de cargadores actualmente conectados al servidor OCPP."""
    return {"connected_charge_points": list(manager.all())}

@router.post("/set_device_configuration")
async def set_device_configuration(
    cp_id: str = Body(..., embed=True),
    key: str = Body(..., embed=True),
    value: str = Body(..., embed=True)
):
    """Cambia una clave de configuración del cargador mediante OCPP."""
    cp = manager.get(cp_id)
    if cp is None:
        raise HTTPException(status_code=404, detail=f"Cargador '{cp_id}' no está conectado")

    payload = call.ChangeConfigurationPayload(key=key, value=value)
    try:
        resp = await cp.call(payload)
        return {"status": resp.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar configuración: {e}")

@router.post("/whitelist")
async def send_whitelist(
    cp_id: str = Body(..., embed=True),
    idtags: list[str] = Body(..., embed=True),
    version: int = Body(1, embed=True)
):
    """Envía una lista local de autorización (RFIDs) al cargador."""
    if not idtags:
        raise HTTPException(status_code=400, detail="idtags no puede estar vacío")

    cp = manager.get(cp_id)
    if cp is None:
        raise HTTPException(status_code=404, detail="Cargador no conectado")

    local_auth_list = [{"idTag": tag} for tag in idtags]
    payload = call.SendLocalListPayload(
        list_version=version,
        local_authorization_list=local_auth_list,
        update_type="Full"
    )
    try:
        resp = await cp.call(payload)
        return {"status": resp.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_configuration")
async def get_configuration(
    cp_id: str = Query(...),
    keys: str = Query("")
):
    """Obtiene configuración del dispositivo (por claves separadas por coma)."""
    cp = manager.get(cp_id)
    if cp is None:
        raise HTTPException(status_code=404, detail="Charge point not connected.")

    key_list = keys.split(",") if keys else []
    payload = call.GetConfigurationPayload(key=key_list)
    try:
        resp = await cp.call(payload)
        return {
            "configuration_key": resp.configuration_key,
            "unknown_key": resp.unknown_key
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{transaction_id}/meter_values", response_model=List[MeterValueOut])
def get_session_meter_values(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Devuelve los `MeterValues` registrados para la sesión indicada."""
    tx = crud.get_transaction_by_id(db, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Session not found")

    values = crud.list_meter_values_for_transaction(db, transaction_id)
    return values
