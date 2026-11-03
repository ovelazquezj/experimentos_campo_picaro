# Microservicio de campo PiCARO — imagen minima sobre Python 3.11 slim.
#
# Se instala solo el paquete `picaro_campo` y sus dependencias de runtime; los
# tests no van dentro de la imagen. El proceso corre como usuario sin privilegios
# y el estado persistente vive en /data (volumen), no en la capa de la imagen.
FROM python:3.11-slim

# No escribir .pyc y salida sin buffer (logs inmediatos en `docker logs`).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero las dependencias (capa cacheable): si no cambia requirements.txt, no se
# reinstala en cada build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo de la app.
COPY picaro_campo ./picaro_campo

# Volumen para la SQLite (DB_PATH=/data/campo.db por defecto).
RUN mkdir -p /data && useradd -r -u 10001 picaro && chown -R picaro:picaro /data /app
USER picaro
VOLUME ["/data"]

# Puerto INTERNO (no se publica al host; Caddy lo alcanza por la red `picaro`).
EXPOSE 8000

# Modo factoria (--factory): uvicorn llama a create_app() en el arranque, cuando
# /data ya existe. Un solo worker: el estado de sesion y el hub de WebSocket viven
# en memoria del proceso; con varios workers cada uno tendria su propia copia.
CMD ["uvicorn", "picaro_campo.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
