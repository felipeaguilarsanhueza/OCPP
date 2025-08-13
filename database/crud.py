"""
Funciones de acceso y manipulación de datos (CRUD) para el dominio OCPP y API.

Incluye utilidades para asegurar existencia de cargadores y conectores,
crear/cerrar transacciones, registrar logs OCPP, y gestionar usuarios/pagos
y facilities.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from database.db import SessionLocal
from database.models import (
    Charger, Connector, ChargeTransaction, MeterValue, LogOcpp, HeartbeatLog,
    Operator, RFIDTag, PaymentIntent, Facility
)

logger = logging.getLogger("ocpp")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------
# OCPP CRUD FUNCTIONS
# ---------------------

def ensure_charger_exists(code, brand=None, charger_model=None, location=None):
    """Asegura que exista un registro `Charger` para el `code` dado."""
    db = SessionLocal()
    try:
        charger = db.query(Charger).filter_by(code=code).first()
        if not charger:
            charger = Charger(
                code=code,
                brand=brand or "Unknown",
                charger_model=charger_model or "Unknown",
                location=location or ""
            )
            db.add(charger)
            db.commit()
            db.refresh(charger)
        return charger
    except Exception as e:
        logger.error(f"Error ensuring charger '{code}': {e}")
        db.rollback()
        return None
    finally:
        db.close()


def ensure_connector_exists(charger_id: int, connector_number: int):
    """Asegura que exista un `Connector` para el cargador/numero indicados."""
    db = SessionLocal()
    try:
        connector = db.query(Connector).filter_by(
            charger_id=charger_id,
            connector_number=connector_number
        ).first()
        if not connector:
            connector = Connector(
                charger_id=charger_id,
                connector_number=connector_number
            )
            db.add(connector)
            db.commit()
            db.refresh(connector)
        return connector
    except Exception as e:
        logger.error(f"Error ensuring connector {connector_number} for charger {charger_id}: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def create_charge_transaction(charger_id, connector_id, id_tag, meter_start, timestamp):
    """Crea una transacción de carga y devuelve su ID."""
    db = SessionLocal()
    try:
        tx = ChargeTransaction(
            charger_id=charger_id,
            connector_id=connector_id,
            id_tag=id_tag,
            meter_start=meter_start,
            start_time=datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        tx.transaction_id = tx.id
        db.commit()
        return tx.id
    except Exception as e:
        logger.error(f"Error creating charge transaction: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def stop_charge_transaction(transaction_id, meter_stop, timestamp):
    """Cierra una transacción de carga, actualizando medición final y tiempo."""
    db = SessionLocal()
    try:
        tx = db.query(ChargeTransaction).filter_by(id=transaction_id).first()
        if tx:
            tx.meter_stop = meter_stop
            tx.end_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            db.commit()
        return tx
    except Exception as e:
        logger.error(f"Error stopping transaction {transaction_id}: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def log_ocpp_message(
    db: Session,
    charger_id: int,
    connector_id: int | None,
    transaction_id: int | None = None,
    payload: dict | None = None,
    action: str = "MeterValues",
    message_type: str = "Request"
) -> LogOcpp:
    """Inserta un registro en `log_ocpp` con metadatos de mensaje/evento."""
    entry = LogOcpp(
        charger_id=charger_id,
        connector_id=connector_id,
        transaction_id=transaction_id,
        message_type=message_type,
        action=action,
        payload=payload,
        timestamp=datetime.utcnow()  # opcional si ya tienes default en el modelo
    )
    try:
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    except Exception:
        db.rollback()
        raise  # o captura y loguea, según convenga


def log_ocpp_meter_values(charger_id, connector_id, transaction_id, meter_values):
    """Persiste una lista de `MeterValues` reportados por el cargador."""
    db = SessionLocal()
    try:
        for entry in meter_values:
            ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            sampled = entry.get("sampledValue") or entry.get("sampled_value", [])
            for sv in sampled:
                mv = MeterValue(
                    meter_date=ts,
                    value=float(sv["value"]),
                    context=sv.get("context"),
                    format=sv.get("format"),
                    measurand=sv.get("measurand"),
                    phase=sv.get("phase"),
                    unit=sv.get("unit"),
                    transaction_id=transaction_id
                )
                db.add(mv)
        db.commit()
    except Exception as e:
        logger.error(f"Error saving meter values: {e}")
        db.rollback()
    finally:
        db.close()


def log_heartbeat(charger_id, connector_id, reported_time=None, payload=None):
    """Crea un registro en `HeartbeatLog` a partir de un latido OCPP."""
    db = SessionLocal()
    try:
        hb = HeartbeatLog(
            charger_id=charger_id,
            connector_id=connector_id,
            reported_time=reported_time,
            payload=payload
        )
        db.add(hb)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    def list_connectors(db: Session, charger_id: int) -> list[Connector]:
        return db.query(Connector).filter_by(charger_id=charger_id).all()
    

# ---------------------
# USER & AUTH CRUD
# ---------------------

def get_user_by_email(db, email: str):
    """Obtiene un usuario por su email (único)."""
    return db.query(Operator).filter_by(email=email).first()


def create_user(db, email: str, password: str, name: str):
    """Crea un usuario hasheando la contraseña con bcrypt."""
    hashed = pwd_context.hash(password)
    user = Operator(username=name, email=email, password_hash=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db, user_id: int):
    """Recupera un usuario por su ID interno."""
    return db.query(Operator).filter_by(id=user_id).first()


def update_user_name(db, user_id: int, new_name: str):
    """Actualiza el nombre de usuario y devuelve el registro actualizado."""
    user = get_user(db, user_id)
    if user:
        user.username = new_name
        db.commit()
        db.refresh(user)
    return user


def list_rfid_tags_for_user(db, user_id: int):
    """Lista etiquetas RFID asociadas a un usuario."""
    return db.query(RFIDTag).filter_by(user_id=user_id).all()


def add_rfid_tag_to_user(db, user_id: int, id_tag: str):
    """Agrega una etiqueta RFID a un usuario y la devuelve."""
    tag = RFIDTag(user_id=user_id, id_tag=id_tag)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


# ---------------------
# PAYMENT CRUD
# ---------------------

def save_payment_intent(db, intent_id: str, user_id: int, charger_code: str, amount: float):
    """Crea un intento de pago en estado `created`."""
    pi = PaymentIntent(
        intent_id=intent_id,
        user_id=user_id,
        charger_code=charger_code,
        amount=amount,
        status="created",
        created_at=datetime.utcnow()
    )
    db.add(pi)
    db.commit()
    db.refresh(pi)
    return pi


def list_payments_for_user(db, user_id: int):
    """Lista intentos de pago vinculados a un usuario."""
    return db.query(PaymentIntent).filter_by(user_id=user_id).all()


def update_payment_intent_status(db, intent_id: str, status: str):
    """Actualiza el estado de un intento de pago y lo devuelve."""
    pi = db.query(PaymentIntent).filter_by(intent_id=intent_id).first()
    if pi:
        pi.status = status
        db.commit()
        db.refresh(pi)
    return pi

# Facilities
def create_facility(db, name: str, latitude: float, longitude: float, description: str | None = None):
    """Crea una instalación y la devuelve."""
    facility = Facility(
        name=name,
        latitude=latitude,
        longitude=longitude,
        description=description,
    )
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility

def get_facility(db, facility_id: int):
    """Obtiene una instalación por ID, o None si no existe."""
    return db.query(Facility).filter(Facility.id == facility_id).first()

def list_facilities(db):
    """Devuelve instalaciones ordenadas por nombre."""
    return db.query(Facility).order_by(Facility.name).all()

def update_facility(db, facility_id: int, **updates):
    """Actualiza campos de una instalación usando kwargs y devuelve el registro."""
    facility = get_facility(db, facility_id)
    if not facility:
        return None
    for key, value in updates.items():
        setattr(facility, key, value)
    db.commit()
    db.refresh(facility)
    return facility

def delete_facility(db, facility_id: int):
    """Elimina una instalación si existe y la devuelve (o None)."""
    facility = get_facility(db, facility_id)
    if facility:
        db.delete(facility)
        db.commit()
    return facility

def list_connectors(db: Session, charger_id: int) -> list[Connector]:
    """Lista conectores de un cargador, ordenados por número de conector."""
    return (
        db.query(Connector)
          .filter_by(charger_id=charger_id)
          .order_by(Connector.connector_number)
          .all()
    )

def list_chargers_for_facility(db: Session, facility_id: int):
    """Lista cargadores asociados a una instalación, ordenados por código."""
    return (
        db.query(Charger)
          .filter_by(facility_id=facility_id)
          .order_by(Charger.code)
          .all()
    )

def list_meter_values_for_transaction(db: Session, transaction_id: int):
    """Devuelve todos los `MeterValue` de una transacción, en orden temporal."""
    return (
        db.query(MeterValue)
          .filter_by(transaction_id=transaction_id)
          .order_by(MeterValue.meter_date)
          .all()
    )

def list_meter_values_for_transaction(db: Session, transaction_id: int):
    return db.query(MeterValue).filter_by(transaction_id=transaction_id).order_by(MeterValue.meter_date).all()

def get_transaction_by_id(db: Session, tx_id: int) -> ChargeTransaction | None:
    """Obtiene una transacción por su ID interno, o None si no existe."""
    return db.query(ChargeTransaction).filter(ChargeTransaction.id == tx_id).first()

def get_active_transaction(
    db: Session,
    charger_code: str,
    connector_number: int
) -> ChargeTransaction | None:
    """Busca la última transacción sin `end_time` para charger/conector dados."""
    tx = (
        db.query(ChargeTransaction)
          .join(Connector, ChargeTransaction.connector_id == Connector.id)
          .join(Charger,   ChargeTransaction.charger_id   == Charger.id)
          .filter(Charger.code == charger_code)
          .filter(Connector.connector_number == connector_number)
          .filter(ChargeTransaction.end_time.is_(None))
          .order_by(ChargeTransaction.start_time.desc())
          .first()
    )
    return tx