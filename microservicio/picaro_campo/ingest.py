"""
ingest.py — Ingesta de uplinks de ChirpStack por MQTT (paho-mqtt 2.x).

Reutiliza `parse_chirpstack_up` (el mismo mapeo de campos que dashboard/
mqtt_ingest.py) para no reinventar el formato del registro plano. El loop de paho
corre en su propio hilo; por cada uplink llama a `manager.ingest_record(rec)`,
que es sincrono y esta protegido por su propio lock. El estado de conexion se
refleja en el manager (mqtt_connected), que es lo que informa /health y lo que
exige `start` (§6: 503 si MQTT no responde).

POR QUE UNA COPIA DE parse_chirpstack_up Y NO UN IMPORT
-------------------------------------------------------
El microservicio se empaqueta en su propio contenedor (ver Dockerfile) sin el
resto del repo dentro; importar dashboard/ obligaria a copiar ese arbol. El
mapeo es corto y estable, asi que se copia aqui (el contrato autoriza
"copialo/adaptalo"). Si algun dia cambia el formato del uplink, se cambia en
ambos sitios — pero ese formato lleva congelado desde el ejercicio 09.
"""
import json
import socket
import ssl
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


def _b(v):
    """bool/None -> 1/0/None (para columnas enteras de SQLite)."""
    return None if v is None else (1 if v else 0)


def parse_chirpstack_up(payload: dict) -> dict:
    """Convierte un evento 'up' de ChirpStack v4 en un registro plano.

    Copia fiel de dashboard/mqtt_ingest.py::parse_chirpstack_up."""
    obj = payload.get("object") or {}
    rx_list = payload.get("rxInfo") or []
    rx0 = rx_list[0] if rx_list else {}
    tx = payload.get("txInfo") or {}
    di = payload.get("deviceInfo") or {}

    t = payload.get("time")
    try:
        ts = datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp() if t else time.time()
    except Exception:
        ts = time.time()

    return {
        "ts": ts,
        "iso": datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds"),
        "dev_eui": di.get("devEui") or payload.get("devEUI") or payload.get("devEui"),
        "f_cnt": payload.get("fCnt"),
        "f_port": payload.get("fPort"),
        "rssi": rx0.get("rssi"),
        "snr": rx0.get("snr", rx0.get("loRaSNR")),
        "gateway_id": rx0.get("gatewayId") or rx0.get("gatewayID"),
        "freq": tx.get("frequency"),
        "dr": payload.get("dr"),
        "gps_active": _b(obj.get("gps_active")),
        "gps_fix": _b(obj.get("gps_fix")),
        "latitude": obj.get("latitude"),
        "longitude": obj.get("longitude"),
        "altitude_m": obj.get("altitude_m"),
        "satellites": obj.get("satellites"),
        "battery_v": obj.get("battery_v"),
        "battery_pct": obj.get("battery_pct"),
        "charging": _b(obj.get("charging")),
        "usb_powered": _b(obj.get("usb_powered")),
        "temperature_c": obj.get("temperature_c"),
        "pressure_hpa": obj.get("pressure_hpa"),
        "raw_json": json.dumps(payload, ensure_ascii=False),
    }


def resolve_host(host):
    """host='auto'/'' -> IP LAN; el resto tal cual (igual que mqtt_ingest.py)."""
    if host and host not in ("auto", "0.0.0.0"):
        return host
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MqttIngest:
    """Suscriptor MQTT que empuja cada uplink al SessionManager.

    on_record(rec)  se invoca desde el hilo de paho por cada uplink.
    on_status(bool) refleja conexion/desconexion (para /health y para 'start')."""

    def __init__(self, host, port, app_id, dev_eui, on_record, on_status,
                 username=None, password=None, tls=True, ca_certs=None):
        self.host = resolve_host(host)
        self.port = int(port)
        self.on_record = on_record
        self.on_status = on_status
        dev = dev_eui if dev_eui else "+"
        self.topic = f"application/{app_id}/device/{dev}/event/up"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        if username:
            self.client.username_pw_set(username, password)
        if tls:
            # ca_certs=None -> almacen de CAs del sistema (incluye Let's Encrypt).
            self.client.tls_set(ca_certs=ca_certs, cert_reqs=ssl.CERT_REQUIRED)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self):
        # connect_async + loop_start: no bloquea el arranque de la app aunque el
        # broker tarde o este caido; el estado se reflejara por on_status.
        try:
            self.client.connect_async(self.host, self.port, keepalive=30)
            self.client.loop_start()
        except Exception as e:
            self.on_status(False, f"error MQTT: {e}")

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    # --- callbacks paho 2.x ---
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        failed = reason_code.is_failure if hasattr(reason_code, "is_failure") else (reason_code != 0)
        if not failed:
            client.subscribe(self.topic)
            self.on_status(True, f"MQTT OK · {self.topic}")
        else:
            self.on_status(False, f"MQTT rc={reason_code}")

    def _on_disconnect(self, client, userdata, *args):
        self.on_status(False, "MQTT desconectado")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self.on_record(parse_chirpstack_up(payload))
        except Exception:
            pass   # se ignora cualquier mensaje que no sea un uplink JSON valido
