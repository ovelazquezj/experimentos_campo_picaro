"""
config.py — Configuracion del microservicio de campo, leida del entorno.

POR QUE TODO POR VARIABLES DE ENTORNO
-------------------------------------
El servicio corre en un contenedor junto a ChirpStack en el servidor en la nube y se despliega
por `docker-compose` leyendo un `.env` (ver despliegue-campo/). No hay fichero de
config versionado con secretos: el token de la API, la contrasena MQTT, etc.
viven solo en el `.env` del servidor. Aqui centralizamos su lectura para que el
resto de modulos no toque `os.environ` a mano.

El mapa de corridas es CONSTANTE del experimento (§5 y §8 del contrato) y va
fijo aqui. Los IDs de device profile tambien son constantes de un despliegue,
pero son identificadores reales de ChirpStack y no se publican: se leen del
`.env` (PROFILE_ID_*); si faltan, quedan marcadores de ejemplo que ChirpStack
rechazara, en vez de apuntar en silencio a un perfil equivocado.
"""
import os
from dataclasses import dataclass, field


# --- IDs de device profile (del .env; los mismos que servidor/perfil.py) ------
# Cambiar el perfil de NUESTRO device es una operacion sobre un objeto propio
# del proyecto; nunca se toca la config global de ChirpStack (regla dura
# heredada, §1 del contrato). Sin la variable, queda el marcador de ejemplo.
PROFILE_IDS = {
    "ej09":      os.environ.get("PROFILE_ID_EJ09") or "<PROFILE_ID_EJ09>",
    "terreno-a": os.environ.get("PROFILE_ID_TERRENO_A") or "<PROFILE_ID_TERRENO_A>",
    "terreno-c": os.environ.get("PROFILE_ID_TERRENO_C") or "<PROFILE_ID_TERRENO_C>",
    # Radiosonda-PiCARO-ClaseC (docs/RADIOSONDA-ESPEC.md): Clase C con el codec
    # propio de la radiosonda (fPorts 20-23 y 30).
    "radiosonda-c": os.environ.get("PROFILE_ID_RADIOSONDA_C") or "<PROFILE_ID_RADIOSONDA_C>",
}

# --- Mapa de las 8 corridas (§5 del contrato + VUELO, D-64 + RADIOSONDA) ----
# (escenario, clase) -> fPort + perfil que hay que activar. El fPort es lo que
# permite ligar cada uplink a su corrida sin ambiguedad; el perfil selecciona el
# codec correcto (Clase A vs C) en ChirpStack. Una corrida puede fijar su propio
# `target` (uplinks hasta auto-finalizar); si no lo trae, usa el global
# (Config.target_uplinks, env TARGET_UPLINKS).
#
# Claves opcionales (RADIOSONDA es la primera que las usa; sin ellas, cada
# corrida conserva su comportamiento de siempre):
#   · fports:           TODOS los fPorts que son de la corrida (por defecto solo
#                       `fport`). Ninguno de ellos es desajuste. `fport` sigue
#                       siendo el principal: es el que se guarda como
#                       expected_fport y el que se informa en los avisos.
#   · fports_objetivo:  los que cuentan hacia el objetivo (por defecto `fports`).
#   · autofinaliza:     False = la sesion la cierra el operador aunque se llegue
#                       al objetivo (por defecto True).
#   · ping_auto:        False = sin ping automatico fPort 98 (por defecto True).
CORRIDAS = {
    ("URBANO",  "A"): {"fport": 11, "profile": "terreno-a"},
    ("URBANO",  "C"): {"fport": 12, "profile": "terreno-c"},
    ("TERRAZA", "A"): {"fport": 13, "profile": "terreno-a"},
    ("TERRAZA", "C"): {"fport": 14, "profile": "terreno-c"},
    ("CERRO16", "A"): {"fport": 15, "profile": "terreno-a"},
    ("CERRO16", "C"): {"fport": 16, "profile": "terreno-c"},
    # VUELO (docs/VUELO-ESPEC.md): SOLO Clase A. 55 rafagas x 3 paquetes
    # (P1 posicion, P2 ambiente, P3 navegacion) = 165 uplinks. VUELO-C no existe:
    # se rechaza como cualquier combinacion desconocida.
    ("VUELO",   "A"): {"fport": 17, "profile": "terreno-a", "target": 165},
    # RADIOSONDA (docs/RADIOSONDA-ESPEC.md): SOLO Clase C y solo la sonda
    # `radiosonda`. Cada lectura sale en 4 uplinks (20 posicion, 21 atmosfera,
    # 22 ambiente, 23 interno) cada 15 min: 4 lecturas en 55 min de vuelo = 16
    # uplinks nominales. El 30 es el Polo del Marco Polo, que no cuenta como
    # lectura. El firmware NO se detiene solo (sigue transmitiendo tras el
    # aterrizaje para poder recuperarla): llegar a 16 no cierra la sesion. Sin
    # ping automatico: el Marco Polo (fPort 30) lo sustituye.
    ("RADIOSONDA", "C"): {"fport": 20, "fports": (20, 21, 22, 23, 30),
                          "fports_objetivo": (20, 21, 22, 23),
                          "profile": "radiosonda-c", "target": 16,
                          "autofinaliza": False, "ping_auto": False},
}


