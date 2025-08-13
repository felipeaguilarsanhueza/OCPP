OCPP Server
===========

Despliegue en Railway y uso local.

Ejecutar localmente
-------------------

1. Crear y activar entorno virtual (opcional)
2. Instalar dependencias: `pip install -r requirements.txt`
3. Variables de entorno requeridas (puedes copiar `.env.example` a `.env`):
   - `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
   - `ADMIN_MASTER_KEY`, `ADMIN_TOKEN_EXPIRE_DAYS`
   - `DATABASE_URL` (opcional; por defecto Postgres local)
4. Lanzar servidor local (REST + WS): `python main.py`

Despliegue en Railway
---------------------

1. Crea un proyecto en Railway y añade un servicio a partir de este repositorio.
2. Configura variables de entorno en Railway:
   - `RUN_MODE=rest` para servicio HTTP (FastAPI)
   - `PORT` (Railway lo inyecta automáticamente)
   - `DATABASE_URL` (conecta a Postgres de Railway)
   - `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `ADMIN_MASTER_KEY`, `ADMIN_TOKEN_EXPIRE_DAYS`
3. Establece el comando de inicio del servicio HTTP: `python -m uvicorn main:api_app --host 0.0.0.0 --port $PORT`
4. Para el servidor OCPP WS, crea otro servicio clonando este repo y usa:
   - `RUN_MODE=ws`
   - `PORT` (Railway)
   - Comando: `python main.py`

Nota: Puedes ejecutar ambos servicios en un único dyno en local, pero en Railway es recomendable separarlos en dos servicios.


