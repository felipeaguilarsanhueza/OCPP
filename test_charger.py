import asyncio
import json
import os
import uuid
import argparse
import websockets
from datetime import datetime


def generate_default_cpid() -> str:
    return f"TEST-{uuid.uuid4().hex[:8].upper()}"


def parse_args():
    parser = argparse.ArgumentParser(description="Simulador simple de cargador OCPP 1.6")
    parser.add_argument("--url", dest="server_url", default=os.getenv("OCPP_WS_URL", "wss://ocpp-ws-production.up.railway.app/ocpp"), help="URL base del WS OCPP (sin CPID). Ej: wss://dominio/ocpp")
    parser.add_argument("--cpid", dest="cpid", default=os.getenv("CPID", generate_default_cpid()), help="Charge Point ID a usar")
    parser.add_argument("--timeout", dest="timeout", type=int, default=int(os.getenv("OCPP_TIMEOUT", "20")), help="Timeout de conexión en segundos")
    return parser.parse_args()


async def ocpp_connect(server_url: str, cpid: str, timeout: int) -> None:
    # Normaliza URL y construye destino final: <server_url>/<cpid>
    uri = f"{server_url.rstrip('/')}/{cpid}"
    print(f"🔌 Conectando a: {uri}")
    try:
        async with websockets.connect(uri, subprotocols=["ocpp1.6"], open_timeout=timeout, ping_interval=30, ping_timeout=10) as ws:
            print(f"✅ Conectado: {uri}")

            # 1) BootNotification
            boot = [
                2,                     # CALL
                "1",                   # MessageId
                "BootNotification",    # Acción
                {
                    "chargePointVendor": "Demo",
                    "chargePointModel": "DemoModel",
                    "chargePointSerialNumber": cpid,
                    "firmwareVersion": "1.0.0"
                },
            ]
            await ws.send(json.dumps(boot))
            print("📤 BootNotification enviado")

            # Respuesta del servidor
            reply = await ws.recv()
            print("📥 Respuesta:", reply)

            # 2) Heartbeat (opcional)
            heartbeat = [2, "2", "Heartbeat", {}]
            await ws.send(json.dumps(heartbeat))
            print("💓 Heartbeat enviado")
            print("📥 Respuesta:", await ws.recv())

            # 3) StatusNotification (opcional)
            status = [
                2, "3", "StatusNotification",
                {
                    "connectorId": 1,
            "errorCode": "NoError",
                    "status": "Available",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
            ]
            await ws.send(json.dumps(status))
            print("📊 StatusNotification enviado")
            print("📥 Respuesta:", await ws.recv())
    except Exception as exc:
        print(f"❌ Error conectando a {uri}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(ocpp_connect(args.server_url, args.cpid, args.timeout))