def fports_de(corrida):
    """fPorts que pertenecen a una corrida (ver claves opcionales arriba)."""
    return tuple(corrida.get("fports") or (corrida["fport"],))


def fports_objetivo_de(corrida):
    """fPorts que cuentan hacia el objetivo de una corrida."""
    return tuple(corrida.get("fports_objetivo") or fports_de(corrida))

# Escenario VUELO y su geometria de rafagas (metricas por tipo/rafaga).
ESCENARIO_VUELO = "VUELO"
VUELO_RAFAGAS = 55
VUELO_TIPOS = ("posicion", "ambiente", "navegacion")
FPORT_VUELO = CORRIDAS[(ESCENARIO_VUELO, "A")]["fport"]   # 17
# Campos del decoder de fPort 17 sin columna en SQLite (viajan en raw_json) que
# se exponen en la clave `vuelo` de cada uplink (REST y WS).
VUELO_UPLINK_FIELDS = ("tipo_paquete", "rafaga", "humidity_pct", "speed_kmh",
                       "heading_deg", "hdop", "vspeed_ms", "uptime_s",
                       "mag_ok", "bme_ok")

# Escenario RADIOSONDA (docs/RADIOSONDA-ESPEC.md): tipo de paquete de cada fPort
# y campos del codec que se exponen en la clave `radiosonda` de cada uplink.
# Los nombres son EXACTAMENTE los de la salida del codec (firmware/decoder.js).
ESCENARIO_RADIOSONDA = "RADIOSONDA"
SONDA_RADIOSONDA = "radiosonda"
FPORT_MARCOPOLO = 30
RADIOSONDA_TIPO_POR_FPORT = {20: "posicion", 21: "atmosfera", 22: "ambiente",
                             23: "interno", FPORT_MARCOPOLO: "polo"}
# Los 4 tipos que forman una lectura completa (el Polo no es lectura).
RADIOSONDA_TIPOS_LECTURA = ("posicion", "atmosfera", "ambiente", "interno")
RADIOSONDA_CAMPOS = {
    "posicion":  ("gps_fix", "latitude", "longitude", "altitude_m", "satellites"),
    "atmosfera": ("ext_temperature_c", "ext_pressure_hpa", "ext_humidity_pct",
                  "tvoc_ppb", "eco2_ppm", "aqi", "battery_pct"),
    "ambiente":  ("aht_temperature_c", "aht_humidity_pct", "light_lux",
                  "dht_temperature_c", "dht_humidity_pct", "battery_v",
                  "uptime_s"),
    "interno":   ("temperature_c", "pressure_hpa", "humidity_pct", "ina_bus_v",
                  "ina_current_ma", "lectura", "gps_fix", "usb_powered",
                  "charging", "gps_active"),
    "polo":      ("seq", "rssi_dbm", "snr_db"),
}
# Campos enteros por naturaleza: ChirpStack los manda como double (3.0) porque
# el `object` del codec viaja como google.protobuf.Struct; se devuelven como int.
RADIOSONDA_ENTEROS = {"satellites", "altitude_m", "ext_humidity_pct", "tvoc_ppb",
                      "eco2_ppm", "aqi", "battery_pct", "aht_humidity_pct",
                      "light_lux", "dht_temperature_c", "dht_humidity_pct",
                      "uptime_s", "humidity_pct", "lectura", "seq", "rssi_dbm"}

