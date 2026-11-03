"""
conftest.py — Utillaje comun de los tests.

Regla de oro (contrato: "SIN red real"): aqui NO se conecta a ningun broker MQTT
ni a ChirpStack. Se inyecta:
  · un ChirpStack FALSO (FakeChirpStack) que registra las llamadas y puede
    simular caidas para probar el 503;
  · la app creada con start_mqtt=False (no arranca paho);
  · una SQLite en fichero temporal por test (aislamiento total).

El estado MQTT se fuerza a mano (manager.set_mqtt_connected(True)) porque sin
broker real nadie lo pondria; asi los tests de 'start' pueden avanzar y a la vez
se puede probar el 503 de "MQTT no conectado".
"""
import time

import pytest

from picaro_campo.config import Config
from picaro_campo.main import create_app
from picaro_campo.store import CampoStore

TOKEN = "test-token-123"


class FakeChirpStack:
    """Doble de ChirpStackClient. No hace red: registra llamadas y, si se le
    pide, lanza el error que la app traduce a 503.

    `enabled_class` controla lo que devuelve get_enabled_class() (gate de clase,
    D-60):
      · "auto" (defecto): la clase del ULTIMO perfil puesto — simula un device
        que hizo su JOIN con el perfil correcto, asi el gate pasa y los tests
        del flujo normal no cambian;
      · "A"/"B"/"C": clase efectiva FIJA — simula la congelacion del issue #360
        de ChirpStack (el PUT de perfil no la actualiza);
      · None: el servidor no expone classEnabled (ChirpStack viejo)."""

    _PROFILE_CLASS = {"terreno-a": "A", "terreno-c": "C", "ej09": "A",
                      "radiosonda-c": "C"}

    def __init__(self):
        self.profile_calls = []
        self.ping_calls = []
        # DevEUI de cada llamada, en orden (D-65: cada sesion es de una sonda).
        self.profile_euis = []
        self.class_euis = []
        self.ping_euis = []
        # Marcos (fPort 30) de la radiosonda.
        self.marco_calls = []
        self.marco_euis = []
        # Coordenadas de gateway que "tiene" ChirpStack (D-65); el resto, None.
        self.gateway_locations = {}
        self.gateway_calls = []
        self.fail = None            # si es una excepcion, se lanza en cada llamada
        self.enabled_class = "auto"

    def set_device_profile(self, profile_key, dev_eui=None):
        if self.fail:
            raise self.fail
        self.profile_calls.append(profile_key)
        self.profile_euis.append(dev_eui)
        return profile_key

    def get_enabled_class(self, dev_eui=None):
        if self.fail:
            raise self.fail
        self.class_euis.append(dev_eui)
        if self.enabled_class != "auto":
            return self.enabled_class
        profile = self.profile_calls[-1] if self.profile_calls else None
        return self._PROFILE_CLASS.get(profile)

    def get_gateway_location(self, gateway_id):
        if self.fail:
            raise self.fail
        self.gateway_calls.append(gateway_id)
        return self.gateway_locations.get(gateway_id)

    def enqueue_ping(self, seq, dev_eui=None):
        if self.fail:
            raise self.fail
        self.ping_calls.append(seq)
        self.ping_euis.append(dev_eui)
        return {"queued": True}

    def enqueue_marco(self, seq, dev_eui=None):
        if self.fail:
            raise self.fail
        self.marco_calls.append(seq)
        self.marco_euis.append(dev_eui)
        return {"queued": True}


def make_config(db_path, ping_interval_s=0.0):
    # GW en una posicion conocida (cerca del CERRO16 ficticio) para que la
    # distancia haversine de las metricas salga > 0 y se pueda comprobar.
    # El ping automatico va APAGADO por defecto (intervalo 0) para que los tests
    # que no lo prueban sean deterministas; el test del ciclo inyecta un
    # intervalo de milisegundos en vez de dormir 60 s.
    return Config(
        campo_token=TOKEN,
        mqtt_host="broker.invalido", mqtt_port=8883, mqtt_user="x",
        mqtt_password="y", mqtt_tls=False,
        chirpstack_api="http://chirpstack.invalido", chirpstack_token="z",
        app_id="app-test", dev_eui="0011223344550001",
        dev_eui_lora32="0011223344550003",
        # La radiosonda es la misma placa que la tbeam: mismo DevEUI.
        dev_eui_radiosonda="0011223344550001",
        db_path=str(db_path), gw_lat=19.4000, gw_lon=-99.1000,
        target_uplinks=300, ping_interval_s=ping_interval_s,
    )


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "campo.db"


@pytest.fixture
def chirp():
    return FakeChirpStack()


@pytest.fixture
def app(db_path, chirp):
    cfg = make_config(db_path)
    store = CampoStore(str(db_path))
    application = create_app(config=cfg, chirpstack=chirp, store=store,
                             start_mqtt=False)
    return application


@pytest.fixture
def client(app):
    # TestClient como context manager: dispara el lifespan (ata el event loop).
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        # Simula el MQTT conectado (sin broker real): permite arrancar sesiones.
        app.state.manager.set_mqtt_connected(True)
        yield c


def auth_headers(token=TOKEN):
    return {"Authorization": f"Bearer {token}"}


def make_uplink(f_cnt, f_port, *, rssi=-118, snr=-8.0, lat=19.40, lon=-99.30,
                gps_fix=1, sats=9, battery_v=3.71, battery_pct=None, ts=None):
    """Construye un registro plano de uplink (como el que produce
    parse_chirpstack_up), listo para manager.ingest_record()."""
    ts = ts if ts is not None else time.time()
    from datetime import datetime, timezone
    return {
        "ts": ts,
        "iso": datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds"),
        "dev_eui": "0011223344550001",
        "f_cnt": f_cnt, "f_port": f_port,
        "rssi": rssi, "snr": snr, "gateway_id": "gw-test",
        "freq": 903900000, "dr": 1,
        "gps_active": 1, "gps_fix": gps_fix,
        "latitude": lat, "longitude": lon, "altitude_m": 2240.0,
        "satellites": sats, "battery_v": battery_v, "battery_pct": battery_pct,
        "charging": 0, "usb_powered": 0,
        "temperature_c": 21.5, "pressure_hpa": 780.0,
        "raw_json": "{}",
    }
