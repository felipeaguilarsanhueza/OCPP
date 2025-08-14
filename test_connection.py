"""
Script de diagnóstico para probar la conectividad al servidor OCPP en Railway.
- Verifica conectividad TCP/SSL.
- Intenta el handshake WebSocket con subprotocolo OCPP 1.6.
- Si hay timeout en /ocpp/{id}, reintenta en /{id}.
"""

import os
import ssl
import socket
import argparse
import asyncio
import logging
import traceback

import websockets
from websockets.exceptions import InvalidStatusCode, InvalidHandshake

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("ocpp_diag")


async def test_domain_connectivity(domain: str, port: int = 443) -> bool:
    logger.info(f"🔍 Probando conectividad a {domain}:{port}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((domain, port))
        sock.close()
        if result == 0:
            logger.info(f"✅ Conectividad exitosa a {domain}:{port}")
            return True
        logger.error(f"❌ No se puede conectar a {domain}:{port} (connect_ex={result})")
        return False
    except Exception as e:
        logger.error(f"❌ Error probando {domain}:{port}: {e!r}")
        return False


async def test_ssl_connection(domain: str, port: int = 443) -> bool:
    logger.info(f"🔍 Probando SSL a {domain}:{port}")
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                logger.info(f"✅ SSL exitoso a {domain}:{port}")
                logger.info(f"   Sujeto: {cert.get('subject')}")
                logger.info(f"   Emisor: {cert.get('issuer')}")
                logger.info(f"   Válido desde: {cert.get('notBefore')}, hasta: {cert.get('notAfter')}")
                return True
    except Exception as e:
        logger.error(f"❌ Error SSL a {domain}:{port}: {e!r}")
        return False


async def test_websocket_connection(base_url: str, charge_point_id: str, use_subprotocol: bool = True) -> bool:
    """
    base_url: "wss://dominio/ocpp" o "wss://dominio"
    """
    base_url = base_url.rstrip("/")
    full_url = f"{base_url}/{charge_point_id}"
    logger.info(f"🔍 Probando WS: {full_url}")

    kwargs = dict(
        ping_interval=30,
        ping_timeout=10,
        close_timeout=5,
        open_timeout=15,  # subimos a 15s para evitar falsos timeouts
    )
    if use_subprotocol:
        kwargs["subprotocols"] = ["ocpp1.6"]

    try:
        async with websockets.connect(full_url, **kwargs) as ws:
            proto = getattr(ws, "subprotocol", None)
            logger.info(f"✅ Conexión WS exitosa a {full_url} (subprotocolo negociado: {proto})")
            return True

    except InvalidStatusCode as e:
        logger.error(f"❌ HTTP {e.status_code} en handshake hacia {full_url}")
        hdrs = getattr(e, "headers", None)
        if hdrs:
            logger.error(f"   Headers: {dict(hdrs)}")
        return False

    except InvalidHandshake as e:
        logger.error(f"❌ Handshake inválido: {e!r}")
        logger.error(traceback.format_exc())
        return False

    except asyncio.TimeoutError:
        logger.error("⏳ Timeout esperando respuesta de handshake (open_timeout agotado)")
        return False

    except Exception as e:
        logger.error(f"❌ Error WS no controlado: {e!r}")
        logger.error(traceback.format_exc())
        return False


async def main():
    parser = argparse.ArgumentParser(description="Diagnóstico de conectividad OCPP en Railway")
    parser.add_argument("--domain", default=os.getenv("OCPP_DOMAIN", "ocpp-ws-production.up.railway.app"),
                        help="Dominio del servicio (sin esquema)")
    parser.add_argument("--cpid", default=os.getenv("OCPP_CPID", "TACW745321T2412"),
                        help="Charge Point ID para la ruta")
    parser.add_argument("--prefer-root", action="store_true",
                        help="Probar primero la raíz '/{id}' en lugar de '/ocpp/{id}'")

    args = parser.parse_args()
    domain = args.domain
    charge_point_id = args.cpid

    print("🔍 Diagnóstico de Conectividad OCPP")
    print("=" * 50)

    # 1) Conectividad básica
    print("\n1️⃣ Probando conectividad básica...")
    await test_domain_connectivity(domain, 443)
    await test_domain_connectivity(domain, 80)

    # 2) SSL
    print("\n2️⃣ Probando SSL...")
    await test_ssl_connection(domain, 443)

    # 3) WebSocket WSS con subprotocolo
    print("\n3️⃣ Probando WebSocket WSS con subprotocolo...")

    primary_base = f"wss://{domain}"           # raíz
    secondary_base = f"wss://{domain}/ocpp"    # /ocpp

    if not args.prefer_root:
        primary_base, secondary_base = secondary_base, primary_base

    ok = await test_websocket_connection(primary_base, charge_point_id, use_subprotocol=True)
    if not ok:
        logger.info("↩️ Reintentando en la ruta alternativa...")
        await test_websocket_connection(secondary_base, charge_point_id, use_subprotocol=True)

    # 4) WS claro (no TLS) – normalmente falla en Railway
    print("\n4️⃣ Probando WebSocket WS (no-TLS, debería fallar en Railway)...")
    ws_base = primary_base.replace("wss://", "ws://")
    await test_websocket_connection(ws_base, charge_point_id, use_subprotocol=True)

    # 5) WSS sin subprotocolo
    print("\n5️⃣ Probando WSS sin subprotocolo OCPP (debería fallar si el server lo exige)...")
    await test_websocket_connection(primary_base, charge_point_id, use_subprotocol=False)

    print("\n🏁 Diagnóstico completado")


if __name__ == "__main__":
    asyncio.run(main())
