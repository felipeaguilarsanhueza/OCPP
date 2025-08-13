# main.py

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from api.routes import auth, facilities, charging, users
from api.middleware.rate_limit import limiter_middleware
from core.auth import get_current_user

app = FastAPI(title="OCPP Server API", version="1.0")

# 1) CORS — siempre antes de todo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # en prod pon tu dominio
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2) Rate-limit
app.middleware("http")(limiter_middleware)

# 3) Auth (register, login, me…)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])

# 4) Facilities **públicas**:
#    SOLO los GET list y detail NO piden token.
app.include_router(
    facilities.router,
    prefix="/facilities",
    tags=["Facilities"],
    # <<< No dependencies aquí >>>
)

# 5) Rutas que sí piden JWT
jwt_dep = [Depends(get_current_user)]
app.include_router(charging.router, prefix="/charging", tags=["Charging"], dependencies=jwt_dep)
app.include_router(users.router,    prefix="/users",    tags=["Users"],    dependencies=jwt_dep)

@app.get("/")
def root():
    return {"message": "API OCPP Activa"}
