"""
sessions.py — Maquina de estados de la sesion de captura, metricas en vivo y el
hub de WebSocket.

Es el corazon del microservicio. Concentra:
  · SessionManager: las transiciones de §3 (start/abort/finish/auto-finish), la
    ingesta de uplinks ligados a la sesion, el calculo de metricas (§6), el
    encolado de pings y el Marco Polo de la radiosonda (fPort 30).
  · WsHub: la lista de clientes WebSocket y el broadcast de mensajes (§7).
  · CampoError: errores de dominio con codigo HTTP, que main.py traduce a
    respuestas JSON {"detail": ...}.

DECISION DE CONCURRENCIA
------------------------
Los uplinks entran por el hilo de MQTT (paho) y las llamadas REST corren en el
threadpool de FastAPI; ambos tocan la SQLite y el estado de sesion. Por eso todo
lo que muta o lee estado consistente pasa por `self._lock` (un RLock). Asi la
invariante "una sola sesion capturando" y la SQLite quedan serializadas sin
depender del GIL.

DECISION DE BROADCAST
---------------------
El WsHub graba SIEMPRE el mensaje en un historico (util para los tests, que no
levantan un WebSocket real) y ADEMAS lo entrega a los clientes conectados. La
entrega se agenda en el event loop con run_coroutine_threadsafe porque el
broadcast se dispara desde hilos que no son el del loop (MQTT, threadpool).
"""
import asyncio
import bisect
import json
import math
import threading
import time
from datetime import datetime, timezone

from .config import (CORRIDAS, CORRIDA_FPORTS, ESCENARIO_RADIOSONDA,
                     ESCENARIO_VUELO, FPORT_MARCOPOLO, FPORT_PING, FPORT_VUELO,
                     POSICION_MAX_DESFASE_S, PROFILE_IDS, RADIOSONDA_CAMPOS,
                     RADIOSONDA_ENTEROS, RADIOSONDA_TIPO_POR_FPORT,
                     RADIOSONDA_TIPOS_LECTURA, SONDA_CORRIDAS, SONDA_POR_DEFECTO,
                     SONDA_RADIOSONDA, SONDAS_GPS_TELEFONO, VUELO_RAFAGAS,
                     VUELO_TIPOS, VUELO_UPLINK_FIELDS, fports_de, sonda_admite)
from .store import (DL_FIELDS, MP_FIELDS, POS_FIELDS, STATE_ABORTED,
                    STATE_CAPTURING, STATE_FINISHED)


# --- Errores de dominio -------------------------------------------------------
class CampoError(Exception):
    """Error con codigo HTTP asociado. main.py lo serializa a {"detail": ...}."""

    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# --- Hub de WebSocket ---------------------------------------------------------
class WsHub:
    """Registro de clientes WS y difusor de mensajes servidor->cliente (§7)."""

    def __init__(self, history_max=500):
        self._clients = set()
        self._loop = None                 # se ata en el startup de la app
        self._lock = threading.Lock()
        # Historico de lo emitido: los tests lo inspeccionan sin abrir un WS.
        # Acotado para no crecer sin limite en un servicio de larga vida.
        self.history = []
        self._history_max = history_max

    def attach_loop(self, loop):
        self._loop = loop

    def add(self, ws):
        """Registra un cliente YA aceptado. El accept lo hace el endpoint, que
        primero valida el token para poder cerrar con 1008 si es invalido."""
        with self._lock:
            self._clients.add(ws)

    def remove(self, ws):
        with self._lock:
            self._clients.discard(ws)

    def broadcast(self, message: dict):
        """Emite un mensaje a todos los clientes. Seguro desde cualquier hilo."""
        with self._lock:
            self.history.append(message)
            if len(self.history) > self._history_max:
                del self.history[:-self._history_max]
        # Agenda la entrega en el loop del servidor. Si aun no hay loop (tests
        # unitarios sin app), basta con el historico.
        loop = self._loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send_all(message), loop)

    async def _send_all(self, message):
        with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_json(message)
            except Exception:
                # Cliente caido a mitad de envio: se descarta sin tumbar al resto.
                self.remove(ws)

    async def send_to(self, ws, message: dict):
        """Envio directo a un solo cliente (p.ej. el 'hello' inicial)."""
        await ws.send_json(message)


# --- Utilidades ---------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    """Distancia en km entre dos coordenadas (formula del haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _round(v, n):
    return None if v is None else round(v, n)


def _last_known(ups, field):
    """Ultimo valor NO nulo de `field`. En VUELO cada uplink trae solo una parte
    de la lectura (P2/P3 sin posicion, P1 sin bateria): la magnitud se toma del
    ultimo paquete que la trajo, nunca de un null ni de un 0 inventado."""
    for u in reversed(ups):
        if u.get(field) is not None:
            return u[field]
    return None


