"""
store.py — Capa SQLite del microservicio de campo.

Extiende el esquema de dashboard/storage.py (la "caja negra" de telemetria) con:
  · una columna `session_id` en `telemetry` (FK a sessions.id), para ligar cada
    uplink a la corrida que lo capturo;
  · una tabla `sessions` con la maquina de estados de §3/§4 del contrato.

Se reusan EXACTAMENTE las columnas de telemetria de dashboard/storage.py (mismo
orden, mismos nombres) para que el CSV y el analisis posterior sean compatibles
con lo que ya produce el dashboard. No se reinventa el formato.

Acceso concurrente: la conexion se abre con check_same_thread=False porque a la
SQLite entran el hilo de MQTT (ingesta) y los hilos del threadpool de FastAPI
(endpoints). La serializacion la garantiza un Lock en SessionManager, no aqui;
este modulo es una capa fina de SQL.
"""
import sqlite3
import time
from datetime import datetime, timezone

# Columnas del registro de telemetria: IDENTICAS a dashboard/storage.py::FIELDS.
FIELDS = [
    "ts", "iso", "dev_eui", "f_cnt", "f_port", "rssi", "snr", "gateway_id",
    "freq", "dr", "gps_active", "gps_fix", "latitude", "longitude",
    "altitude_m", "satellites", "battery_v", "battery_pct", "charging",
    "usb_powered", "temperature_c", "pressure_hpa", "raw_json",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_label      TEXT NOT NULL,      -- 20260814-CERRO16-C
    scenario       TEXT NOT NULL,      -- URBANO | TERRAZA | CERRO16 | VUELO | RADIOSONDA
    class          TEXT NOT NULL,      -- A | C
    expected_fport INTEGER NOT NULL,   -- 11..17, 20 (RADIOSONDA: el principal de 20-23/30)
    profile        TEXT NOT NULL,      -- terreno-a | terreno-c | radiosonda-c
    state          TEXT NOT NULL,      -- capturing | finished | aborted
    target_uplinks INTEGER NOT NULL,   -- 300 (VUELO: 165, RADIOSONDA: 16)
    started_at     REAL NOT NULL,      -- epoch UTC
    ended_at       REAL,              -- epoch UTC, null si activa
    notes          TEXT,
    sonda          TEXT NOT NULL DEFAULT 'tbeam',   -- tbeam | lora32 (D-65), radiosonda
    dev_eui        TEXT                -- DevEUI de la sonda; null en sesiones previas a D-65
);

CREATE TABLE IF NOT EXISTS telemetry (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER REFERENCES sessions(id),
    ts            REAL NOT NULL,      -- epoch unix (segundos)
    iso           TEXT,              -- marca de tiempo ISO-8601 UTC
    dev_eui       TEXT,
    f_cnt         INTEGER,
    f_port        INTEGER,
    rssi          INTEGER,
    snr           REAL,
    gateway_id    TEXT,
    freq          INTEGER,
    dr            INTEGER,
    gps_active    INTEGER,
    gps_fix       INTEGER,
    latitude      REAL,
    longitude     REAL,
    altitude_m    REAL,
    satellites    INTEGER,
    battery_v     REAL,
    battery_pct   INTEGER,
    charging      INTEGER,
    usb_powered   INTEGER,
    temperature_c REAL,
    pressure_hpa  REAL,
    raw_json      TEXT
);
CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry(ts);
CREATE INDEX IF NOT EXISTS idx_telemetry_session ON telemetry(session_id);

-- Downlinks ENVIADOS por el microservicio (pings de latencia, D-61). Es el lado
-- "enviado" del cruce con lo que la sonda registra en su microSD: en la campana
-- de agosto-2026 este registro no existio (el pinger suelto nunca corrio y
-- downlinks_enviados.csv quedo como placeholder), asi que el cruce
-- enviados/recibidos era imposible. Ahora cada envio, manual o automatico,
-- queda ligado a su sesion.
CREATE TABLE IF NOT EXISTS downlinks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id),
    seq        INTEGER NOT NULL,   -- numero de secuencia 1..255 (el byte del payload)
    fport      INTEGER NOT NULL,   -- 98 (ping) | 30 (Marco de la radiosonda)
    ts         REAL NOT NULL,      -- epoch UTC del encolado
    iso        TEXT,               -- ISO-8601 UTC con milisegundos (latencia)
    origin     TEXT NOT NULL       -- manual | auto | marco
);
CREATE INDEX IF NOT EXISTS idx_downlinks_session ON downlinks(session_id);

