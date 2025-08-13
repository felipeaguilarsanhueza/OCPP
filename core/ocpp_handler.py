
"""
Handlers de mensajes OCPP 1.6 para cada `ChargePoint` conectado.

Este módulo implementa la clase `ChargePoint` que extiende la de la librería
`ocpp` y define manejadores `@on(...)` para eventos OCPP (BootNotification,
Authorize, MeterValues, Heartbeat, Start/StopTransaction, etc.). Además, registra
actividad en la base de datos y mantiene estado en memoria por conector.
"""
from ocpp.v16 import call, call_result
from ocpp.v16.enums import RegistrationStatus, AuthorizationStatus
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.routing import on, after
from ocpp.messages import CallResult
from datetime import datetime
import logging
from normalizers import get_normalizer
from database import crud
from database.models import Connector
from database.db import SessionLocal

logger = logging.getLogger("core.ocpp_handler")


class ChargePoint(BaseChargePoint):
    """
    Representa un cargador conectado vía WebSocket, con estado y lógica OCPP.

    - Mantiene transacciones por conector en memoria.
    - Persiste eventos y métricas en la base de datos mediante `crud`.
    - Expone manejadores decorados con `@on` para cada acción OCPP soportada.
    """
    def __init__(self, id, connection):
        super().__init__(id, connection)
        # 'id' es el identificador externo (por ejemplo, el código) del Charger.
        self.id: str = id
        self.connection = connection
        self.normalizer = None
        self.active_transaction = None   # ID de la transacción activa
        self.pending_remote_start: bool = False
        self.pending_remote_stop: bool = False
        # Diccionario: connector_id -> { transaction_id, start_time }
        self.transactions: dict[int, dict] = {}
        self.last_heartbeat = datetime.utcnow()
        # Almacena el ID numérico del Charger (registro en DB) obtenido en BootNotification.
        self.db_charger_id = None

    def _now(self) -> str:
        """Devuelve timestamp UTC ISO8601 para respuestas OCPP."""
        return datetime.utcnow().isoformat()

    def allow_remote_start(self):
        """Habilita el flag para permitir arranque remoto de transacción."""
        self.pending_remote_start = True

    def store_transaction_id(self, connector_id: int, transaction_id: int):
        """Guarda en memoria el `transaction_id` asociado a un conector."""
        self.transactions[connector_id] = {
            "transaction_id": transaction_id,
            "start_time": datetime.utcnow()
        }
        logger.debug(f"[{self.id}] Stored TxID {transaction_id} for connector {connector_id}")

    def get_transaction_id(self, connector_id: int) -> int | None:
        """Obtiene el `transaction_id` para un conector, si existe."""
        entry = self.transactions.get(connector_id)
        return entry["transaction_id"] if entry else None

    def clear_transaction_id(self, connector_id: int):
        """Elimina el `transaction_id` asociado a un conector."""
        if connector_id in self.transactions:
            logger.debug(f"[{self.id}] Clearing TxID for connector {connector_id}")
            self.transactions.pop(connector_id)

    def _get_connector_by_transaction(self, transaction_id: int) -> int | None:
        """Busca el número de conector por un `transaction_id` conocido."""
        for conn_id, entry in self.transactions.items():
            if entry["transaction_id"] == transaction_id:
                return conn_id
        return None

    def _clear_transaction_id_by_transaction(self, transaction_id: int):
        """Limpia el mapping de un `transaction_id` dado, si existe."""
        conn_id = self._get_connector_by_transaction(transaction_id)
        if conn_id is not None:
            self.clear_transaction_id(conn_id)

    @on('BootNotification')
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        """Registra/asegura el Charger en BD y responde con aceptación."""
        logger.info(f"BootNotification from {charge_point_vendor} - {charge_point_model}")

        # normalizer…
        charger = crud.ensure_charger_exists(
            code=self.id,
            brand=charge_point_vendor,
            charger_model=charge_point_model,
            location=""
        )
        if not charger:
            logger.error(f"[{self.id}] No se pudo crear/recuperar Charger en BD.")
        self.db_charger_id = charger.id

        # Log con sesión explícita
        db = SessionLocal()
        try:
            crud.log_ocpp_message(
                db,
                charger_id=self.db_charger_id,
                connector_id=None,
                transaction_id=None,
                payload={
                    "vendor": charge_point_vendor,
                    "model":  charge_point_model,
                    "timestamp": self._now()
                },
                action="BootNotification"
            )
        except Exception as e:
            logger.error(f"Error guardando log BootNotification: {e}")
            db.rollback()
        finally:
            db.close()

        return call_result.BootNotificationPayload(
            current_time=self._now(),
            interval=10,
            status=RegistrationStatus.accepted
        )

    @on('Authorize')
    async def on_authorize(self, id_tag):
        """Autoriza un `idTag` usando el normalizador configurado y registra el evento."""
        logger.info(f"[{self.id}] Authorization request with tag: {id_tag}")
        if self.normalizer is None:
            from normalizers.base import GenericNormalizer
            self.normalizer = GenericNormalizer()
            logger.warning(f"[{self.id}] Normalizer not defined; using GenericNormalizer.")
        auth_result = self.normalizer.authorize(id_tag)

        db = SessionLocal()
        try:
            crud.log_ocpp_message(
                db,
                charger_id=self.db_charger_id,
                connector_id=None,
                transaction_id=None,
                payload={"id_tag": id_tag, "result": auth_result},
                action="Authorize"
            )
        finally:
            db.close()

        if auth_result["status"] == "Accepted":
            return call_result.AuthorizePayload(
                id_tag_info={"status": AuthorizationStatus.accepted}
            )
        else:
            return call_result.AuthorizePayload(
                id_tag_info={"status": AuthorizationStatus.invalid}
            )

    
    @after('SecurityEventNotification')
    async def on_security_event_notification(self, **kwargs):
        """Registra de forma laxa eventos de seguridad no validados (OCPP ext)."""
        logger.info(f"[{self.id}] SecurityEventNotification received (unvalidated): {kwargs}")
        return call_result.CallResult('SecurityEventNotification', {})

    @on('FirmwareStatusNotification')
    async def on_firmware_status(self, status, **kwargs):
        """Registra estados de firmware reportados por el cargador."""
        logger.info(f"[{self.id}] Firmware status: {status}")
        db = SessionLocal()
        try:
            crud.log_ocpp_message(
                db,
                charger_id=self.db_charger_id,
                connector_id=None,
                transaction_id=None,
                payload={"firmwareStatus": status, "details": kwargs},
                action="FirmwareStatusNotification"
            )
        finally:
            db.close()
        return call_result.FirmwareStatusNotificationPayload()
    
    @on('MeterValues')
    async def on_meter_values(self, connector_id, transaction_id, meter_value):
        """Procesa y persiste mediciones de energía (MeterValues)."""
        logger.info(f"[{self.id}] MeterValues received:")
        logger.debug(f"Raw meter_value payload: {meter_value}")
        
        # Si meter_value es un diccionario y tiene la clave "meterValue", la extraemos;
        # de lo contrario, usamos meter_value directamente.
        if isinstance(meter_value, dict) and "meterValue" in meter_value:
            meter_values_list = meter_value["meterValue"]
        else:
            meter_values_list = meter_value
    
        logger.debug(f"Extracted meter values: {meter_values_list}")
        
        # Llama a la función actualizada para MeterValues con la lista correcta.
        crud.log_ocpp_meter_values(
            charger_id=self.db_charger_id,
            connector_id=connector_id,
            transaction_id=transaction_id,
            meter_values=meter_values_list
        )
        
        return call_result.MeterValuesPayload()
        
    
    
    
    @on('GetLocalListVersion')
    async def on_get_local_list_version(self):
        """Responde con la versión de la lista local de autorizaciones."""
        logger.info(f"[{self.id}] GetLocalListVersion request received")
        crud.log_ocpp_message(
            charger_id=self.db_charger_id,
            connector_id=None,
            transaction_id=None,
            payload={"request": "GetLocalListVersion", "timestamp": self._now()},
            action="GetLocalListVersion"
        )
        return call_result.GetLocalListVersionPayload(list_version=1)

    @on('SendLocalList')
    async def on_send_local_list(self, list_version, local_authorization_list, update_type, **kwargs):
        """Recibe una lista local de autorizaciones (RFID) y la registra."""
        logger.info(f"[{self.id}] Received local authorization list (version {list_version}, type {update_type})")
        db = SessionLocal()
        try:
            crud.log_ocpp_message(
                db,
                charger_id=self.db_charger_id,
                connector_id=None,
                transaction_id=None,
                payload={
                    "listVersion": list_version,
                    "updateType": update_type,
                    "localList": local_authorization_list
                },
                action="SendLocalList"
            )
        finally:
            db.close()
        for entry in local_authorization_list:
            logger.info(f"  RFID: {entry['idTag']}")
        return call_result.SendLocalListPayload(status="Accepted")
    
    @on('Heartbeat')
    async def on_heartbeat(self):
        """Actualiza latido, asegura `db_charger_id` y registra `HeartbeatLog`."""
        logger.info(f"[{self.id}] Heartbeat received; db_charger_id: {self.db_charger_id}")
        # Si self.db_charger_id es None, se intenta recuperar el Charger usando el código self.id.
        if self.db_charger_id is None:
            charger = crud.ensure_charger_exists(code=self.id)
            if charger:
                self.db_charger_id = charger.id
                logger.info(f"[{self.id}] Retrieved Charger from DB with id {self.db_charger_id} in Heartbeat.")
            else:
                logger.error(f"[{self.id}] Unable to retrieve Charger in Heartbeat.")

        self.last_heartbeat = datetime.utcnow()

        # Registra el Heartbeat en la tabla heartbeat_logs
        # Puedes extraer reported_time del payload si es relevante (aquí se deja como None)
        crud.log_heartbeat(
            charger_id=self.db_charger_id,
            connector_id=None,
            reported_time=None,
            payload={}
        )

        return call_result.HeartbeatPayload(current_time=self._now())
    
    @on('StartTransaction')
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        """Crea transacción real en BD y la marca como activa en memoria."""
        logger.info(f"[{self.id}] StartTransaction received for id_tag: {id_tag}")

        # Cerramos cualquier placeholder antiguo
        old_tx = self.get_transaction_id(connector_id)
        if old_tx is not None:
            try:
                crud.stop_charge_transaction(
                    transaction_id=old_tx,
                    meter_stop=meter_start,
                    timestamp=timestamp
                )
                logger.debug(f"[{self.id}] Closed placeholder TxID {old_tx} for connector {connector_id}")
            except Exception as e:
                logger.error(f"[{self.id}] Error closing placeholder transaction {old_tx}: {e}")
            finally:
                self.clear_transaction_id(connector_id)

        # Asegurar conector en BD
        connector_record = crud.ensure_connector_exists(
            charger_id=self.db_charger_id,
            connector_number=connector_id
        )
        validated_connector_id = connector_record.id if connector_record else None

        # Crear la transacción real
        transaction_id = crud.create_charge_transaction(
            charger_id=self.db_charger_id,
            connector_id=validated_connector_id,
            id_tag=id_tag,
            meter_start=meter_start,
            timestamp=timestamp
        )
        if transaction_id is None:
            raise RuntimeError("Failed to create charge transaction")

        # Guardamos la tx en memoria **y** como activa
        self.store_transaction_id(connector_id, transaction_id)
        self.active_transaction = transaction_id
        self.pending_remote_start = False

        return call_result.StartTransactionPayload(
            transaction_id=transaction_id,
            id_tag_info={"status": AuthorizationStatus.accepted}
        )


    @on('StatusNotification')
    async def on_status_notification(self, connector_id, error_code, status, **kwargs):
        """Registra cambio de estado del conector y crea placeholder si aplica."""
        logger.info(f"[{self.id}] StatusNotification: connector {connector_id}, status: {status}")

        # Solo registramos si ya tenemos db_charger_id
        if self.db_charger_id is None:
            charger = crud.ensure_charger_exists(code=self.id)
            if charger:
                self.db_charger_id = charger.id

        # Ignorar canal 0
        if connector_id == 0:
            return call_result.StatusNotificationPayload()

        # Log en BD
        db = SessionLocal()
        try:
            crud.log_ocpp_message(
                db,
                charger_id=self.db_charger_id,
                connector_id=connector_id,
                transaction_id=None,
                payload={"errorCode": error_code, "status": status, "info": kwargs.get("info")},
                action="StatusNotification"
            )
        finally:
            db.close()

        # Si entra en Charging **y** no era un arranque remoto pendiente, creamos placeholder
        if status == 'Charging' \
           and self.get_transaction_id(connector_id) is None \
           and not self.pending_remote_start:
            ts_now = datetime.utcnow().isoformat()
            placeholder_tx = crud.create_charge_transaction(
                charger_id=self.db_charger_id,
                connector_id=connector_id,
                id_tag=None,
                meter_start=0,
                timestamp=ts_now
            )
            if placeholder_tx is not None:
                self.store_transaction_id(connector_id, placeholder_tx)
                logger.debug(f"[{self.id}] Auto-creada placeholder TxID {placeholder_tx} para connector {connector_id}")
            else:
                logger.error(f"[{self.id}] No se pudo crear placeholder Tx para connector {connector_id}")

        # Actualizamos el estado del conector en BD
        db2 = SessionLocal()
        try:
            conn = db2.query(Connector).filter_by(
                charger_id=self.db_charger_id,
                connector_number=connector_id
            ).first()
            if conn:
                conn.status = status
                conn.error_code = error_code
                conn.updated_at = datetime.utcnow()
                db2.commit()
        finally:
            db2.close()

        return call_result.StatusNotificationPayload()


    @on('RemoteStopTransaction')
    async def on_remote_stop_transaction(self, transaction_id):
        """Solicita al cargador detener la transacción activa indicada."""
        logger.info(f"[{self.id}] RemoteStopTransaction request for transaction {transaction_id}")

        # Solo aceptamos parar **si** coincide con la tx activa
        if self.active_transaction != transaction_id:
            logger.warning(f"[{self.id}] Remote stop rechazado: no coincide con active_transaction ({self.active_transaction})")
            return call_result.RemoteStopTransactionPayload(status="Rejected")

        self.pending_remote_stop = True

        db = SessionLocal()
        try:
            crud.log_ocpp_message(
                db,
                charger_id=self.db_charger_id,
                connector_id=self._get_connector_by_transaction(transaction_id),
                transaction_id=transaction_id,
                payload={"remote": True},
                action="RemoteStopTransaction"
            )
        finally:
            db.close()

        return call_result.RemoteStopTransactionPayload(status="Accepted")


    @on('StopTransaction')
    async def on_stop_transaction(self, meter_stop, timestamp, transaction_id, **kwargs):
        """Cierra la transacción en BD y limpia estado en memoria."""
        logger.info(f"[{self.id}] StopTransaction received for transaction {transaction_id}")

        # Si no es la tx activa, lo registramos pero no tocamos active_transaction
        if transaction_id != self.active_transaction:
            logger.warning(f"[{self.id}] StopTransaction de tx distinta a active_transaction ({self.active_transaction})")
        else:
            # Limpiamos la tx activa
            self.active_transaction = None
            self.clear_transaction_id(self._get_connector_by_transaction(transaction_id))
            self.pending_remote_stop = False

        # Log y cierre en BD
        db = SessionLocal()
        try:
            conn_id = self._get_connector_by_transaction(transaction_id)
            crud.log_ocpp_message(
                db,
                charger_id=self.db_charger_id,
                connector_id=conn_id,
                transaction_id=transaction_id,
                payload={"meter_stop": meter_stop, "timestamp": timestamp},
                action="StopTransaction"
            )
            crud.stop_charge_transaction(
                transaction_id=transaction_id,
                meter_stop=meter_stop,
                timestamp=timestamp
            )
        finally:
            db.close()

        return call_result.StopTransactionPayload()