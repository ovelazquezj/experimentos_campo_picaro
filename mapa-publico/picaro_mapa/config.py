"""Configuracion de picaro-mapa, toda por variables de entorno (ver .env.example)."""
import os
from dataclasses import dataclass


def _req(nombre: str) -> str:
    v = os.environ.get(nombre)
    if not v:
        raise RuntimeError(f"falta la variable de entorno {nombre}")
    return v


@dataclass(frozen=True)
class Config:
    # MQTT interno del stack (listener 1883, solo red Docker). Usuario de SOLO LECTURA.
    mqtt_host: str
    mqtt_port: int
    mqtt_user: str
    mqtt_pass: str
    # Postgres de ChirpStack con un rol de SOLO LECTURA por columnas (ver README).
    pg_dsn: str
    # Solo se publican eventos de este tenant.
    tenant_id: str
    # Clave para derivar los IDs publicos opacos (nunca se expone un DevEUI ni un EUI de gateway).
    id_secret: str
    # Ubicacion por defecto: ITPA (Pabellon de Arteaga).
    itpa_lat: float
    itpa_lon: float
    historial_dias: int
    catalogo_seg: int
    db_path: str


def cargar() -> Config:
    return Config(
        mqtt_host=os.environ.get("MQTT_HOST", "mosquitto"),
        mqtt_port=int(os.environ.get("MQTT_PORT", "1883")),
        mqtt_user=_req("MQTT_USER"),
        mqtt_pass=_req("MQTT_PASS"),
        pg_dsn=_req("PG_DSN"),
        tenant_id=_req("TENANT_ID"),
        id_secret=_req("ID_SECRET"),
        itpa_lat=float(os.environ.get("ITPA_LAT", "22.161428")),
        itpa_lon=float(os.environ.get("ITPA_LON", "-102.269043")),
        historial_dias=int(os.environ.get("HISTORIAL_DIAS", "7")),
        catalogo_seg=int(os.environ.get("CATALOGO_SEG", "60")),
        db_path=os.environ.get("DB_PATH", "/data/mapa.db"),
    )
