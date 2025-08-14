"""
Simulador de cargador OCPP para probar la conexión al servidor.
"""
import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCPPChargerSimulator:
    def __init__(self, charge_point_id, server_url):
        self.charge_point_id = charge_point_id
        self.server_url = server_url
        self.websocket = None
        self.message_id = 1
        
    async def connect(self):
        """Conecta al servidor OCPP."""
        try:
            # Construir la URL completa con el charge_point_id
            full_url = f"{self.server_url}/{self.charge_point_id}"
            logger.info(f"Intentando conectar a: {full_url}")
            
            self.websocket = await websockets.connect(
                full_url,
                subprotocols=["ocpp1.6"],
                ping_interval=30,
                ping_timeout=10
            )
            logger.info(f"✅ Conectado exitosamente al servidor OCPP")
            return True
        except websockets.exceptions.InvalidURI as e:
            logger.error(f"❌ URL inválida: {e}")
            return False
        except websockets.exceptions.InvalidHandshake as e:
            logger.error(f"❌ Error en handshake WebSocket: {e}")
            return False
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"❌ Conexión cerrada: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error al conectar: {e}")
            logger.error(f"   Tipo de error: {type(e).__name__}")
            return False
    
    def create_message(self, action, payload):
        """Crea un mensaje OCPP."""
        message = [
            2,  # MessageTypeId = CALL
            str(self.message_id),
            action,
            payload
        ]
        self.message_id += 1
        return json.dumps(message)
    
    async def send_boot_notification(self):
        """Envía BootNotification."""
        payload = {
            "chargePointVendor": "ABB",
            "chargePointModel": "Terra 184",
            "chargePointSerialNumber": self.charge_point_id,
            "chargeBoxSerialNumber": self.charge_point_id,
            "firmwareVersion": "1.0.0",
            "iccid": "123456789",
            "imsi": "987654321",
            "meterType": "ABB Meter",
            "meterSerialNumber": "METER123"
        }
        
        message = self.create_message("BootNotification", payload)
        await self.websocket.send(message)
        logger.info(f"📤 BootNotification enviado: {payload['chargePointModel']}")
    
    async def send_heartbeat(self):
        """Envía Heartbeat."""
        payload = {}
        message = self.create_message("Heartbeat", payload)
        await self.websocket.send(message)
        logger.info("💓 Heartbeat enviado")
    
    async def send_status_notification(self, connector_id=1, status="Available"):
        """Envía StatusNotification."""
        payload = {
            "connectorId": connector_id,
            "errorCode": "NoError",
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        message = self.create_message("StatusNotification", payload)
        await self.websocket.send(message)
        logger.info(f"📊 StatusNotification enviado: {status}")
    
    async def handle_messages(self):
        """Maneja mensajes entrantes del servidor."""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                message_type = data[0]
                
                if message_type == 2:  # CALL
                    # Mensaje del servidor (Authorize, StartTransaction, etc.)
                    message_id = data[1]
                    action = data[2]
                    payload = data[3]
                    
                    logger.info(f"📥 Mensaje recibido: {action}")
                    
                    # Responder según el tipo de mensaje
                    if action == "Authorize":
                        response = [3, message_id, {"idTagInfo": {"status": "Accepted"}}]
                        await self.websocket.send(json.dumps(response))
                        logger.info("✅ Authorize respondido: Accepted")
                    
                    elif action == "StartTransaction":
                        response = [3, message_id, {
                            "transactionId": 12345,
                            "idTagInfo": {"status": "Accepted"}
                        }]
                        await self.websocket.send(json.dumps(response))
                        logger.info("✅ StartTransaction respondido")
                    
                    elif action == "StopTransaction":
                        response = [3, message_id, {"idTagInfo": {"status": "Accepted"}}]
                        await self.websocket.send(json.dumps(response))
                        logger.info("✅ StopTransaction respondido")
                
                elif message_type == 3:  # CALLRESULT
                    # Respuesta a nuestro mensaje
                    message_id = data[1]
                    payload = data[2]
                    logger.info(f"📥 Respuesta recibida para mensaje {message_id}: {payload}")
                
                elif message_type == 4:  # CALLERROR
                    # Error en nuestro mensaje
                    message_id = data[1]
                    error_code = data[2]
                    error_description = data[3]
                    logger.error(f"❌ Error en mensaje {message_id}: {error_code} - {error_description}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 Conexión cerrada por el servidor")
        except Exception as e:
            logger.error(f"❌ Error al manejar mensajes: {e}")
    
    async def run(self):
        """Ejecuta el simulador."""
        if not await self.connect():
            return
        
        # Enviar BootNotification al conectar
        await self.send_boot_notification()
        
        # Enviar StatusNotification inicial
        await self.send_status_notification()
        
        # Iniciar heartbeat cada 30 segundos
        async def heartbeat_loop():
            while True:
                await asyncio.sleep(30)
                try:
                    await self.send_heartbeat()
                except:
                    break
        
        # Ejecutar heartbeat en background
        heartbeat_task = asyncio.create_task(heartbeat_loop())
        
        # Manejar mensajes del servidor
        try:
            await self.handle_messages()
        finally:
            heartbeat_task.cancel()
            if self.websocket:
                await self.websocket.close()

async def main():
    """Función principal para probar la conexión."""
    # Configuración
    charge_point_id = "TACW745321T2412"  # Tu cargador
    
    # IMPORTANTE: Railway maneja la redirección internamente
    # No especificar puerto - Railway redirige automáticamente
    server_url = "wss://ocpp-ws-production.up.railway.app"
    
    print("🔌 Simulador de Cargador OCPP")
    print(f"📍 Servidor: {server_url}")
    print(f"🆔 Charge Point ID: {charge_point_id}")
    print("=" * 50)
    
    simulator = OCPPChargerSimulator(charge_point_id, server_url)
    
    try:
        await simulator.run()
    except KeyboardInterrupt:
        logger.info("🛑 Simulador detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error en el simulador: {e}")

if __name__ == "__main__":
    asyncio.run(main())