def _uplink_object(u):
    """`object` decodificado del evento ChirpStack guardado en raw_json ({} si
    falta o no es JSON valido). Ahi viajan tipo_paquete, rafaga, hdop, etc."""
    try:
        obj = (json.loads(u.get("raw_json") or "{}") or {}).get("object")
    except (ValueError, AttributeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _entero(v):
    """int >= 0 o None. ChirpStack serializa el `object` del codec como un
    google.protobuf.Struct, donde TODO numero es double: la rafaga 3 llega como
    3.0 (visto en banco, sesion 44). Se aceptan floats enteros; un bool no."""
    if isinstance(v, bool):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return v if isinstance(v, int) and v >= 0 else None


def posicion_cercana(posiciones, ts):
    """Posicion del telefono mas cercana en el tiempo a `ts`, o None si la mas
    cercana dista mas de POSICION_MAX_DESFASE_S. `posiciones` va ordenada por ts."""
    if not posiciones or ts is None:
        return None
    tss = [p["ts"] for p in posiciones]
    i = bisect.bisect_left(tss, ts)
    candidatas = [posiciones[j] for j in (i - 1, i) if 0 <= j < len(posiciones)]
    mejor = min(candidatas, key=lambda p: abs(p["ts"] - ts))
    return mejor if abs(mejor["ts"] - ts) <= POSICION_MAX_DESFASE_S else None


def _posicion_publica(p):
    return {k: p.get(k) for k in POS_FIELDS} if p else None


def vuelo_metrics(ups):
    """Metricas propias de la corrida VUELO (docs/VUELO-ESPEC.md, «Metricas»):
    recibidos por tipo de paquete y estado de las rafagas agrupando por `rafaga`.

      · completa: llegaron los 3 tipos (P1+P2+P3) de esa rafaga;
      · parcial:  llegaron 1 o 2;
      · perdida:  ninguno, contando las rafagas 0..rafaga_max (las posteriores a
        la ultima vista aun no se sabe si se enviaron).
    La rafaga en curso cuenta como parcial hasta que llega su P3. Un uplink sin
    tipo/rafaga valido (decoder viejo, payload corrupto) no se clasifica."""
    por_tipo = {t: 0 for t in VUELO_TIPOS}
    tipos_por_rafaga = {}
    for u in ups:
        obj = _uplink_object(u)
        tipo = obj.get("tipo_paquete")
        rafaga = _entero(obj.get("rafaga"))
        if tipo not in por_tipo:
            continue
        por_tipo[tipo] += 1
        if rafaga is not None:
            # Conjunto de tipos: un duplicado del mismo paquete no hace 4/3.
            tipos_por_rafaga.setdefault(rafaga, set()).add(tipo)

    rafaga_max = max(tipos_por_rafaga) if tipos_por_rafaga else None
    completas = sum(1 for t in tipos_por_rafaga.values() if len(t) == len(VUELO_TIPOS))
    parciales = len(tipos_por_rafaga) - completas
    perdidas = (rafaga_max + 1 - len(tipos_por_rafaga)) if rafaga_max is not None else 0
    return {
        "por_tipo": por_tipo,
        "rafagas_completas": completas,
        "rafagas_parciales": parciales,
        "rafagas_perdidas": perdidas,
        "rafaga_max": rafaga_max,
        "rafagas_objetivo": VUELO_RAFAGAS,
    }


# Columnas que NO se exponen tal cual en el WS/REST de uplinks: raw_json es el
# evento entero de ChirpStack, pesado e innecesario para la app (que ya recibe
# los campos aplanados).
def public_uplink(row: dict) -> dict:
    out = {k: v for k, v in row.items() if k != "raw_json"}
    # VUELO: los campos que no tienen columna viajan en raw_json; se exponen
    # SOLO esos, en la clave `vuelo` (null en los demas fPorts).
    out["vuelo"] = vuelo_uplink_fields(row)
    # RADIOSONDA: igual, en la clave `radiosonda` (null en los demas fPorts).
    out["radiosonda"] = radiosonda_uplink_fields(row)
    return out


def vuelo_uplink_fields(row: dict):
    """Campos propios de VUELO de un uplink fPort 17 (los que falten -> null),
    sacados del `object` decodificado. None para cualquier otro fPort."""
    if row.get("f_port") != FPORT_VUELO:
        return None
    obj = _uplink_object(row)
    out = {k: obj.get(k) for k in VUELO_UPLINK_FIELDS}
    for k in ("rafaga", "uptime_s"):          # enteros, aunque ChirpStack los mande 3.0
        if out.get(k) is not None:
            out[k] = _entero(out[k])
    return out


# --- RADIOSONDA (docs/RADIOSONDA-ESPEC.md) ------------------------------------
def _rs_valor(campo, v):
    """Valor de un campo del codec de la radiosonda: los enteros que ChirpStack
    manda como double (Struct) vuelven a int; el resto, tal cual. A diferencia
    de _entero(), admite negativos (rssi_dbm, dht_temperature_c)."""
    if campo in RADIOSONDA_ENTEROS and isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def radiosonda_uplink_fields(row: dict):
    """Campos propios de la radiosonda de un uplink fPort 20-23/30: el
    `tipo_paquete` y los campos de SU tabla en la especificacion (los que falten
    -> null). None para cualquier otro fPort.

    El tipo se toma del codec; si no lo trae (decoder viejo, object vacio), del
    fPort, que en esta corrida lo determina sin ambiguedad."""
    tipo_fport = RADIOSONDA_TIPO_POR_FPORT.get(row.get("f_port"))
    if tipo_fport is None:
        return None
    obj = _uplink_object(row)
    tipo = obj.get("tipo_paquete")
    if tipo not in RADIOSONDA_CAMPOS:
        tipo = tipo_fport
    out = {"tipo_paquete": tipo}
    for k in RADIOSONDA_CAMPOS[tipo]:
        out[k] = _rs_valor(k, obj.get(k))
    return out


# Magnitudes de una lectura (union de los campos de 20-23, sin repetir gps_fix).
_RS_MAGNITUDES = tuple(dict.fromkeys(
    k for t in RADIOSONDA_TIPOS_LECTURA for k in RADIOSONDA_CAMPOS[t]))


def radiosonda_lecturas(paquetes):
    """Agrupa los paquetes de telemetria (f_cnt, indice 0..3 del tipo) en
    lecturas. Devuelve una lista de conjuntos de indices, uno por lectura.

    Los fPort 20-22 no llevan el contador `lectura` (no cabe en 11 bytes), asi
    que se agrupan por fCnt consecutivo (RADIOSONDA-ESPEC): 20 = n, 21 = n+1,
    22 = n+2, 23 = n+3. Dos paquetes son de la misma lectura si el tipo avanza y
    el salto de fCnt menos el salto de tipo (los fCnt "de mas") es < 4. Entre
    dos paquetes de una misma lectura solo pueden colarse Polos (la sonda
    contesta el Marco en cuanto lo recibe, aunque este a mitad de rafaga); entre
    lecturas distintas hay como poco 4 fCnt de mas (los otros 4 paquetes). Asi
    un Polo intercalado, o uno que se perdio por el camino, no parte la lectura
    en dos. Los duplicados (mismo fCnt y tipo) cuentan una vez."""
    grupos = []
    cur = None                                 # [indices, ultimo_fcnt, ultimo_idx]
    for fcnt, idx in sorted(set(paquetes)):
        if cur is not None and idx > cur[2] \
                and 0 <= (fcnt - cur[1]) - (idx - cur[2]) < 4:
            cur[0].add(idx)
            cur[1], cur[2] = fcnt, idx
        else:
            cur = [{idx}, fcnt, idx]
            grupos.append(cur)
    return [g[0] for g in grupos]


def radiosonda_metrics(ups, marcopolo, objetivo):
    """Bloque `radiosonda` de las metricas (RADIOSONDA-ESPEC, «Contrato»):
      · ultima: ultimo valor CONOCIDO de cada magnitud. Cada uplink trae solo una
        parte de la lectura; la magnitud sale del ultimo paquete que la trajo y
        un null nunca tapa un valor anterior ni se pinta como 0;
      · recibidos por tipo, telemetria (20-23) contra el objetivo de 16;
      · lecturas completas (4 de 4) y parciales (1-3), agrupadas por fCnt;
      · Marco Polo: Marcos enviados, Polos emparejados y RTT medio/min/max."""
    por_tipo = {t: 0 for t in RADIOSONDA_TIPOS_LECTURA + ("polo",)}
    ultima = {k: None for k in _RS_MAGNITUDES}
    paquetes = []
    for u in ups:
        rs = radiosonda_uplink_fields(u)
        if rs is None:
            continue
        tipo = rs["tipo_paquete"]
        por_tipo[tipo] += 1
        if tipo == "polo":
            continue
        for k, v in rs.items():
            if k in ultima and v is not None:
                ultima[k] = v
        if u.get("f_cnt") is not None:
            paquetes.append((u["f_cnt"], RADIOSONDA_TIPOS_LECTURA.index(tipo)))

    lecturas = radiosonda_lecturas(paquetes)
    completas = sum(1 for g in lecturas if len(g) == len(RADIOSONDA_TIPOS_LECTURA))
    telemetria = sum(por_tipo[t] for t in RADIOSONDA_TIPOS_LECTURA)

    enviados = [m for m in marcopolo if m.get("enqueued_ts") is not None]
    rtts = [m["rtt_ms"] for m in enviados if m.get("rtt_ms") is not None]
    return {
        "ultima": ultima,
        "por_tipo": por_tipo,
        "telemetria_recibidos": telemetria,
        "telemetria_objetivo": objetivo,
        "lecturas_completas": completas,
        "lecturas_parciales": len(lecturas) - completas,
        "lectura_ultima": ultima.get("lectura"),
        "marcos_enviados": len(enviados),
        "polos_recibidos": len(rtts),
        # Polos sin Marco pendiente (duplicados o de antes de un reinicio).
        "polos_sin_marco": sum(1 for m in marcopolo if m.get("enqueued_ts") is None),
        "rtt_ms_mean": _round(_mean(rtts), 1),
        "rtt_ms_min": min(rtts) if rtts else None,
        "rtt_ms_max": max(rtts) if rtts else None,
    }


def _marcopolo_publico(m):
    return {k: m.get(k) for k in MP_FIELDS}


# --- Gestor de sesiones -------------------------------------------------------
class SessionManager:
    def __init__(self, store, chirpstack, hub, config):
        self.store = store
        self.chirpstack = chirpstack
        self.hub = hub
        self.config = config
        self._lock = threading.RLock()
        self._mqtt_connected = False
        # Secuencia de ping, 1..255 ciclica; se reinicia al arrancar una sesion
        # para que el cruce (run_id, seq) no sea ambiguo entre corridas. La
        # COMPARTEN el ping manual y el automatico (D-61).
        self._ping_seq = 0
        # Secuencia del Marco Polo de la radiosonda (fPort 30), 1..255 ciclica.
        # Propia (no la del ping): el Polo la devuelve y con ella se empareja el
        # RTT. Tambien se reinicia al abrir sesion.
        self._marco_seq = 0
        # Event loop de la app (lo ata el lifespan) y tarea del ping automatico.
        self._loop = None
        self._ping_task = None
        # Coordenadas de cada gateway segun ChirpStack (D-65), para no
        # preguntarlas en cada uplink. None = el gateway no tiene coordenadas.
        self._gw_cache = {}

    # --- Estado MQTT (lo actualiza ingest.py; los tests lo fuerzan) ---------
    def set_mqtt_connected(self, connected: bool):
        self._mqtt_connected = bool(connected)

    @property
    def mqtt_connected(self):
        return self._mqtt_connected

    def attach_loop(self, loop):
        self._loop = loop
        self.hub.attach_loop(loop)

    def shutdown(self):
        """Apagado ordenado del servicio: mata la tarea de ping automatico para
        que no quede un sleep colgando el cierre del event loop."""
        self._cancel_auto_ping()

    # --- Sondas (D-65) ------------------------------------------------------
    def _dev_eui_sonda(self, sonda):
        """DevEUI de una sonda conocida y configurada; 400 si no lo es."""
        if sonda not in SONDA_CORRIDAS:
            raise CampoError(400, f"sonda desconocida: {sonda}")
        eui = self.config.dev_eui_for(sonda)
        if not eui:
            raise CampoError(400, f"la sonda {sonda} no esta configurada en el "
                                  f"servidor (falta su DevEUI en el entorno)")
        return eui

    def _session_dev_eui(self, session):
        """DevEUI de la sonda de una sesion. Las sesiones anteriores a D-65 no
        lo guardaron: eran todas de la T-Beam."""
        return ((session or {}).get("dev_eui")
                or self.config.dev_eui_for(SONDA_POR_DEFECTO))

    # --- Distancia con el GPS del telefono (D-65) ----------------------------
    def _gw_coords(self, gateway_id):
        """(lat, lon) del gateway que recibio un uplink: las de ChirpStack si las
        tiene; si no, las de GW_LAT/GW_LON del entorno; si tampoco, None. Un fallo
        de red no se cachea: se reintenta en el siguiente uplink."""
        loc = None
        if gateway_id:
            if gateway_id in self._gw_cache:
                loc = self._gw_cache[gateway_id]
            else:
                getter = getattr(self.chirpstack, "get_gateway_location", None)
                if getter is not None:
                    try:
                        loc = getter(gateway_id)
                        self._gw_cache[gateway_id] = loc
                    except Exception:
                        loc = None
        if loc is None and self.config.gw_lat is not None and self.config.gw_lon is not None:
            loc = (self.config.gw_lat, self.config.gw_lon)
        return loc

    def distancias_telefono(self, session, ups):
        """Para cada uplink: posicion del telefono emparejada, gateway que lo
        recibio y distancia entre ambos. Alineada con `ups`; cada elemento es un
        dict con tel_lat, tel_lon, tel_precision_m, gw_lat, gw_lon, dist_gw_km
        (null lo que no se pueda saber)."""
        posiciones = self.store.session_posiciones(session["id"])
        out = []
        for u in ups:
            p = posicion_cercana(posiciones, u.get("ts"))
            gw = self._gw_coords(u.get("gateway_id"))
            d = None
            if p is not None and gw is not None:
                d = haversine_km(gw[0], gw[1], p["lat"], p["lon"])
            out.append({
                "tel_lat": p["lat"] if p else None,
                "tel_lon": p["lon"] if p else None,
                "tel_precision_m": p["precision_m"] if p else None,
                "gw_lat": gw[0] if gw else None,
                "gw_lon": gw[1] if gw else None,
                "dist_gw_km": _round(d, 3),
            })
        return out

    def add_posicion(self, session_id, lat, lon, alt_m=None, precision_m=None,
                     ts=None):
        """Registra un fix del GPS del telefono en una sesion capturando."""
        with self._lock:
            session = self.store.get_session(session_id)
            if session is None:
                raise CampoError(404, f"sesion {session_id} no encontrada")
            if session["state"] != STATE_CAPTURING:
                raise CampoError(409, "la sesion no esta capturando")
            pos = self.store.insert_posicion(session_id, lat, lon, alt_m,
                                             precision_m, ts)
            metrics = self._metrics_locked(session)
        pub = _posicion_publica(pos)
        self.hub.broadcast({"type": "posicion", **pub})
        self.hub.broadcast({"type": "metrics", **metrics})
        return pub

    def session_posiciones(self, session_id):
        if self.store.get_session(session_id) is None:
            raise CampoError(404, f"sesion {session_id} no encontrada")
        return [_posicion_publica(p)
                for p in self.store.session_posiciones(session_id)]

    def uplinks_con_distancia(self, session_id):
        """Uplinks de una sesion (filas de la SQLite) con las columnas de la
        distancia medida desde el telefono, para el CSV. En las sesiones de
        sondas con GPS propio esas columnas van vacias."""
        session = self.store.get_session(session_id)
        if session is None:
            raise CampoError(404, f"sesion {session_id} no encontrada")
        ups = self.store.session_uplinks(session_id)
        if session.get("sonda") not in SONDAS_GPS_TELEFONO:
            return ups
        with self._lock:
            extra = self.distancias_telefono(session, ups)
        return [{**u, **e} for u, e in zip(ups, extra)]

    # --- Transiciones -------------------------------------------------------
    def start_session(self, scenario, class_, sonda=SONDA_POR_DEFECTO):
        scenario = (scenario or "").upper()
        class_ = (class_ or "").upper()
        sonda = (sonda or SONDA_POR_DEFECTO).lower()
        corrida = CORRIDAS.get((scenario, class_))
        if corrida is None:
            raise CampoError(400, f"corrida desconocida: {scenario}/{class_}")
        dev_eui = self._dev_eui_sonda(sonda)
        # Cada sonda solo abre sus corridas, y las exclusivas (RADIOSONDA-C)
        # solo su sonda: tbeam y lora32 no pueden abrir RADIOSONDA-C.
        if not sonda_admite(sonda, scenario, class_):
            raise CampoError(400, f"la sonda {sonda} no admite la corrida "
                                  f"{scenario}/{class_}")

        with self._lock:
            # Invariante dura: una sola sesion capturando a la vez (§3).
            if self.store.current_session() is not None:
                raise CampoError(409, "ya hay una sesion capturando")

            # Sin MQTT no podriamos capturar los uplinks: mejor fallar pronto con
            # 503 que abrir una sesion que nunca recibira datos (§6).
            if not self._mqtt_connected:
                raise CampoError(503, "MQTT no conectado; no se puede capturar")

            base = self._run_label_base(scenario, class_)
            run_label = self.store.next_run_label(base)
            profile = corrida["profile"]
            expected_fport = corrida["fport"]

            # El cambio de perfil es parte de 'start' (§3): si ChirpStack no
            # responde, no se abre la sesion (ChirpStackError -> 503 en main).
            self.chirpstack.set_device_profile(profile, dev_eui=dev_eui)

            # GATE DE CLASE (D-60, §15.1). ChirpStack v4 congela la clase
            # EFECTIVA del device en el JOIN OTAA segun el perfil activo
            # entonces; el PUT de arriba NO la actualiza (issue #360 de
            # ChirpStack). Como la sonda hace su unico join al encender (D-41),
            # normalmente ANTES de este start, el servidor puede quedarse
            # operando con la clase de la corrida anterior: en campo, una
            # corrida de Clase A recibio 0/764 downlinks porque el servidor la
            # creia C y transmitia por RX2 a una sonda sorda. La sesion NO se
            # abre con la clase desajustada: 409 con la instruccion de
            # recuperacion (el perfil bueno YA quedo puesto arriba, asi que
            # apagar/encender fuerza un join que congela la clase correcta).
            enabled = self.chirpstack.get_enabled_class(dev_eui=dev_eui)
            if enabled is None:
                # Servidor sin el campo classEnabled (ChirpStack < 4.6): no se
                # puede verificar. Se avisa y se deja pasar: bloquear aqui
                # dejaria la campana entera sin poder arrancar.
                self.hub.broadcast({"type": "warning", "kind": "class_unverified",
                                    "expected": class_, "got": None})
            elif enabled != class_:
                self.hub.broadcast({"type": "warning", "kind": "class_mismatch",
                                    "expected": class_, "got": enabled})
                raise CampoError(
                    409,
                    f"clase desajustada: ChirpStack tiene el device en clase "
                    f"efectiva {enabled} y la corrida es de clase {class_} "
                    f"(la clase se congela en el JOIN; el cambio de perfil no "
                    f"la actualiza). El perfil {profile} ya quedo puesto, asi "
                    f"que basta con que la sonda rehaga el JOIN: la app lo "
                    f"pide sola por BLE y reintenta (D-62). Con el boton, o si "
                    f"el firmware no admite el re-join, apaga y enciende la "
                    f"sonda y vuelve a arrancar.")

            session = self.store.create_session(
                run_label=run_label, scenario=scenario, class_=class_,
                expected_fport=expected_fport, profile=profile,
                target_uplinks=self.config.target_for(scenario, class_),
                sonda=sonda, dev_eui=dev_eui)
            self._ping_seq = 0
            self._marco_seq = 0

        # Ping automatico ligado a la sesion (D-61): arranca con ella y muere
        # con ella. Fuera del lock (solo agenda una corutina en el loop).
        # RADIOSONDA no lo lleva: el Marco Polo (fPort 30) lo sustituye.
        if corrida.get("ping_auto", True):
            self._start_auto_ping(session["id"])

        self.hub.broadcast({"type": "session", **session})
        return session

    def abort_session(self, session_id):
        return self._close_session(session_id, STATE_ABORTED)

    def finish_session(self, session_id):
        return self._close_session(session_id, STATE_FINISHED)

    def delete_session(self, session_id):
        """Borra una sesion y sus datos (§6 DELETE). Irreversible.

        No se borra una sesion EN CAPTURA: primero hay que abortarla. Asi un
        borrado accidental no puede tumbar una medida en marcha."""
        with self._lock:
            session = self.store.get_session(session_id)
            if session is None:
                raise CampoError(404, f"sesion {session_id} no encontrada")
            if session["state"] == STATE_CAPTURING:
                raise CampoError(409, "no se puede borrar una sesion en captura; "
                                      "abortala primero")
            self.store.delete_session(session_id)
        return {"id": session_id, "deleted": True}

    def _close_session(self, session_id, new_state):
        with self._lock:
            session = self.store.get_session(session_id)
            if session is None:
                raise CampoError(404, f"sesion {session_id} no encontrada")
            if session["state"] != STATE_CAPTURING:
                raise CampoError(409, "la sesion no esta capturando")
            session = self.store.set_session_state(
                session_id, new_state, ended_at=time.time())
        # El ciclo de ping automatico muere con la sesion (stop/abort, D-61).
        self._cancel_auto_ping()
        self.hub.broadcast({"type": "session", **session})
        return session

    def _run_label_base(self, scenario, class_):
        # Fecha UTC del servidor (§3). El firmware usa la del GPS; aqui usamos la
        # del servidor porque es de quien disponemos y siempre es valida.
        fecha = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"{fecha}-{scenario}-{class_}"

    # --- Ingesta de uplinks -------------------------------------------------
    def ingest_record(self, rec: dict):
        """Procesa un uplink ya aplanado (parse_chirpstack_up). Sincrono: lo
        llama el hilo de MQTT y tambien los tests. Devuelve la fila guardada o
        None si no pertenece a la sesion activa."""
        with self._lock:
            session = self.store.current_session()
            if session is None:
                return None   # sin sesion capturando no hay nada que ligar

            # Uplink de OTRA sonda (D-65): el MQTT trae todos los devices de la
            # aplicacion y la sesion es de una sola. Se ignora en silencio: la
            # otra sonda puede estar encendida con toda normalidad.
            eui = (rec.get("dev_eui") or "").lower()
            if eui and eui != self._session_dev_eui(session):
                return None

            fport = rec.get("f_port")
            expected = session["expected_fport"]
            # fPorts de la corrida: uno solo en las clasicas y VUELO; 20-23 y 30
            # en RADIOSONDA. Ninguno de ellos es desajuste.
            corrida = CORRIDAS.get((session["scenario"], session["class"])) or {}
            propios = fports_de(corrida) if corrida else (expected,)

            if fport in propios:
                self.store.insert_uplink(rec, session["id"])
                # Polo del Marco Polo: se empareja con su Marco ANTES de calcular
                # las metricas, para que el RTT ya cuente en el bloque radiosonda.
                polo = None
                if fport == FPORT_MARCOPOLO and \
                        session.get("scenario") == ESCENARIO_RADIOSONDA:
                    polo = self._registrar_polo_locked(session, rec)
                metrics = self._metrics_locked(session)
                # ¿Llego al objetivo? Auto-finaliza (§3). Se decide dentro del
                # lock para que dos uplinks casi simultaneos no la cierren dos veces.
                finished = None
                # Auto-finaliza cuando la sonda ha ENVIADO el objetivo desde que
                # empezo la sesion. Se mide con el rango de fCnt (recibidos+gaps),
                # NO con el fCnt absoluto: una segunda corrida sin reiniciar la
                # sonda arranca con el contador alto y el absoluto la cerraria al
                # instante. El rango espeja el "TX n/300" del propio dispositivo.
                # RADIOSONDA no se autofinaliza: la sonda sigue transmitiendo
                # tras el aterrizaje y la sesion la cierra el operador.
                enviados = metrics.get("received", 0) + metrics.get("gaps", 0)
                if corrida.get("autofinaliza", True) and \
                        enviados >= session["target_uplinks"]:
                    finished = self.store.set_session_state(
                        session["id"], STATE_FINISHED, ended_at=time.time())
            elif fport in CORRIDA_FPORTS:
                # fPort de OTRA corrida: la sonda esta en un escenario/clase
                # distinto del que arranco la app. Se avisa pero NO se guarda (§6).
                self.hub.broadcast({"type": "warning", "kind": "fport_mismatch",
                                    "expected": expected, "got": fport})
                return None
            else:
                # fPort ajeno al experimento (p.ej. un heartbeat): se ignora.
                return None

        # Fuera del lock: difundir (el broadcast no toca estado protegido).
        self.hub.broadcast({"type": "uplink", **public_uplink(rec)})
        if polo is not None:
            self.hub.broadcast(polo)
        self.hub.broadcast({"type": "metrics", **metrics})
        if finished is not None:
            # La auto-finalizacion tambien mata el ping automatico (D-61).
            self._cancel_auto_ping()
            self.hub.broadcast({"type": "session", **finished})
        return rec

    # --- Metricas y resumen -------------------------------------------------
    def metrics(self, session):
        with self._lock:
            return self._metrics_locked(session)

    def _metrics_locked(self, session):
        ups = self.store.session_uplinks(session["id"])
        expected = session["expected_fport"]
        target = session["target_uplinks"]
        received = len(ups)
        # Bloque `vuelo` solo en sesiones VUELO; null en las demas corridas.
        es_vuelo = session.get("scenario") == ESCENARIO_VUELO
        # Bloque `radiosonda` solo en sesiones RADIOSONDA (null en las demas).
        # Como en VUELO, cada uplink trae solo una parte de la lectura.
        es_radiosonda = session.get("scenario") == ESCENARIO_RADIOSONDA
        lectura_partida = es_vuelo or es_radiosonda
        radiosonda = (radiosonda_metrics(
            ups, self.store.session_marcopolo(session["id"]), target)
            if es_radiosonda else None)
        # Sonda sin GPS propio (D-65): la distancia sale del telefono.
        gps_tel = session.get("sonda") in SONDAS_GPS_TELEFONO
        posiciones = self.store.session_posiciones(session["id"]) if gps_tel else []
        telefono = {
            "posicion_telefono": _posicion_publica(posiciones[-1]) if posiciones else None,
            "dist_gw_km_ultima": None,
            "gateway_ultimo": None,
        }

        if received == 0:
            return {
                "received": 0, "expected_fport": expected, "last_fcnt": None,
                "gaps": 0, "pdr_est": None, "progress_pct": 0.0,
                "rssi_mean": None, "rssi_last": None, "snr_mean": None,
                "dist_gw_km_max": None, "last_uplink_iso": None,
                "battery_v": None, "battery_pct": None,
                "gps_fix": None, "satellites": None,
                "vuelo": vuelo_metrics([]) if es_vuelo else None,
                "radiosonda": radiosonda,
                **telefono,
            }

        fcnts = [u["f_cnt"] for u in ups if u["f_cnt"] is not None]
        first_fcnt = min(fcnts) if fcnts else None
        last_fcnt = max(fcnts) if fcnts else None

        # PDR estimado (§6): recibidos / (rango de fCnt). Es ESTIMADO porque el
        # denominador real (cuantos deberia haber) vive en la microSD; aqui se
        # aproxima con el rango de contadores observado.
        span = (last_fcnt - first_fcnt + 1) if (first_fcnt is not None) else 0
        pdr = (received / span) if span > 0 else None
        gaps = (span - received) if span > 0 else 0
        # Progreso = uplinks ENVIADOS desde el inicio de la sesion (el rango de
        # fCnt), no el fCnt absoluto: asi coincide con el "TX n/300" del device y
        # es robusto a que la corrida no empiece con el contador en cero. Se topa
        # a 100 porque el device se detiene en su objetivo y la captura puede
        # haber arrancado un poco antes o despues.
        progress = min(100.0, 100.0 * span / target) if (span and target) else 0.0
        if es_radiosonda:
            # En RADIOSONDA el objetivo son 16 uplinks de TELEMETRIA (20-23) y el
            # rango de fCnt incluye los Polos: el progreso se mide con la
            # telemetria recibida. Topado a 100: la sonda sigue transmitiendo
            # despues de las 4 lecturas nominales.
            tel = radiosonda["telemetria_recibidos"]
            progress = min(100.0, 100.0 * tel / target) if target else 0.0

        rssi_vals = [u["rssi"] for u in ups]
        snr_vals = [u["snr"] for u in ups]

        # Distancia maxima al gateway por haversine, solo con puntos con fix y
        # coordenadas validas (se descarta el (0,0) del arranque sin fix).
        # En VUELO solo P1 trae lat/lon; P2/P3 llegan con null y se saltan
        # (nunca cuentan como (0,0)). Si el decoder de P1 no mandara gps_fix,
        # basta con que traiga coordenadas (sin fix las da null, VUELO-ESPEC).
        dist_max = None
        if gps_tel:
            # Telefono -> gateway que recibio cada uplink. La posicion que
            # venga en el payload no cuenta: en la T3 es simulada.
            dist = self.distancias_telefono(session, ups)
            vals = [d["dist_gw_km"] for d in dist if d["dist_gw_km"] is not None]
            dist_max = max(vals) if vals else None
            telefono["dist_gw_km_ultima"] = dist[-1]["dist_gw_km"]
            telefono["gateway_ultimo"] = {"id": ups[-1].get("gateway_id"),
                                          "lat": dist[-1]["gw_lat"],
                                          "lon": dist[-1]["gw_lon"]}
        elif self.config.gw_lat is not None and self.config.gw_lon is not None:
            for u in ups:
                con_fix = u["gps_fix"] or (lectura_partida and u["gps_fix"] is None)
                if con_fix and u["latitude"] is not None and u["longitude"] is not None \
                        and not (u["latitude"] == 0 and u["longitude"] == 0):
                    d = haversine_km(self.config.gw_lat, self.config.gw_lon,
                                     u["latitude"], u["longitude"])
                    dist_max = d if dist_max is None else max(dist_max, d)

        last = ups[-1]
        # Magnitudes de estado del device. En las corridas clasicas cada uplink
        # las trae todas y se toma el ultimo tal cual (un null es un null). En
        # VUELO y RADIOSONDA se toma el ultimo paquete que TRAJO cada una (P3 no
        # trae bateria; en la radiosonda la bateria va en 21/22 y el fix en 20/23).
        if lectura_partida:
            estado = {f: _last_known(ups, f)
                      for f in ("battery_v", "battery_pct", "gps_fix", "satellites")}
        else:
            estado = {f: last[f]
                      for f in ("battery_v", "battery_pct", "gps_fix", "satellites")}
        return {
            "received": received,
            "expected_fport": expected,
            "last_fcnt": last_fcnt,
            "gaps": gaps,
            "pdr_est": _round(pdr, 2),
            "progress_pct": _round(progress, 1),
            "rssi_mean": _round(_mean(rssi_vals), 1),
            "rssi_last": last["rssi"],
            "snr_mean": _round(_mean(snr_vals), 1),
            "dist_gw_km_max": _round(dist_max, 1),
            "last_uplink_iso": last["iso"],
            "battery_v": estado["battery_v"],
            # battery_pct puede ser null (0xFF->null en el decoder); NO se fuerza a 0.
            "battery_pct": estado["battery_pct"],
            "gps_fix": bool(estado["gps_fix"]) if estado["gps_fix"] is not None else None,
            "satellites": estado["satellites"],
            "vuelo": vuelo_metrics(ups) if es_vuelo else None,
            "radiosonda": radiosonda,
            **telefono,
        }

    def summary(self, session):
        """Resumen de una sesion cerrada (§6)."""
        m = self.metrics(session)
        ended = session["ended_at"] if session["ended_at"] is not None else time.time()
        return {
            "received": m["received"],
            "pdr_est": m["pdr_est"],
            "rssi_mean": m["rssi_mean"],
            "snr_mean": m["snr_mean"],
            "dist_gw_km_max": m["dist_gw_km_max"],
            "duracion_s": _round(ended - session["started_at"], 1),
            "run_label": session["run_label"],
            "state": session["state"],
            "vuelo": m["vuelo"],
            "radiosonda": m["radiosonda"],
        }

    def session_uplinks(self, session_id):
        session = self.store.get_session(session_id)
        if session is None:
            raise CampoError(404, f"sesion {session_id} no encontrada")
        return [public_uplink(u) for u in self.store.session_uplinks(session_id)]

    def session_downlinks(self, session_id):
        """Downlinks ENVIADOS de una sesion (el lado 'enviado' del cruce de
        latencia, D-61), con las columnas publicas DL_FIELDS."""
        session = self.store.get_session(session_id)
        if session is None:
            raise CampoError(404, f"sesion {session_id} no encontrada")
        return [{k: d.get(k) for k in DL_FIELDS}
                for d in self.store.session_downlinks(session_id)]

    # --- Marco Polo de la radiosonda (fPort 30, RADIOSONDA-ESPEC) -----------
    # Sustituye al ping automatico en RADIOSONDA: la app pide un Marco, se encola
    # el downlink fPort 30 [seq] y la sonda (Clase C, escucha siempre) contesta
    # en segundos con un Polo fPort 30 que trae el mismo seq y la senal con la
    # que recibio el Marco. RTT = llegada del Polo - encolado del Marco, ambos
    # con el reloj de ESTE servicio (nunca se mezclan relojes).
    def session_marcopolo(self, session_id):
        if self.store.get_session(session_id) is None:
            raise CampoError(404, f"sesion {session_id} no encontrada")
        return [_marcopolo_publico(m)
                for m in self.store.session_marcopolo(session_id)]

    def enqueue_marco(self):
        """Encola un Marco a la radiosonda de la sesion activa. 409 si no hay
        sesion capturando de la sonda `radiosonda`."""
        with self._lock:
            session = self.store.current_session()
            if session is None or session.get("sonda") != SONDA_RADIOSONDA:
                raise CampoError(409, "el Marco Polo exige una sesion activa de "
                                      "la sonda radiosonda")
            self._marco_seq = (self._marco_seq % 255) + 1
            seq = self._marco_seq
            # El Marco se registra como pendiente ANTES de llamar a ChirpStack:
            # en Clase C el Polo puede volver muy rapido y, si llegara antes de
            # tener la fila, quedaria como Polo sin Marco y sin RTT.
            marco = self.store.insert_marco(session["id"], seq, ts=time.time())
            dev_eui = self._session_dev_eui(session)
        try:
            self.chirpstack.enqueue_marco(seq, dev_eui=dev_eui)
        except Exception:
            # El Marco nunca salio: se deshace para no dejar un pendiente
            # fantasma. El error sube (ChirpStackError -> 503).
            with self._lock:
                self.store.delete_marco(marco["id"])
            raise
        with self._lock:
            # Tambien en la tabla de downlinks ENVIADOS, para el cruce con el
            # `_dl.csv` de la microSD (que registra el Marco recibido).
            self.store.insert_downlink(session["id"], seq, FPORT_MARCOPOLO,
                                       "marco", ts=marco["enqueued_ts"])
        ack = {"seq": seq, "enqueued_at": marco["enqueued_at"]}
        self.hub.broadcast({"type": "marco_ack", **ack})
        return ack

    def _registrar_polo_locked(self, session, rec):
        """Empareja un Polo (uplink fPort 30) con su Marco y devuelve el mensaje
        WS `polo`, o None si el Polo no trae un seq valido. Se llama con el lock
        tomado, desde la ingesta."""
        obj = _uplink_object(rec)
        seq = _entero(obj.get("seq"))
        if seq is None:
            return None
        mp = self.store.register_polo(
            session["id"], seq, time.time(),
            rssi_dbm=_rs_valor("rssi_dbm", obj.get("rssi_dbm")),
            snr_db=obj.get("snr_db"),
            gw_rssi=rec.get("rssi"), gw_snr=rec.get("snr"),
            f_cnt=rec.get("f_cnt"))
        return {"type": "polo", "seq": seq, "rtt_ms": mp["rtt_ms"],
                "rssi_dbm": mp["rssi_dbm"], "snr_db": mp["snr_db"],
                "gw_rssi": mp["gw_rssi"], "gw_snr": mp["gw_snr"],
                "received_at": mp["received_at"]}

    # --- Ping ---------------------------------------------------------------
    def enqueue_ping(self, origin="manual"):
        """Encola un ping fPort 98 (manual desde /ping o automatico desde el
        ciclo de sesion). Ambos comparten la MISMA secuencia 1..255: es lo que
        la sonda registra en su microSD y lo que hace el cruce no ambiguo.

        Si hay sesion capturando, el envio se PERSISTE ligado a ella (tabla
        downlinks, D-61). Un ping manual sin sesion sigue permitido (diagnostico
        suelto) pero no se persiste: no hay corrida a la que ligarlo."""
        with self._lock:
            session = self.store.current_session()
            if origin != "manual" and session is None:
                # La sesion se cerro entre el tick del ciclo y este envio: el
                # ping automatico solo existe mientras la sesion captura.
                return None
            self._ping_seq = (self._ping_seq % 255) + 1
            seq = self._ping_seq
            # A la sonda de la sesion; sin sesion (ping manual de diagnostico),
            # a la sonda por defecto.
            dev_eui = self._session_dev_eui(session)
        # El encolado real habla con ChirpStack fuera del lock; un fallo sube como
        # ChirpStackError -> 503.
        self.chirpstack.enqueue_ping(seq, dev_eui=dev_eui)
        ts = time.time()
        if session is not None:
            with self._lock:
                self.store.insert_downlink(session["id"], seq, FPORT_PING,
                                           origin, ts=ts)
        self.hub.broadcast({"type": "ping_ack", "seq": seq, "origin": origin})
        return seq

    # --- Ping automatico ligado a la sesion (D-61) --------------------------
    # El pinger suelto de servidor/pinger.py (proceso nohup aparte) no envio un
    # solo ping en toda la campana de agosto-2026. Su funcion vive ahora aqui:
    # mientras la sesion captura, un tick cada config.ping_interval_s encola un
    # ping por el MISMO camino que el /ping manual. La tarea corre en el event
    # loop de FastAPI y se cancela limpiamente al cerrar la sesion (stop/abort/
    # auto-finish) y al apagar el servicio.
    def _start_auto_ping(self, session_id):
        interval = getattr(self.config, "ping_interval_s", 0) or 0
        if interval <= 0:
            return                     # desactivado por configuracion
        loop = self._loop
        if loop is None or not loop.is_running():
            return                     # sin loop (tests de unidad sin app)
        self._cancel_auto_ping()       # nunca dos ciclos a la vez
        self._ping_task = asyncio.run_coroutine_threadsafe(
            self._auto_ping_loop(session_id, interval), loop)

    def _cancel_auto_ping(self):
        task, self._ping_task = self._ping_task, None
        if task is not None:
            # Future de run_coroutine_threadsafe: cancel() es thread-safe y
            # propaga la cancelacion a la corutina en el loop.
            task.cancel()

    async def _auto_ping_loop(self, session_id, interval):
        """Un ping cada `interval` s mientras SU sesion siga capturando. El
        primer ping sale a t+interval (al arrancar la sesion la sonda puede no
        estar transmitiendo todavia)."""
        try:
            while True:
                await asyncio.sleep(interval)
                with self._lock:
                    current = self.store.current_session()
                    if current is None or current["id"] != session_id:
                        return         # la sesion murio: el ciclo muere con ella
                try:
                    # enqueue_ping es sincrono (httpx): a un hilo para no
                    # bloquear el event loop mientras ChirpStack responde.
                    await asyncio.to_thread(self.enqueue_ping, "auto")
                except Exception:
                    # ChirpStack caido en un tick no tumba el ciclo: se
                    # reintenta al siguiente. El operador ve el hueco en la
                    # secuencia de ping_ack.
                    pass
        except asyncio.CancelledError:
            pass                       # cierre limpio de sesion o del servicio

    # --- Perfil -------------------------------------------------------------
    def set_profile(self, profile_key, sonda=SONDA_POR_DEFECTO):
        if profile_key not in PROFILE_IDS:
            raise CampoError(400, f"perfil desconocido: {profile_key}")
        dev_eui = self._dev_eui_sonda((sonda or SONDA_POR_DEFECTO).lower())
        self.chirpstack.set_device_profile(profile_key, dev_eui=dev_eui)
        return profile_key
