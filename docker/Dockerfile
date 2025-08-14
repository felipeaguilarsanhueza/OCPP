# syntax=docker/dockerfile:1

FROM python:3.11-slim

WORKDIR /app

# Dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código fuente
COPY . .

# Exponer puerto esperado por Railway
ENV PORT=8000
EXPOSE 8000

# Arranque del servidor (REST + WebSocket)
CMD ["python", "main.py"]

