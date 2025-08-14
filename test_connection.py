"""
Script de diagnóstico para probar la conectividad al servidor OCPP.
"""
import asyncio
import websockets
import logging
import socket
import ssl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_connection(url, charge_point_id):
    """Prueba una conexión WebSocket específica."""
    full_url = f"{url}/{charge_point_id}"
    logger.info(f"🔍 Probando: {full_url}")
    
    try:
        websocket = await websockets.connect(
            full_url,
            subprotocols=["ocpp1.6"],
            ping_interval=30,
            ping_timeout=10
        )
        logger.info(f"✅ Conexión exitosa a {full_url}")
        await websocket.close()
        return True
    except Exception as e:
        logger.error(f"❌ Falló {full_url}: {e}")
        return False

async def test_domain_connectivity(domain, port=443):
    """Prueba conectividad básica al dominio."""
    logger.info(f"🔍 Probando conectividad a {domain}:{port}")
    
    try:
        # Crear socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        # Conectar
        result = sock.connect_ex((domain, port))
        sock.close()
        
        if result == 0:
            logger.info(f"✅ Conectividad exitosa a {domain}:{port}")
            return True
        else:
            logger.error(f"❌ No se puede conectar a {domain}:{port}")
            return False
    except Exception as e:
        logger.error(f"❌ Error probando {domain}:{port}: {e}")
        return False

async def test_ssl_connection(domain, port=443):
    """Prueba conexión SSL."""
    logger.info(f"🔍 Probando SSL a {domain}:{port}")
    
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                logger.info(f"✅ SSL exitoso a {domain}:{port}")
                logger.info(f"   Certificado: {ssock.getpeername()}")
                return True
    except Exception as e:
        logger.error(f"❌ Error SSL a {domain}:{port}: {e}")
        return False

async def main():
    """Función principal de diagnóstico."""
    domain = "ocpp-ws-production.up.railway.app"
    charge_point_id = "TACW745321T2412"
    
    print("🔍 Diagnóstico de Conectividad OCPP")
    print("=" * 50)
    
    # 1. Probar conectividad básica
    print("\n1️⃣ Probando conectividad básica...")
    await test_domain_connectivity(domain, 443)
    await test_domain_connectivity(domain, 80)
    
    # 2. Probar SSL
    print("\n2️⃣ Probando SSL...")
    await test_ssl_connection(domain, 443)
    
    # 3. Probar WebSocket WSS
    print("\n3️⃣ Probando WebSocket WSS...")
    await test_websocket_connection("wss://ocpp-ws-production.up.railway.app", charge_point_id)
    
    # 4. Probar WebSocket WS (debería fallar)
    print("\n4️⃣ Probando WebSocket WS (debería fallar)...")
    await test_websocket_connection("ws://ocpp-ws-production.up.railway.app", charge_point_id)
    
    # 5. Probar sin subprotocolo
    print("\n5️⃣ Probando sin subprotocolo OCPP...")
    try:
        full_url = f"wss://{domain}/{charge_point_id}"
        websocket = await websockets.connect(full_url, ping_interval=30, ping_timeout=10)
        logger.info(f"✅ Conexión sin subprotocolo exitosa")
        await websocket.close()
    except Exception as e:
        logger.error(f"❌ Conexión sin subprotocolo falló: {e}")
    
    print("\n🏁 Diagnóstico completado")

if __name__ == "__main__":
    asyncio.run(main())
