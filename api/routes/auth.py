"""
Rutas de autenticación (registro, login, perfil y emisión de token admin).

Prefijo aplicado en `main.py`: `/auth`.
"""
# api/routes/auth.py

from fastapi import APIRouter, HTTPException, Depends, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from core.auth import authenticate_user, create_access_token, get_current_user, get_db, create_admin_token
from api.schemas.auth import Token, UserCreate, UserOut
from database import crud

# No prefix here; it will be applied in main.py
router = APIRouter()

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Registra un nuevo usuario y devuelve sus datos (sin contraseña).
    """
    if crud.get_user_by_email(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = crud.create_user(
        db,
        email=user_in.email,
        password=user_in.password,
        username=user_in.username
    )
    return user

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Loguea al usuario y devuelve un JWT.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"}
        )
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    """
    Devuelve los datos del usuario autenticado.
    """
    return current_user

@router.post("/admin_token", summary="Genera un JWT de administrador")
def admin_token(master_key: str = Body(..., embed=True)):
    """
    Recibe { "master_key": "…" } y si coincide con ADMIN_MASTER_KEY
    devuelve un token con role=admin y expiración larga.
    """
    from core.auth import ADMIN_MASTER_KEY
    if master_key != ADMIN_MASTER_KEY:
        raise HTTPException(status_code=401, detail="Clave de administrador inválida")
    token = create_admin_token()
    return {"access_token": token, "token_type": "bearer"}