# Conjunto de fPorts que pertenecen a ALGUNA corrida del experimento. Un uplink
# con uno de estos fPorts que no es de la corrida en curso es un "desajuste"
# (§6): la sonda esta en otra corrida distinta de la que la app arranco.
CORRIDA_FPORTS = {p for c in CORRIDAS.values() for p in fports_de(c)}

SCENARIOS = sorted({s for (s, _c) in CORRIDAS})   # CERRO16, RADIOSONDA, TERRAZA, URBANO, VUELO
CLASSES = tuple(sorted({c for (_s, c) in CORRIDAS}))   # A, C
# No todo escenario tiene ambas clases (VUELO solo A, RADIOSONDA solo C): la fuente de verdad de lo
# que es valido es CORRIDAS, no el producto SCENARIOS x CLASSES.
CLASES_POR_ESCENARIO = {s: tuple(sorted(c for (s2, c) in CORRIDAS if s2 == s))
                        for s in SCENARIOS}

# --- Sondas (D-65) -----------------------------------------------------------
# El servicio atiende varias sondas, UNA sesion a la vez. Cada sesion es de una
# sonda, y sobre su DevEUI se hacen el cambio de perfil, el gate de clase, los
# pings y la captura. El DevEUI de cada una sale del entorno (DEV_EUI para la
# T-Beam, que es la sonda por defecto y la unica que conocia la app <= 2.1.0;
# DEV_EUI_LORA32 para la T3; DEV_EUI_RADIOSONDA para la radiosonda).
#
# Corridas que admite cada sonda (None = todas las de CORRIDAS que no sean
# exclusivas de otra sonda). La T3 no tiene sensores y su firmware esta fijo en
# VUELO-A: abrir otra corrida para ella dejaria una sesion esperando un fPort que
# nunca va a llegar. La radiosonda es la MISMA T-Beam fisica (mismo DevEUI) con
# el firmware RADIOSONDA, que solo corre RADIOSONDA-C; y esa corrida es solo
# suya: con el firmware de terreno (`tbeam`) la placa nunca mandaria 20-23/30.
SONDA_POR_DEFECTO = "tbeam"
SONDA_CORRIDAS = {
    "tbeam":      None,
    "lora32":     {("VUELO", "A")},
    "radiosonda": {("RADIOSONDA", "C")},
}
# Corridas que solo puede abrir una sonda concreta: quedan fuera del "todas"
# (None) de las demas.
CORRIDAS_EXCLUSIVAS = {("RADIOSONDA", "C"): SONDA_RADIOSONDA}


def sonda_admite(sonda, scenario, class_):
    """True si la sonda (conocida) puede abrir la corrida (scenario, class_)."""
    exclusiva = CORRIDAS_EXCLUSIVAS.get((scenario, class_))
    if exclusiva is not None and exclusiva != sonda:
        return False
    admitidas = SONDA_CORRIDAS[sonda]
    return admitidas is None or (scenario, class_) in admitidas

# Sondas sin GPS propio (D-65): su distancia al gateway se mide con las
# posiciones que manda el TELEFONO del operador, nunca con la posicion que
# venga en el payload (en la T3 es simulada).
SONDAS_GPS_TELEFONO = {"lora32"}

# Un uplink se empareja con la posicion del telefono mas cercana en el tiempo,
# si no dista mas que esto. Mas lejos, el telefono pudo haberse movido.
POSICION_MAX_DESFASE_S = 300

# fPort de los downlink de ping de latencia (byte = numero de secuencia, §5).
# El Marco Polo de la radiosonda va por FPORT_MARCOPOLO (30) en ambos sentidos.
FPORT_PING = 98

