# picaro-mapa — mapa publico del tenant Proyecto PiCARO (mismo patron que picaro-campo).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY picaro_mapa ./picaro_mapa

RUN mkdir -p /data && useradd -r -u 10002 mapa && chown -R mapa:mapa /data /app
USER mapa
VOLUME ["/data"]

# Puerto INTERNO: Caddy lo alcanza por la red `picaro`; no se publica al host.
EXPOSE 8000

# Un solo worker: catalogo y clientes SSE viven en memoria del proceso.
CMD ["uvicorn", "picaro_mapa.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
