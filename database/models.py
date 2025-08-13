"""
Modelos ORM de la base de datos para el servidor OCPP y la API.

Incluye entidades para cargadores, conectores, transacciones, mediciones,
logs OCPP, usuarios y facilities.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, Boolean
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

Base = declarative_base()


class Charger(Base):
    """Cargador físico identificado por `code` y asociado a una facility."""
    __tablename__ = "chargers"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    brand = Column(String(50), nullable=True)
    box_serial_number = Column(String(100), nullable=True)
    name = Column(String(100), nullable=True)
    location = Column(String(200), nullable=True)
    admin_status = Column(String(50), nullable=True)
    proxy_status = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    connectors = relationship("Connector", back_populates="charger", cascade="all, delete-orphan")
    transactions = relationship("ChargeTransaction", back_populates="charger", cascade="all, delete-orphan")
    log_ocpp = relationship("LogOcpp", back_populates="charger", cascade="all, delete-orphan")
    log_ocpp_proxy_connections = relationship(
        "LogOcppProxyConnection", back_populates="charger", cascade="all, delete-orphan"
    )
    heartbeat_logs = relationship("HeartbeatLog", back_populates="charger", cascade="all, delete-orphan")
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=True)


class Connector(Base):
    """Conector físico de un cargador (toma), numerado por `connector_number`."""
    __tablename__ = "connectors"
    
    id = Column(Integer, primary_key=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"), nullable=False)
    connector_number = Column(Integer, nullable=False)
    name = Column(String(100), nullable=True)
    status = Column(String(50), nullable=True)
    error_code = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    charger = relationship("Charger", back_populates="connectors")
    transactions = relationship("ChargeTransaction", back_populates="connector", cascade="all, delete-orphan")
    log_ocpp = relationship("LogOcpp", back_populates="connector", cascade="all, delete-orphan")
    log_ocpp_proxy_connections = relationship(
        "LogOcppProxyConnection", back_populates="connector", cascade="all, delete-orphan"
    )


class ChargeTransaction(Base):
    """Sesión de carga con mediciones y estado, enlazada a conector y cargador."""
    __tablename__ = "charge_transactions"
    
    id = Column(Integer, primary_key=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"), nullable=False)
    connector_id = Column(Integer, ForeignKey("connectors.id"), nullable=False)
    transaction_id = Column(Integer, nullable=True)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    delivered_energy = Column(Float, nullable=True)
    user_id = Column(Integer, nullable=True)
    meter_start = Column(Float, nullable=True)
    meter_stop = Column(Float, nullable=True)
    net_energy = Column(Float, nullable=True)
    status = Column(String(50), nullable=True)
    id_tag = Column(String(100), nullable=True)
    
    # Relaciones
    charger = relationship("Charger", back_populates="transactions")
    connector = relationship("Connector", back_populates="transactions")
    meter_values = relationship("MeterValue", back_populates="transaction", cascade="all, delete-orphan")


class MeterValue(Base):
    """Medición puntual reportada por el cargador durante una transacción."""
    __tablename__ = "meter_values_logs"
    
    id = Column(Integer, primary_key=True)
    meter_date = Column(DateTime, default=datetime.utcnow)
    value = Column(Float, nullable=True)
    context = Column(String(100), nullable=True)
    format = Column(String(50), nullable=True)
    measurand = Column(String(100), nullable=True)
    phase = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=True)
    transaction_id = Column(Integer, ForeignKey("charge_transactions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    transaction = relationship("ChargeTransaction", back_populates="meter_values")


class MeterValue15min(Base):
    """Agregación de `MeterValue` en intervalos de 15 minutos (si aplica)."""
    __tablename__ = "meter_values_15min_logs"
    
    id = Column(Integer, primary_key=True)
    meter_date = Column(DateTime, default=datetime.utcnow)
    meter_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PartitionHistory(Base):
    """Histórico de particiones por tabla (opcional, para mantenimiento)."""
    __tablename__ = "partition_history"
    
    id = Column(Integer, primary_key=True)
    table_name = Column(String(100), nullable=False)
    partition_start = Column(DateTime, nullable=False)
    partition_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LogOcpp(Base):
    """Registro de mensajes/eventos OCPP recibidos o enviados."""
    __tablename__ = "log_ocpp"
    
    id = Column(Integer, primary_key=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"), nullable=True)
    connector_id = Column(Integer, ForeignKey("connectors.id"), nullable=True)
    transaction_id = Column(Integer, nullable=True)
    message_type = Column(String(50), nullable=True)
    action = Column(String(50), nullable=True)
    payload = Column(JSONB, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    charger = relationship("Charger", back_populates="log_ocpp")
    connector = relationship("Connector", back_populates="log_ocpp")


class LogOcppDuplicatedIDs(Base):
    """Registro de IDs OCPP duplicados detectados (anti-replay)."""
    __tablename__ = "log_ocpp_duplicated_ids"
    
    id = Column(Integer, primary_key=True)
    unique_id = Column(String(100), nullable=False)
    event_timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LogOcppProxyConnection(Base):
    """Registro de eventos en el proxy/conexión OCPP (errores, estado)."""
    __tablename__ = "log_ocpp_proxy_connection"
    
    id = Column(Integer, primary_key=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"), nullable=True)
    connector_id = Column(Integer, ForeignKey("connectors.id"), nullable=True)
    action = Column(String(50), nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    charger = relationship("Charger", back_populates="log_ocpp_proxy_connections")
    connector = relationship("Connector", back_populates="log_ocpp_proxy_connections")


class Operator(Base):
    """Usuario operador del sistema; puede tener rol administrador."""
    __tablename__ = "operators"
    id           = Column(Integer, primary_key=True)
    email        = Column(String, unique=True, nullable=False)
    username     = Column(String, nullable=False)
    password_hash= Column(String, nullable=False)
    is_admin     = Column(Boolean, default=False, nullable=False)   # ← nuevo
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    rfid_tags = relationship("RFIDTag", back_populates="user", cascade="all, delete-orphan")
    payment_intents = relationship("PaymentIntent", back_populates="user", cascade="all, delete-orphan")


class RFIDTag(Base):
    """Etiqueta RFID asociada a un operador para autorizar cargas."""
    __tablename__ = "rfid_tags"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    id_tag = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("Operator", back_populates="rfid_tags")


class PaymentIntent(Base):
    """Intento de pago vinculado a usuario y cargador (integración externa)."""
    __tablename__ = "payment_intents"

    id = Column(Integer, primary_key=True)
    intent_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    charger_code = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("Operator", back_populates="payment_intents")


class HeartbeatLog(Base):
    """Latidos periódicos recibidos desde los cargadores."""
    __tablename__ = "heartbeat_logs"
    
    id = Column(Integer, primary_key=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"), nullable=True)
    connector_id = Column(Integer, nullable=True)
    reported_time = Column(DateTime, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    payload = Column(JSONB, nullable=True)
    
    charger = relationship("Charger", back_populates="heartbeat_logs")

class Facility(Base):
    """Instalación física donde se ubican uno o varios cargadores."""
    __tablename__ = "facilities"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    chargers = relationship("Charger", backref="facility", lazy="dynamic")