-- Posiciones del TELEFONO del operador (D-65). La T3 no tiene GPS: la distancia
-- de sus sesiones se mide desde donde esta el telefono, que va junto a la sonda.
CREATE TABLE IF NOT EXISTS posiciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES sessions(id),
    ts          REAL NOT NULL,      -- epoch UTC del fix del telefono
    iso         TEXT,
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    alt_m       REAL,
    precision_m REAL                -- radio de precision horizontal (m)
);
CREATE INDEX IF NOT EXISTS idx_posiciones_session ON posiciones(session_id);

-- Intercambios Marco Polo de la radiosonda (fPort 30, RADIOSONDA-ESPEC). Un
-- renglon por Marco encolado; el Polo que vuelve con el mismo seq lo completa
-- (received_*, rtt_ms y la senal). Un Polo sin Marco pendiente (duplicado, o un
-- Marco anterior a un reinicio del servicio) se guarda con enqueued_* null para
-- no perder la medida de senal.
CREATE TABLE IF NOT EXISTS marcopolo (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES sessions(id),
    seq         INTEGER NOT NULL,   -- 1..255, el byte del Marco y del Polo
    enqueued_ts REAL,               -- epoch UTC del encolado del Marco
    enqueued_at TEXT,               -- ISO-8601 UTC con milisegundos
    received_ts REAL,               -- epoch UTC de llegada del Polo al servicio
    received_at TEXT,
    rtt_ms      INTEGER,            -- received_ts - enqueued_ts, en ms
    rssi_dbm    INTEGER,            -- senal con la que la SONDA recibio el Marco
    snr_db      REAL,
    gw_rssi     INTEGER,            -- senal con la que el GATEWAY recibio el Polo
    gw_snr      REAL,
    f_cnt       INTEGER             -- fCnt del uplink del Polo
);
CREATE INDEX IF NOT EXISTS idx_marcopolo_session ON marcopolo(session_id);
"""

# Columnas publicas de un intercambio Marco Polo (GET /sessions/{id}/marcopolo).
MP_FIELDS = ["seq", "enqueued_at", "received_at", "rtt_ms", "rssi_dbm", "snr_db",
             "gw_rssi", "gw_snr"]


def _iso_ms(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds")

# Columnas publicas de un downlink enviado (JSON y CSV `_dl`).
DL_FIELDS = ["seq", "fport", "ts", "iso", "origin"]

# Columnas publicas de una posicion del telefono (JSON y CSV `_pos`).
POS_FIELDS = ["ts", "iso", "lat", "lon", "alt_m", "precision_m"]

# Estados de la maquina de sesion (§3). Se usan como constantes para no repartir
# literales por el codigo.
STATE_CAPTURING = "capturing"
STATE_FINISHED = "finished"
STATE_ABORTED = "aborted"


class CampoStore:
    def __init__(self, path):
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrar()
        self._conn.commit()

    def _migrar(self):
        """Columnas anadidas despues de crear la base de produccion. CREATE
        TABLE IF NOT EXISTS no toca una tabla que ya existe, asi que se anaden
        aqui. Las sesiones viejas quedan como sonda tbeam y dev_eui null, que
        es lo que eran."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(sessions)")}
        if "sonda" not in cols:
            self._conn.execute(
                "ALTER TABLE sessions ADD COLUMN sonda TEXT NOT NULL DEFAULT 'tbeam'")
        if "dev_eui" not in cols:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN dev_eui TEXT")

    # --- Sesiones -----------------------------------------------------------
    def create_session(self, *, run_label, scenario, class_, expected_fport,
                        profile, target_uplinks, started_at=None,
                        sonda="tbeam", dev_eui=None):
        started_at = started_at if started_at is not None else time.time()
        cur = self._conn.execute(
            "INSERT INTO sessions (run_label, scenario, class, expected_fport, "
            "profile, state, target_uplinks, started_at, ended_at, notes, "
            "sonda, dev_eui) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_label, scenario, class_, expected_fport, profile,
             STATE_CAPTURING, target_uplinks, started_at, None, None,
             sonda, dev_eui))
        self._conn.commit()
        return self.get_session(cur.lastrowid)

    def get_session(self, session_id):
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def current_session(self):
        """La (unica) sesion en estado capturing, o None."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE state=? ORDER BY id DESC LIMIT 1",
            (STATE_CAPTURING,)).fetchone()
        return dict(row) if row else None

    def all_sessions(self):
        """Todas, mas reciente primero (§6 GET /sessions)."""
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def set_session_state(self, session_id, state, ended_at=None):
        self._conn.execute(
            "UPDATE sessions SET state=?, ended_at=? WHERE id=?",
            (state, ended_at, session_id))
        self._conn.commit()
        return self.get_session(session_id)

    def delete_session(self, session_id):
        """Borra la sesion y TODOS sus uplinks. Devuelve True si existia.

        Se borran antes los uplinks y downlinks (hijos) para no dejar filas
        huerfanas apuntando a una sesion inexistente."""
        row = self._conn.execute(
            "SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            return False
        self._conn.execute("DELETE FROM telemetry WHERE session_id=?", (session_id,))
        self._conn.execute("DELETE FROM downlinks WHERE session_id=?", (session_id,))
        self._conn.execute("DELETE FROM posiciones WHERE session_id=?", (session_id,))
        self._conn.execute("DELETE FROM marcopolo WHERE session_id=?", (session_id,))
        self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        self._conn.commit()
        return True

    def next_run_label(self, base):
        """Devuelve el run_label libre para `base` (AAAAMMDD-ESCENARIO-CLASE).

        Mismo criterio que el firmware (runlog_asignar_run_id): el primer intento
        del dia/escenario/clase va SIN sufijo; los siguientes anaden -2, -3, ...
        Asi la etiqueta del microservicio y la de la microSD coinciden cuando hay
        un solo intento, que es el caso normal."""
        rows = self._conn.execute(
            "SELECT run_label FROM sessions "
            "WHERE run_label=? OR run_label LIKE ?", (base, base + "-%")).fetchall()
        existing = {r["run_label"] for r in rows}
        n = 1
        while True:
            candidate = base if n == 1 else f"{base}-{n}"
            if candidate not in existing:
                return candidate
            n += 1

    # --- Telemetria ---------------------------------------------------------
    def insert_uplink(self, rec, session_id):
        cols = ["session_id"] + FIELDS
        vals = [session_id] + [rec.get(c) for c in FIELDS]
        placeholders = ",".join("?" * len(cols))
        cur = self._conn.execute(
            f"INSERT INTO telemetry ({','.join(cols)}) VALUES ({placeholders})", vals)
        self._conn.commit()
        return cur.lastrowid

    def session_uplinks(self, session_id):
        """Uplinks de una sesion en orden temporal (para metricas, mapa y CSV)."""
        rows = self._conn.execute(
            "SELECT * FROM telemetry WHERE session_id=? ORDER BY ts ASC, id ASC",
            (session_id,)).fetchall()
        return [dict(r) for r in rows]

    # --- Downlinks enviados (D-61) ------------------------------------------
    def insert_downlink(self, session_id, seq, fport, origin, ts=None):
        """Registra un downlink ENVIADO (ping manual o automatico) ligado a su
        sesion. `iso` va con milisegundos porque es la marca del lado "enviado"
        del calculo de latencia."""
        ts = ts if ts is not None else time.time()
        iso = datetime.fromtimestamp(ts, timezone.utc).isoformat(
            timespec="milliseconds")
        cur = self._conn.execute(
            "INSERT INTO downlinks (session_id, seq, fport, ts, iso, origin) "
            "VALUES (?,?,?,?,?,?)", (session_id, seq, fport, ts, iso, origin))
        self._conn.commit()
        return cur.lastrowid

    def session_downlinks(self, session_id):
        """Downlinks enviados de una sesion en orden temporal (JSON y CSV _dl)."""
        rows = self._conn.execute(
            "SELECT * FROM downlinks WHERE session_id=? ORDER BY ts ASC, id ASC",
            (session_id,)).fetchall()
        return [dict(r) for r in rows]

    # --- Posiciones del telefono (D-65) --------------------------------------
    def insert_posicion(self, session_id, lat, lon, alt_m=None, precision_m=None,
                        ts=None):
        ts = ts if ts is not None else time.time()
        iso = datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")
        cur = self._conn.execute(
            "INSERT INTO posiciones (session_id, ts, iso, lat, lon, alt_m, "
            "precision_m) VALUES (?,?,?,?,?,?,?)",
            (session_id, ts, iso, lat, lon, alt_m, precision_m))
        self._conn.commit()
        row = self._conn.execute("SELECT * FROM posiciones WHERE id=?",
                                 (cur.lastrowid,)).fetchone()
        return dict(row)

    def session_posiciones(self, session_id):
        """Posiciones del telefono de una sesion, en orden temporal."""
        rows = self._conn.execute(
            "SELECT * FROM posiciones WHERE session_id=? ORDER BY ts ASC, id ASC",
            (session_id,)).fetchall()
        return [dict(r) for r in rows]

    # --- Marco Polo de la radiosonda (fPort 30) -------------------------------
    def insert_marco(self, session_id, seq, ts=None):
        """Registra un Marco encolado (pendiente de su Polo). Devuelve la fila."""
        ts = ts if ts is not None else time.time()
        cur = self._conn.execute(
            "INSERT INTO marcopolo (session_id, seq, enqueued_ts, enqueued_at) "
            "VALUES (?,?,?,?)", (session_id, seq, ts, _iso_ms(ts)))
        self._conn.commit()
        return dict(self._conn.execute("SELECT * FROM marcopolo WHERE id=?",
                                       (cur.lastrowid,)).fetchone())

    def delete_marco(self, marco_id):
        """Deshace un Marco cuyo encolado fallo en ChirpStack (nunca salio)."""
        self._conn.execute("DELETE FROM marcopolo WHERE id=?", (marco_id,))
        self._conn.commit()

    def register_polo(self, session_id, seq, received_ts, *, rssi_dbm=None,
                      snr_db=None, gw_rssi=None, gw_snr=None, f_cnt=None):
        """Empareja un Polo con el Marco PENDIENTE mas reciente de ese seq en la
        sesion y lo completa. El mas reciente porque el seq es ciclico 1..255: un
        Marco viejo sin respuesta con el mismo seq no debe robarse el Polo. Sin
        Marco pendiente, guarda el Polo suelto (enqueued_* y rtt_ms null).
        Devuelve la fila resultante."""
        row = self._conn.execute(
            "SELECT * FROM marcopolo WHERE session_id=? AND seq=? "
            "AND enqueued_ts IS NOT NULL AND received_ts IS NULL "
            "ORDER BY id DESC LIMIT 1", (session_id, seq)).fetchone()
        received_at = _iso_ms(received_ts)
        if row is not None:
            rtt = int(round((received_ts - row["enqueued_ts"]) * 1000))
            self._conn.execute(
                "UPDATE marcopolo SET received_ts=?, received_at=?, rtt_ms=?, "
                "rssi_dbm=?, snr_db=?, gw_rssi=?, gw_snr=?, f_cnt=? WHERE id=?",
                (received_ts, received_at, rtt, rssi_dbm, snr_db, gw_rssi,
                 gw_snr, f_cnt, row["id"]))
            mp_id = row["id"]
        else:
            cur = self._conn.execute(
                "INSERT INTO marcopolo (session_id, seq, received_ts, received_at, "
                "rssi_dbm, snr_db, gw_rssi, gw_snr, f_cnt) VALUES (?,?,?,?,?,?,?,?,?)",
                (session_id, seq, received_ts, received_at, rssi_dbm, snr_db,
                 gw_rssi, gw_snr, f_cnt))
            mp_id = cur.lastrowid
        self._conn.commit()
        return dict(self._conn.execute("SELECT * FROM marcopolo WHERE id=?",
                                       (mp_id,)).fetchone())

    def session_marcopolo(self, session_id):
        """Intercambios Marco Polo de una sesion, en orden de creacion."""
        rows = self._conn.execute(
            "SELECT * FROM marcopolo WHERE session_id=? ORDER BY id ASC",
            (session_id,)).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
