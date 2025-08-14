# main.py
"""
Servidor OCPP con FastAPI:
- API REST y WebSocket OCPP 1.6 en el MISMO puerto ($PORT).
- Requiere que el cliente establezca Sec-WebSocket-Protocol: ocpp1.6
"""

import os
import logging
import uvicorn
import ocpp.messages
ocpp.messages._skip_schema_validation = True

from database.db import engine
from database.models import Base

# ---- Logging & DB
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main")
Base.metadata.create_all(bind=engine)

# =========================
# FastAPI (REST + WebSocket)
# =========================
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.rate_limit import limiter_middleware
from api.routes.auth       import router as auth_router
from api.routes.users      import router as users_router
from api.routes.payments   import router as payments_router
from api.routes.charging   import router as charging_router
from api.routes.admin      import router as admin_router
from api.routes.facilities import router as facilities_router
from api.routes.connectors import router as connectors_router

from core.auth               import get_current_user
from core.ocpp_handler       import ChargePoint
from core.connection_manager import manager

app = FastAPI(title="OCPP Server API", version="1.0")

# --- ASGI wrapper para loguear scopes HTTP/WS antes de que los maneje FastAPI
class ASGILogWrapper:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        stype = scope.get("type")
        if stype in ("http", "websocket"):
            path = scope.get("path")
            client = scope.get("client")
            headers = {}
            for k, v in (scope.get("headers") or []):
                try:
                    kk = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
                    vv = v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
                    headers[kk.lower()] = vv
                except Exception:
                    continue
            if stype == "websocket":
                logger.info(
                    f"[ASGI] WS scope path={path} client={client} upgrade={headers.get('upgrade')} "
                    f"subprotocol={headers.get('sec-websocket-protocol')}"
                )
            else:
                logger.info(
                    f"[ASGI] HTTP scope path={path} client={client} upgrade={headers.get('upgrade')} "
                    f"subprotocol={headers.get('sec-websocket-protocol')}"
                )
        return await self.app(scope, receive, send)

# preparar app ASGI con logger de scopes (no sustituye el objeto FastAPI)
asgi_app = ASGILogWrapper(app)

# 1) CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # en producción: restringe al dominio
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2) Rate-limit
app.middleware("http")(limiter_middleware)

# 3) Routers REST
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(facilities_router, prefix="/facilities", tags=["Facilities"])

jwt_dep = [Depends(get_current_user)]
app.include_router(users_router,      tags=["Users"],      dependencies=jwt_dep)
app.include_router(payments_router,   prefix="/payments", tags=["Payments"], dependencies=jwt_dep)
app.include_router(charging_router,   tags=["Charging"],   dependencies=jwt_dep)
app.include_router(admin_router,      prefix="/admin",    tags=["Admin"],    dependencies=jwt_dep)
app.include_router(connectors_router, tags=["Connectors"], dependencies=jwt_dep)

# Health
@app.get("/")
def root():
    return {"message": "API y WebSocket OCPP activos"}

# =========================
# WebSocket OCPP (ocpp1.6)
# =========================

class FastAPIWebSocketAdapter:
    """
    Adaptador mínimo para que ChargePoint funcione con fastapi.WebSocket.
    Debe proveer send/recv/close con semántica de texto.
    """
    def __init__(self, ws: WebSocket):
        self.ws = ws

    async def recv(self) -> str:
        return await self.ws.receive_text()

    async def send(self, message: str):
        await self.ws.send_text(message)

    async def close(self):
        await self.ws.close()

@app.websocket("/ocpp/{cp_id}")
async def ocpp_ws(websocket: WebSocket, cp_id: str):
    """Endpoint WebSocket OCPP 1.6 con logs detallados de intentos.

    - Rechaza si el cliente no ofrece el subprotocolo `ocpp1.6`.
    - Registra IP/puerto, headers relevantes y cp_id.
    """
    client = websocket.client or ("?", "?")
    headers_dict = {k.decode() if isinstance(k, (bytes, bytearray)) else k: (
        v.decode() if isinstance(v, (bytes, bytearray)) else v
    ) for k, v in websocket.headers.items()} if hasattr(websocket, "headers") else {}
    offered_protocols_raw = headers_dict.get("sec-websocket-protocol") or headers_dict.get("Sec-WebSocket-Protocol")
    offered = [p.strip().lower() for p in offered_protocols_raw.split(',')] if offered_protocols_raw else []

    logger.info(
        f"[WS Attempt] cp_id={cp_id} from={client} offered_protocols={offered} "
        f"ua={headers_dict.get('user-agent')}"
    )

    if "ocpp1.6" not in offered:
        logger.warning(f"[WS Reject] cp_id={cp_id} motivo=missing-subprotocol offered={offered}")
        # 1002 (protocol error) o 1003 (unsupported data). Elegimos 1002
        await websocket.close(code=1002)
        return

    # Aceptar negociando explícitamente ocpp1.6
    await websocket.accept(subprotocol="ocpp1.6")
    logger.info(f"[WS Accept] cp_id={cp_id} subprotocol=ocpp1.6 from={client}")

    adapter = FastAPIWebSocketAdapter(websocket)
    cp = ChargePoint(cp_id, adapter)
    manager.add(cp_id, cp)
    try:
        await cp.start()
    except WebSocketDisconnect:
        logger.info(f"[WS Close] cp_id={cp_id} disconnected by client")
    except Exception as exc:
        logger.exception(f"[WS Error] cp_id={cp_id} error={type(exc).__name__}: {exc}")
    finally:
        manager.remove(cp_id)

@app.get("/ocpp/{cp_id}")
async def ocpp_http_probe(cp_id: str, request: Request):
    """Ruta HTTP espejo para registrar intentos vía HTTP en lugar de WS.

    Útil para ver 499/40x en el proxy y confirmar que el cliente no está
    haciendo WebSocket upgrade. Devuelve 426 con detalles.
    """
    client = (request.client.host, request.client.port) if request.client else ("?", "?")
    ua = request.headers.get("user-agent")
    upgrade = request.headers.get("upgrade")
    ws_proto = request.headers.get("sec-websocket-protocol")
    logger.info(f"[HTTP Probe] cp_id={cp_id} from={client} upgrade={upgrade} subprotocol={ws_proto} ua={ua}")
    return {
        "detail": "Use WebSocket wss://<host>/ocpp/{cp_id} con subprotocolo ocpp1.6",
        "cp_id": cp_id,
        "client": client,
        "upgrade": upgrade,
        "offered_subprotocol": ws_proto,
        "hint": "Configure el cliente para enviar Sec-WebSocket-Protocol: ocpp1.6"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))  # Railway inyecta $PORT
    uvicorn.run(
        asgi_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
        ws="websockets",
    )
