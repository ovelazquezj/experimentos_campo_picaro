"""
chirpstack.py — Cliente de la API REST de ChirpStack.

Encapsula las operaciones que el microservicio hace contra ChirpStack (§1 del
contrato): cambiar el device profile de NUESTRO device, LEER su clase efectiva
(gate de clase, D-60) y encolar downlinks (ping fPort 98; Marco fPort 30 de la
radiosonda). Todo lo demas (uplinks) llega por MQTT, en solo-lectura.

POR QUE UN CLIENTE APARTE Y NO LLAMADAS SUELTAS
-----------------------------------------------
Aislar la unica dependencia de red sincrona en una clase permite:
  1) mockearla entera en los tests (sin tocar ChirpStack real), y
  2) convertir cualquier fallo de red/HTTP en ChirpStackError, que main.py
     traduce a un 503 limpio (§6: "si la API de ChirpStack no responde, 503").

El cambio de perfil replica servidor/perfil.py: GET del device, se le cambia el
deviceProfileId y se hace PUT. El encolado de ping usa el endpoint de cola de
downlinks de ChirpStack v4 (POST /api/devices/{devEui}/queue), coherente con
"llama a la API REST ... para encolar downlinks de ping" (§1). El byte de datos
es el numero de secuencia, igual que servidor/pinger.py.
"""
import base64

import httpx

from .config import CHIRPSTACK_CLASS, FPORT_MARCOPOLO, FPORT_PING


class ChirpStackError(Exception):
    """Cualquier fallo hablando con ChirpStack (red, timeout o HTTP != 2xx).

    Se traduce a 503 en la capa REST: es un problema de dependencia externa, no
    del cliente que nos llama."""


class ChirpStackClient:
    def __init__(self, api_url, token, dev_eui, profile_ids, timeout=15.0):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.dev_eui = dev_eui
        self.profile_ids = profile_ids
        self.timeout = timeout

    def _headers(self):
        return {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
        }

    def _request(self, method, path, json_body=None):
        url = self.api_url + path
        try:
            with httpx.Client(timeout=self.timeout) as cli:
                r = cli.request(method, url, headers=self._headers(), json=json_body)
        except httpx.HTTPError as e:
            # Sin red / timeout / DNS: dependencia caida -> 503 aguas arriba.
            raise ChirpStackError(f"{method} {path}: {e}") from e
        if r.status_code >= 400:
            raise ChirpStackError(f"{method} {path} -> {r.status_code}: {r.text[:200]}")
        if r.content and r.content.strip():
            return r.json()
        return {}

    # Cada operacion actua sobre `dev_eui` si se pasa (la sonda de la sesion,
    # D-65) y si no sobre el device por defecto con el que se construyo.
    def _eui(self, dev_eui):
        return dev_eui or self.dev_eui

    # --- Perfil -------------------------------------------------------------
    def set_device_profile(self, profile_key, dev_eui=None):
        """Cambia el device profile del device al perfil `profile_key`
        (terreno-a | terreno-c | ej09). Devuelve la clave activada.

        Idempotente: si ya estaba en ese perfil, no hace el PUT. Replica la
        logica de servidor/perfil.py (GET device -> cambiar id -> PUT device)."""
        pid = self.profile_ids.get(profile_key)
        if pid is None:
            raise ChirpStackError(f"perfil desconocido: {profile_key}")
        eui = self._eui(dev_eui)
        dev = self._request("GET", f"/api/devices/{eui}").get("device")
        if not dev:
            raise ChirpStackError("respuesta sin 'device' al leer el dispositivo")
        if dev.get("deviceProfileId") == pid:
            return profile_key   # ya estaba; nada que hacer
        dev["deviceProfileId"] = pid
        self._request("PUT", f"/api/devices/{eui}", {"device": dev})
        return profile_key

    # --- Clase efectiva (gate de clase, D-60) --------------------------------
    def get_enabled_class(self, dev_eui=None):
        """Lee la clase EFECTIVA del device: 'A' | 'B' | 'C', o None si el
        servidor no expone el campo.

        ChirpStack v4 congela la clase operativa (`enabled_class`) en el momento
        del JOIN OTAA segun el perfil activo entonces; el PUT de cambio de perfil
        NO la actualiza (issue #360 de ChirpStack). Por eso el perfil que pone
        set_device_profile() y la clase con la que el servidor de red programa
        los downlinks pueden divergir. Este metodo lee la verdad operativa: el
        campo `classEnabled` de GetDeviceResponse (hermano de `device` y
        `deviceStatus` en GET /api/devices/{devEui}), serializado por el gateway
        REST como "CLASS_A"/"CLASS_B"/"CLASS_C"."""
        resp = self._request("GET", f"/api/devices/{self._eui(dev_eui)}")
        raw = resp.get("classEnabled")
        return CHIRPSTACK_CLASS.get(raw)

    # --- Gateways (D-65) -----------------------------------------------------
    def get_gateway_location(self, gateway_id):
        """(lat, lon) del gateway segun ChirpStack, o None si no tiene
        coordenadas cargadas (ChirpStack devuelve 0,0 en ese caso)."""
        resp = self._request("GET", f"/api/gateways/{gateway_id}")
        loc = (resp.get("gateway") or {}).get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None or (lat == 0 and lon == 0):
            return None
        return (float(lat), float(lon))

    # --- Ping ---------------------------------------------------------------
    def enqueue_ping(self, seq, dev_eui=None):
        """Encola un downlink fPort 98 cuyo unico byte es `seq` (0..255).

        El numero de secuencia es lo que permite emparejar el envio con lo que la
        sonda registre en su microSD y calcular la latencia (igual que
        servidor/pinger.py)."""
        return self._enqueue_seq(FPORT_PING, seq, dev_eui)

    def enqueue_marco(self, seq, dev_eui=None):
        """Encola el Marco de la radiosonda: downlink fPort 30 cuyo unico byte es
        `seq` (1..255, RADIOSONDA-ESPEC). La sonda contesta con un Polo fPort 30
        que trae el mismo seq, y con el se empareja el RTT.

        Va con `data` en bruto, igual que el ping: el byte ya es el payload final
        y asi no depende de que el encoder del codec ({"marco": seq}) este
        cargado en el profile."""
        return self._enqueue_seq(FPORT_MARCOPOLO, seq, dev_eui)

    def _enqueue_seq(self, fport, seq, dev_eui=None):
        eui = self._eui(dev_eui)
        data = base64.b64encode(bytes([seq & 0xFF])).decode()
        body = {"queueItem": {
            "devEui": eui,
            "confirmed": False,
            "fPort": fport,
            "data": data,
        }}
        return self._request("POST", f"/api/devices/{eui}/queue", body)