# Mapa clase efectiva de ChirpStack (GET device -> classEnabled) -> clase del
# experimento. GetDeviceResponse.class_enabled es un enum common.DeviceClass;
# el gateway REST lo serializa como "CLASS_A"/"CLASS_B"/"CLASS_C".
CHIRPSTACK_CLASS = {"CLASS_A": "A", "CLASS_B": "B", "CLASS_C": "C"}

VERSION = "1.5.0"


def _get_float(name, default=None):
    """Lee una variable como float; vacia o ausente -> default (no 0.0).

    GW_LAT/GW_LON pueden faltar en un entorno de pruebas; en ese caso la
    distancia al gateway sale null en las metricas, que es mas honesto que
    inventar (0,0)."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class Config:
    """Instantanea de configuracion. Se crea una vez al arrancar la app."""
    campo_token: str = ""
    mqtt_host: str = "mqtt.pi-caro.org"
    mqtt_port: int = 8883
    mqtt_user: str = "picaro"
    mqtt_password: str = ""
    mqtt_tls: bool = True
    chirpstack_api: str = "https://api.pi-caro.org"
    chirpstack_token: str = ""
    app_id: str = ""
    dev_eui: str = ""              # sonda tbeam
    dev_eui_lora32: str = ""       # sonda lora32 (T3); vacio = no configurada
    # Sonda radiosonda: hoy el MISMO DevEUI que la tbeam (misma placa, otro
    # firmware). Vacio = no configurada.
    dev_eui_radiosonda: str = ""
    db_path: str = "/data/campo.db"
    gw_lat: float = None
    gw_lon: float = None
    # Objetivo por defecto de las corridas que no fijan el suyo en CORRIDAS
    # (VUELO lleva 165, RADIOSONDA 16). Ver target_for().
    target_uplinks: int = 300
    # Cadencia del ping automatico ligado a la sesion (D-61). 0 lo desactiva.
    # Es float para que los tests puedan inyectar intervalos de milisegundos.
    ping_interval_s: float = 60.0
    profile_ids: dict = field(default_factory=lambda: dict(PROFILE_IDS))

    def target_for(self, scenario, class_):
        """Objetivo de uplinks de una corrida: el suyo propio si lo fija en
        CORRIDAS, si no el global (TARGET_UPLINKS)."""
        corrida = CORRIDAS.get((scenario, class_)) or {}
        return corrida.get("target", self.target_uplinks)

    def dev_eui_for(self, sonda):
        """DevEUI de una sonda, en minusculas, o "" si no esta configurada."""
        eui = {"tbeam": self.dev_eui, "lora32": self.dev_eui_lora32,
               "radiosonda": self.dev_eui_radiosonda}.get(sonda, "")
        return (eui or "").lower()

    @classmethod
    def from_env(cls):
        # MQTT_TLS por defecto True: el broker en la nube exige TLS (8883). Solo
        # se apaga a mano contra un broker local anonimo de laboratorio.
        tls = os.environ.get("MQTT_TLS", "true").strip().lower() not in ("0", "false", "no")
        return cls(
            campo_token=os.environ.get("CAMPO_TOKEN", ""),
            mqtt_host=os.environ.get("MQTT_HOST", "mqtt.pi-caro.org"),
            mqtt_port=int(os.environ.get("MQTT_PORT", "8883")),
            mqtt_user=os.environ.get("MQTT_USER", "picaro"),
            mqtt_password=os.environ.get("MQTT_PASSWORD", ""),
            mqtt_tls=tls,
            chirpstack_api=os.environ.get("CHIRPSTACK_API", "https://api.pi-caro.org"),
            chirpstack_token=os.environ.get("CHIRPSTACK_TOKEN", ""),
            app_id=os.environ.get("APP_ID", ""),
            dev_eui=os.environ.get("DEV_EUI", ""),
            dev_eui_lora32=os.environ.get("DEV_EUI_LORA32", ""),
            dev_eui_radiosonda=os.environ.get("DEV_EUI_RADIOSONDA", ""),
            db_path=os.environ.get("DB_PATH", "/data/campo.db"),
            gw_lat=_get_float("GW_LAT"),
            gw_lon=_get_float("GW_LON"),
            target_uplinks=int(os.environ.get("TARGET_UPLINKS", "300")),
            ping_interval_s=_get_float("PING_INTERVAL_S", 60.0),
        )
