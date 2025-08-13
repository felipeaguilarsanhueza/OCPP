"""
Rutas de pagos (placeholders para integración futura, p.ej. MercadoPago).
"""
from fastapi import APIRouter, HTTPException, Depends
from core.auth import get_current_user

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.post("/create_intent", dependencies=[Depends(get_current_user)])
async def create_payment_intent():
    """Crea un intento de pago (no implementado)."""
    # Lógica de pagos con MercadoPago pendiente de implementar
    raise HTTPException(
        status_code=501,
        detail="Integración con MercadoPago aún no implementada"
    )

@router.get("/status/{payment_id}", dependencies=[Depends(get_current_user)])
async def payment_status(payment_id: str):
    """Consulta el estado de un pago por su ID (no implementado)."""
    raise HTTPException(
        status_code=501,
        detail="Integración con MercadoPago aún no implementada"
    )

@router.get("/history", dependencies=[Depends(get_current_user)])
async def payment_history():
    """Lista el historial de pagos del usuario (no implementado)."""
    raise HTTPException(
        status_code=501,
        detail="Integración con MercadoPago aún no implementada"
    )