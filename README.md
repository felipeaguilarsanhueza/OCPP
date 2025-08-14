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
2. Configura las variables de entorno necesarias (Railway inyecta `PORT` automáticamente):
   - `DATABASE_URL` (conecta a Postgres de Railway)
   - `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `ADMIN_MASTER_KEY`, `ADMIN_TOKEN_EXPIRE_DAYS`
3. Railway detectará el `Dockerfile` y construirá la imagen. El servicio se inicia con `python main.py`.
4. La API REST y el WebSocket OCPP comparten el mismo puerto `$PORT` en un único servicio.


