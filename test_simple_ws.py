"""
Test simple de WebSocket para verificar si Railway soporta WebSocket.
"""
import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_simple_websocket():
    """Prueba una conexión WebSocket simple sin subprotocolo."""
    url = "wss://ocpp-ws-production.up.railway.app"
    
    logger.info(f"🔍 Probando conexión simple a: {url}")
    
    try:
        # Intentar conexión sin subprotocolo
        websocket = await websockets.connect(url, timeout=10)
        logger.info("✅ Conexión WebSocket simple exitosa")
        await websocket.close()
        return True
    except Exception as e:
        logger.error(f"❌ Conexión simple falló: {e}")
        return False

async def test_http_upgrade():
    """Prueba si el servidor responde a upgrade de WebSocket."""
    import socket
    import ssl
    
    host = "ocpp-ws-production.up.railway.app"
    port = 443
    
    logger.info(f"🔍 Probando upgrade HTTP a WebSocket en {host}:{port}")
    
    try:
        # Crear conexión SSL
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                # Enviar request de upgrade WebSocket
                upgrade_request = (
                    f"GET / HTTP/1.1\r\n"
                    f"Host: {host}\r\n"
                    f"Upgrade: websocket\r\n"
                    f"Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                    f"Sec-WebSocket-Version: 13\r\n"
                    f"\r\n"
                )
                
                ssock.send(upgrade_request.encode())
                
                # Leer respuesta
                response = ssock.recv(1024).decode()
                logger.info(f"📥 Respuesta del servidor:")
                logger.info(response)
                
                if "101 Switching Protocols" in response:
                    logger.info("✅ Servidor soporta WebSocket")
                    return True
                else:
                    logger.error("❌ Servidor no soporta WebSocket")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Error en test HTTP upgrade: {e}")
        return False

async def main():
    """Función principal de test."""
    print("🔍 Test de Soporte WebSocket en Railway")
    print("=" * 50)
    
    # Test 1: Conexión WebSocket simple
    print("\n1️⃣ Test WebSocket simple...")
    await test_simple_websocket()
    
    # Test 2: HTTP Upgrade
    print("\n2️⃣ Test HTTP Upgrade...")
    await test_http_upgrade()
    
    print("\n🏁 Test completado")

if __name__ == "__main__":
    asyncio.run(main())
