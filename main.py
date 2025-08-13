"""
Servidor principal de la aplicación OCPP.

Este módulo levanta dos servicios:
- API REST con FastAPI (puerto 8000) para autenticación, gestión y control remoto.
- Servidor WebSocket OCPP 1.6 (puerto 9000) para comunicarse con los cargadores.

También inicializa la base de datos, configuración de CORS y rate limiting.
"""
# main.py

import ocpp.messages
ocpp.messages._skip_schema_validation = True

import asyncio, logging, threading, os
import uvicorn, websockets, ocpp

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from database.db import engine
from database.models import Base
from core.ocpp_handler       import ChargePoint
from core.connection_manager import manager
from core.auth               import get_current_user
from api.middleware.rate_limit import limiter_middleware

# Routers
from api.routes.auth       import router as auth_router
from api.routes.users      import router as users_router
from api.routes.payments   import router as payments_router
from api.routes.charging   import router as charging_router
from api.routes.admin      import router as admin_router
from api.routes.facilities import router as facilities_router
from api.routes.connectors import router as connectors_router

# ---- Logging & DB
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main")
logging.getLogger("passlib.handlers.bcrypt").setLevel(logging.ERROR)

Base.metadata.create_all(bind=engine)

# ---- FastAPI
api_app = FastAPI(title="OCPP Server API", version="1.0")

# 1) CORS — antes de cualquier router
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # En prod pon tu dominio
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2) Rate-limit
api_app.middleware("http")(limiter_middleware)

# 3) Auth: register, login, me…
api_app.include_router(auth_router, prefix="/auth", tags=["Auth"])

# 4) Facilities **públicas**:
#    Los GET de list/detail NO piden token.
api_app.include_router(
    facilities_router,
    prefix="/facilities",
    tags=["Facilities"],
    # <<< no dependencies aquí >>>
)

# 5) Rutas protegidas (requieren JWT):
jwt_dep = [Depends(get_current_user)]
api_app.include_router(users_router,    tags=["Users"],    dependencies=jwt_dep)
api_app.include_router(payments_router, prefix="/payments", tags=["Payments"], dependencies=jwt_dep)
api_app.include_router(charging_router, tags=["Charging"], dependencies=jwt_dep)
api_app.include_router(admin_router,    prefix="/admin",    tags=["Admin"],    dependencies=jwt_dep)
api_app.include_router(connectors_router, tags=["Connectors"], dependencies=jwt_dep)

# Root
@api_app.get("/")
def root():
    """Punto de salud de la API REST."""
    return {"message": "API OCPP y WebSocket Activos"}

# WebSocket...
async def handle_connection(websocket, path):
    """
    Maneja una nueva conexión WebSocket OCPP.
    - Registra el `ChargePoint` en el `ConnectionManager`.
    - Inicia el bucle OCPP del cargador (`cp.start()`).
    - Al finalizar, elimina la conexión del manager.
    """
    cp_id = path.strip("/")
    cp = ChargePoint(cp_id, websocket)
    manager.add(cp_id, cp)
    logger.debug(f"[handle_connection] Conexión añadida: {cp_id}")
    try:
        await cp.start()
    finally:
        manager.remove(cp_id)
        logger.debug(f"[handle_connection] Conexión removida: {cp_id}")

async def start_websocket_server():
    """
    Inicia el servidor WebSocket OCPP y mantiene el proceso vivo.
    El puerto se toma de la variable de entorno `PORT` (Railway) o 9000 por defecto.
    """
    ws_port = int(os.getenv("PORT", "9000"))
    logger.info(f"WebSocket OCPP iniciado en ws://0.0.0.0:{ws_port}")
    async with websockets.serve(
        handle_connection, "0.0.0.0", ws_port, subprotocols=["ocpp1.6"]
    ):
        await asyncio.Future()

def start_rest_api():
    """Arranca la API REST de FastAPI en 0.0.0.0 usando el puerto de entorno."""
    rest_port = int(os.getenv("PORT", "8000"))
    uvicorn.run(api_app, host="0.0.0.0", port=rest_port, log_level="info")

if __name__ == "__main__":
    # Permite ejecutar solo REST o solo WS en entornos como Railway.
    run_mode = os.getenv("RUN_MODE", "both").lower()
    if run_mode == "rest":
        start_rest_api()
    elif run_mode == "ws":
        try:
            asyncio.run(start_websocket_server())
        except KeyboardInterrupt:
            logger.info("Servidor detenido")
    else:
        # Modo local: ambos servicios, REST en hilo y WS en principal
        threading.Thread(target=start_rest_api, daemon=True).start()
        try:
            asyncio.run(start_websocket_server())
        except KeyboardInterrupt:
            logger.info("Servidor detenido")