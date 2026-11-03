"""picaro-mapa: mapa publico de los dispositivos del tenant Proyecto PiCARO.

  MQTT (solo lectura, event/up)  ->  filtro tenant + tag publico  ->  SQLite
                                                                  ->  SSE a navegadores
  Postgres (solo lectura)  ->  catalogo cada CATALOGO_SEG (nombres, tags, gateways)

Un solo worker: el catalogo y los clientes SSE viven en memoria del proceso.
"""
import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import catalogo as catmod
from . import config, procesar
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("mapa")

MAX_CLIENTES = 500
ESTATICO = Path(__file__).parent / "static"


class Estado:
    def __init__(self, cfg):
        self.cfg = cfg
        self.store = Store(cfg.db_path, cfg.historial_dias)
        self.cat = catmod.Catalogo()
        self.gw_vistos = {}              # eui -> (lat, lon) reportada en rxInfo
        self.clientes: set[asyncio.Queue] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    # ----------------------------------------------------------- vistas publicas
    def pid(self, eui):
        return procesar.id_publico(self.cfg.id_secret, eui)

    def nodo(self, d: catmod.Dispositivo):
        nid = self.pid(d.eui)
        pos = self.store.posicion(nid)
        if pos:
            pos["origen"] = "payload"
        else:
            pos = {"lat": self.cfg.itpa_lat, "lon": self.cfg.itpa_lon, "alt": None, "ts": None, "origen": "itpa"}
        return {
            "id": nid, "proyecto": d.proyecto, "nombre": d.nombre, "perfil": d.perfil,
            "tiene_codec": d.tiene_codec, "pos": pos, "ultimo": self.store.ultimo(nid),
        }

    def gateways(self):
        out = []
        for eui, g in self.cat.gateways.items():
            lat, lon = (g.lat, g.lon) if g.lat is not None else self.gw_vistos.get(eui, (None, None))
            if lat is not None:
                out.append({"id": self.pid(eui), "nombre": g.nombre, "lat": lat, "lon": lon})
        return out

    def resumen(self):
        return {
            "itpa": {"lat": self.cfg.itpa_lat, "lon": self.cfg.itpa_lon},
            "historial_dias": self.cfg.historial_dias,
            "nodos": [self.nodo(d) for d in self.cat.dispositivos.values()],
            "gateways": self.gateways(),
        }

    def por_id(self, nid):
        return next((d for d in self.cat.dispositivos.values() if self.pid(d.eui) == nid), None)

    # ----------------------------------------------------------- difusion SSE
    def emitir(self, tipo, datos):
        if not self.loop:
            return
        msg = f"event: {tipo}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"

        def _a_todos():
            for q in list(self.clientes):
                if q.full():
                    continue          # cliente lento: se salta, se pondra al dia con /api/estado
                q.put_nowait(msg)
        self.loop.call_soon_threadsafe(_a_todos)

    # ----------------------------------------------------------- MQTT
    def al_mensaje(self, _c, _u, m):
        try:
            ev = json.loads(m.payload)
        except ValueError:
            return
        info = ev.get("deviceInfo") or {}
        if info.get("tenantId") != self.cfg.tenant_id:
            return
        self.gw_vistos.update(procesar.ubicaciones_gw(ev))
        d = self.cat.dispositivos.get((info.get("devEui") or "").lower())
        if not d:
            return                    # no publico: ni se guarda
        nombres = {e: g.nombre for e, g in self.cat.gateways.items()}
        reg = procesar.construir_registro(ev, nombres, self.cfg.id_secret, d.tags_perfil)
        self.store.guardar(self.pid(d.eui), reg)
        self.emitir("uplink", self.nodo(d))

    def arrancar_mqtt(self):
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="picaro-mapa", clean_session=True)
        c.username_pw_set(self.cfg.mqtt_user, self.cfg.mqtt_pass)
        c.on_connect = lambda cl, *_: cl.subscribe("application/+/device/+/event/up", qos=0)
        c.on_message = self.al_mensaje
        c.reconnect_delay_set(1, 30)
        c.connect_async(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=60)
        c.loop_start()
        return c

    # ----------------------------------------------------------- catalogo
    def refrescar(self):
        nuevo = catmod.leer(self.cfg.pg_dsn, self.cfg.tenant_id)
        cambio = set(nuevo.dispositivos) != set(self.cat.dispositivos)
        self.cat = nuevo
        return cambio

    def bucle_catalogo(self, parar: threading.Event):
        ultima_purga = 0.0
        while not parar.wait(self.cfg.catalogo_seg):
            try:
                if self.refrescar():
                    log.info("catalogo cambiado: %d dispositivos publicos", len(self.cat.dispositivos))
                    self.emitir("catalogo", {})
                if time.time() - ultima_purga > 3600:
                    self.store.purgar()
                    ultima_purga = time.time()
            except Exception:
                log.exception("fallo al refrescar el catalogo")


def create_app() -> FastAPI:
    est = Estado(config.cargar())

    @asynccontextmanager
    async def ciclo(_app):
        est.loop = asyncio.get_running_loop()
        try:
            est.refrescar()
        except Exception:
            log.exception("catalogo inicial no disponible; se reintenta en el siguiente ciclo")
        est.store.purgar()
        log.info("%d dispositivos publicos", len(est.cat.dispositivos))
        parar = threading.Event()
        threading.Thread(target=est.bucle_catalogo, args=(parar,), daemon=True).start()
        cliente = est.arrancar_mqtt()
        yield
        parar.set()
        cliente.loop_stop()

    app = FastAPI(lifespan=ciclo, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/api/estado")
    def estado():
        return JSONResponse(est.resumen(), headers={"Cache-Control": "no-store"})

    @app.get("/api/nodo/{nid}/historial")
    def historial(nid: str):
        if not est.por_id(nid):
            raise HTTPException(404, "nodo no encontrado")
        return JSONResponse(est.store.historial(nid), headers={"Cache-Control": "no-store"})

    @app.get("/api/eventos")
    async def eventos(req: Request):
        if len(est.clientes) >= MAX_CLIENTES:
            raise HTTPException(503, "demasiados clientes")
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        est.clientes.add(q)

        async def flujo():
            try:
                yield "retry: 5000\n\n"
                while not await req.is_disconnected():
                    try:
                        yield await asyncio.wait_for(q.get(), timeout=20)
                    except asyncio.TimeoutError:
                        yield ": vivo\n\n"
            finally:
                est.clientes.discard(q)

        return StreamingResponse(flujo(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @app.get("/salud")
    def salud():
        return {"ok": True, "publicos": len(est.cat.dispositivos), "clientes": len(est.clientes)}

    app.mount("/", StaticFiles(directory=ESTATICO, html=True), name="estatico")
    return app
