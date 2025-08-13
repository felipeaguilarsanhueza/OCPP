"""
Middleware de limitación de tasa (rate limit) simple.

Actualmente deja pasar todas las peticiones y permite `OPTIONS` para CORS.
Aquí puedes añadir tu lógica de rate limiting por IP/usuario/endpoints.
"""
# api/middleware/rate_limit.py
from starlette.requests import Request

async def limiter_middleware(request: Request, call_next):
    """Permite OPTIONS y delega en `call_next` para el resto de métodos."""
    # 1) Permite OPTIONS siempre pasar → CORS los adornará
    if request.method.upper() == "OPTIONS":
        return await call_next(request)

    # 2) (Opcional) tu lógica de limitación aquí
    # if too_many_requests:
    #     from starlette.responses import JSONResponse
    #     return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

    # 3) Para GET/POST normales, sigue el flujo
    return await call_next(request)
