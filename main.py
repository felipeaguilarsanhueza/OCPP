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
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
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
    # Importante: aceptar anunciando el subprotocolo OCPP
    # El cliente debe enviar Sec-WebSocket-Protocol: ocpp1.6
    await websocket.accept(subprotocol="ocpp1.6")
    adapter = FastAPIWebSocketAdapter(websocket)
    cp = ChargePoint(cp_id, adapter)   # ChargePoint debe trabajar con .send/.recv/.close
    manager.add(cp_id, cp)
    logger.info(f"OCPP conectado: {cp_id}")
    try:
        await cp.start()  # tu loop OCPP
    except WebSocketDisconnect:
        logger.info(f"OCPP desconectado: {cp_id}")
    finally:
        manager.remove(cp_id)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))  # Railway inyecta $PORT
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
