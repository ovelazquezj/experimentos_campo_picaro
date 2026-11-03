"""SQLite: historial de uplinks (purga a N dias) y ultima posicion conocida.

Todo se guarda por ID publico; la base no contiene DevEUIs.
"""
import json
import sqlite3
import threading
import time
from datetime import datetime

MAX_PUNTOS = 1500     # puntos por serie que se mandan al navegador
ULTIMOS = 30          # uplinks completos para la tabla de "ultimos mensajes"


def _ms(iso):
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
    except (AttributeError, ValueError):
        return int(time.time() * 1000)


def _numericos(datos, prefijo=""):
    out = {}
    if not isinstance(datos, dict):
        return out
    for k, v in datos.items():
        clave = f"{prefijo}{k}"
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out[clave] = v
        elif isinstance(v, dict) and not prefijo:
            out.update(_numericos(v, clave + "."))
    return out


class Store:
    def __init__(self, ruta: str, dias: int):
        self.dias = dias
        self.lock = threading.Lock()
        self.db = sqlite3.connect(ruta, check_same_thread=False)
        self.db.execute("pragma journal_mode=wal")
        self.db.executescript(
            """
            create table if not exists uplink(nodo text, ts integer, fcnt integer, reg text);
            create index if not exists uplink_nodo_ts on uplink(nodo, ts);
            create table if not exists posicion(nodo text primary key, lat real, lon real, alt real, ts integer);
            """
        )

    def guardar(self, nodo: str, reg: dict):
        ts = _ms(reg.get("ts"))
        reg["ts"] = ts
        with self.lock, self.db:
            self.db.execute("insert into uplink values (?,?,?,?)",
                            (nodo, ts, reg.get("fcnt"), json.dumps(reg, ensure_ascii=False)))
            if reg.get("pos"):
                p = reg["pos"]
                self.db.execute("insert or replace into posicion values (?,?,?,?,?)",
                                (nodo, p["lat"], p["lon"], p["alt"], ts))
        return reg

    def ultimo(self, nodo: str):
        with self.lock:
            f = self.db.execute("select reg from uplink where nodo=? order by ts desc limit 1", (nodo,)).fetchone()
        return json.loads(f[0]) if f else None

    def posicion(self, nodo: str):
        with self.lock:
            f = self.db.execute("select lat, lon, alt, ts from posicion where nodo=?", (nodo,)).fetchone()
        return {"lat": f[0], "lon": f[1], "alt": f[2], "ts": f[3]} if f else None

    def purgar(self):
        limite = int((time.time() - self.dias * 86400) * 1000)
        with self.lock, self.db:
            # Se conserva siempre el ultimo uplink de cada nodo: sin el, un nodo apagado
            # mas de N dias pareceria "sin datos" y volveria al mapa.
            self.db.execute(
                "delete from uplink where ts < ? and rowid not in (select max(rowid) from uplink group by nodo)",
                (limite,))

    def historial(self, nodo: str):
        desde = int((time.time() - self.dias * 86400) * 1000)
        with self.lock:
            filas = self.db.execute(
                "select ts, fcnt, reg from uplink where nodo=? and ts>=? order by ts", (nodo, desde)
            ).fetchall()

        perdidos, previo = 0, None
        for _, fcnt, _ in filas:
            if fcnt is not None and previo is not None and fcnt > previo:
                perdidos += fcnt - previo - 1
            previo = fcnt   # fCnt menor o igual = rejoin/reinicio: no cuenta como perdida

        paso = max(1, -(-len(filas) // MAX_PUNTOS))
        muestra = filas[::paso]
        if filas and muestra[-1] is not filas[-1]:
            muestra.append(filas[-1])
        serie = {"ts": [], "rssi": [], "snr": [], "margen": []}
        campos = {}
        for i, (ts, _, txt) in enumerate(muestra):
            reg = json.loads(txt)
            serie["ts"].append(ts / 1000)
            for k in ("rssi", "snr", "margen"):
                serie[k].append(reg.get(k))
            for k, v in _numericos(reg.get("datos")).items():
                campos.setdefault(k, [None] * i).append(v)
            for k in campos:
                if len(campos[k]) < i + 1:
                    campos[k].append(None)
        serie["campos"] = campos

        return {
            "dias": self.dias,
            "uplinks": len(filas),
            "perdidos": perdidos,
            "serie": serie,
            "ultimos": [json.loads(t) for _, _, t in filas[-ULTIMOS:]][::-1],
        }
