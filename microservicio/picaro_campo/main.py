"""
main.py — App FastAPI del microservicio de campo: rutas REST (§6) y WebSocket (§7).

Se construye con una factoria `create_app(...)` para poder inyectar dependencias
en los tests (un ChirpStack falso, sin arrancar MQTT, con una SQLite temporal) y
correr todo con TestClient SIN red real.

Contrato de respuestas (lectura JS-shorthand del contrato):
  {session}          -> {"session": {...}}
  {session, metrics} -> {"session": {...}, "metrics": {...}}
Los errores salen como {"detail": "..."} con el codigo adecuado (400/401/404/
409/503), tanto los de dominio (CampoError) como los de ChirpStack (503).
"""
import csv
import io

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager

from .auth import require_token, ws_token_ok
from .chirpstack import ChirpStackClient, ChirpStackError
from .config import VERSION, Config
from .ingest import MqttIngest
from .models import PosicionRequest, ProfileRequest, StartRequest
from .sessions import CampoError, SessionManager, WsHub
from .store import DL_FIELDS, FIELDS, POS_FIELDS, CampoStore


# Columnas del CSV de uplinks con la distancia medida desde el telefono (D-65).
DIST_TEL_FIELDS = ["tel_lat", "tel_lon", "tel_precision_m", "gw_lat", "gw_lon",
                   "dist_gw_km"]


def create_app(config=None, chirpstack=None, store=None, start_mqtt=True):
    config = config or Config.from_env()
    store = store or CampoStore(config.db_path)
    chirpstack = chirpstack or ChirpStackClient(
        config.chirpstack_api, config.chirpstack_token, config.dev_eui,
        config.profile_ids)
    hub = WsHub()
    manager = SessionManager(store, chirpstack, hub, config)

    # Ingesta MQTT. on_record empuja cada uplink al manager; on_status refleja la
    # conexion (lo que informa /health y exige 'start').
    # Con mas de una sonda configurada se suscribe a TODOS los devices de la
    # aplicacion y el manager se queda solo con los de la sonda de la sesion
    # (D-65). Con una sola, el topic sigue filtrando por su DevEUI. La
    # radiosonda hoy comparte DevEUI con la tbeam (misma placa): no cuenta como
    # device distinto, por eso se comparan los DevEUI y no las sondas.
    euis = {e.lower(): e for e in (config.dev_eui, config.dev_eui_lora32,
                                   config.dev_eui_radiosonda) if e}
    mqtt_dev = next(iter(euis.values())) if len(euis) == 1 else ""
    ingest = MqttIngest(
        host=config.mqtt_host, port=config.mqtt_port, app_id=config.app_id,
        dev_eui=mqtt_dev, on_record=manager.ingest_record,
        on_status=lambda ok, _msg: manager.set_mqtt_connected(ok),
        username=config.mqtt_user, password=config.mqtt_password,
        tls=config.mqtt_tls)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Captura el event loop para que el broadcast (llamado desde el hilo de
        # MQTT / threadpool) pueda agendar envios en el con run_coroutine_threadsafe.
        import asyncio
        manager.attach_loop(asyncio.get_running_loop())
        if start_mqtt:
            ingest.start()
        yield
        manager.shutdown()          # cancela el ping automatico si quedo vivo
        if start_mqtt:
            ingest.stop()
        store.close()

    app = FastAPI(title="PiCARO — microservicio de campo", version=VERSION,
                  lifespan=lifespan)
    app.state.config = config
    app.state.store = store
    app.state.chirpstack = chirpstack
    app.state.hub = hub
    app.state.manager = manager
    app.state.ingest = ingest

    # --- Manejo uniforme de errores ---------------------------------------
    @app.exception_handler(CampoError)
    async def _campo_error(_req: Request, exc: CampoError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(ChirpStackError)
    async def _chirp_error(_req: Request, exc: ChirpStackError):
        # Dependencia externa caida o con error: 503 (§6).
        return JSONResponse(status_code=503, content={"detail": f"ChirpStack: {exc}"})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Request, exc: RequestValidationError):
        # El contrato pide 400 para cuerpos invalidos (FastAPI usa 422 por defecto).
        return JSONResponse(status_code=400, content={"detail": exc.errors()})

    # --- Salud (sin auth) --------------------------------------------------
    @app.get("/health")
    def health():
        return {"status": "ok", "mqtt_connected": manager.mqtt_connected,
                "version": VERSION}

    # --- Sesiones ----------------------------------------------------------
    @app.post("/session/start", status_code=201, dependencies=[Depends(require_token)])
    def session_start(body: StartRequest):
        session = manager.start_session(body.scenario, body.class_, body.sonda)
        return {"session": session}

    @app.post("/session/{session_id}/posicion", status_code=201,
              dependencies=[Depends(require_token)])
    def session_posicion(session_id: int, body: PosicionRequest):
        # Fix del GPS del telefono (D-65): con el se mide la distancia de las
        # sondas sin GPS propio.
        return {"posicion": manager.add_posicion(
            session_id, body.lat, body.lon, body.alt_m, body.precision_m, body.ts)}

    @app.post("/session/{session_id}/abort", dependencies=[Depends(require_token)])
    def session_abort(session_id: int):
        return {"session": manager.abort_session(session_id)}

    @app.post("/session/{session_id}/finish", dependencies=[Depends(require_token)])
    def session_finish(session_id: int):
        return {"session": manager.finish_session(session_id)}

    @app.get("/session/current", dependencies=[Depends(require_token)])
    def session_current():
        session = store.current_session()
        if session is None:
            return {"session": None}
        return {"session": session, "metrics": manager.metrics(session)}

    @app.get("/sessions", dependencies=[Depends(require_token)])
    def sessions_list():
        return [{"session": s, "summary": manager.summary(s)}
                for s in store.all_sessions()]

    @app.get("/sessions/{session_id}", dependencies=[Depends(require_token)])
    def session_detail(session_id: int):
        session = store.get_session(session_id)
        if session is None:
            raise CampoError(404, f"sesion {session_id} no encontrada")
        return {"session": session, "summary": manager.summary(session),
                "metrics": manager.metrics(session)}

    @app.get("/sessions/{session_id}/uplinks", dependencies=[Depends(require_token)])
    def session_uplinks(session_id: int):
        return manager.session_uplinks(session_id)

    @app.get("/sessions/{session_id}/downlinks", dependencies=[Depends(require_token)])
    def session_downlinks(session_id: int):
        # Lado ENVIADO del cruce de latencia (§15.2): pings manuales y
        # automaticos persistidos durante la sesion.
        return manager.session_downlinks(session_id)

    @app.get("/sessions/{session_id}/marcopolo", dependencies=[Depends(require_token)])
    def session_marcopolo(session_id: int):
        # Intercambios Marco Polo de la radiosonda (fPort 30): Marco encolado y,
        # si volvio, su Polo con el RTT y la senal en ambos sentidos.
        return manager.session_marcopolo(session_id)

    @app.get("/sessions/{session_id}/posiciones", dependencies=[Depends(require_token)])
    def session_posiciones(session_id: int):
        return manager.session_posiciones(session_id)

    @app.get("/sessions/{session_id}/posiciones/csv", dependencies=[Depends(require_token)])
    def session_posiciones_csv(session_id: int):
        session = store.get_session(session_id)
        if session is None:
            raise CampoError(404, f"sesion {session_id} no encontrada")
        rows = manager.session_posiciones(session_id)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(POS_FIELDS)
        for r in rows:
            writer.writerow([r.get(c) for c in POS_FIELDS])
        headers = {"Content-Disposition":
                   f'attachment; filename="{session["run_label"]}_pos.csv"'}
        return Response(content=buf.getvalue(), media_type="text/csv", headers=headers)

    @app.delete("/sessions/{session_id}", dependencies=[Depends(require_token)])
    def session_delete(session_id: int):
        # Borrado irreversible de una sesion y sus datos (§6). 409 si captura.
        return manager.delete_session(session_id)

    @app.get("/sessions/{session_id}/csv", dependencies=[Depends(require_token)])
    def session_csv(session_id: int):
        session = store.get_session(session_id)
        if session is None:
            raise CampoError(404, f"sesion {session_id} no encontrada")
        rows = manager.uplinks_con_distancia(session_id)
        # Mismas columnas que el dashboard y, al final, las de la distancia
        # medida desde el telefono (D-65): vacias en las sondas con GPS propio.
        cols = FIELDS + DIST_TEL_FIELDS
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(cols)
        for r in rows:
            writer.writerow([r.get(c) for c in cols])
        # Content-Disposition con el run_label: el fichero que descarga la app se
        # llama como la corrida (§6), asi el operador lo reconoce sin abrirlo.
        headers = {"Content-Disposition":
                   f'attachment; filename="{session["run_label"]}.csv"'}
        return Response(content=buf.getvalue(), media_type="text/csv", headers=headers)

    @app.get("/sessions/{session_id}/downlinks/csv", dependencies=[Depends(require_token)])
    def session_downlinks_csv(session_id: int):
        # CSV del lado ENVIADO, hermano del CSV de uplinks. Se descarga como
        # `<run_label>_dl.csv`, el mismo sufijo `_dl` que ya usa la campana para
        # los ficheros de downlinks, para que el cruce con la microSD sea obvio.
        session = store.get_session(session_id)
        if session is None:
            raise CampoError(404, f"sesion {session_id} no encontrada")
        rows = manager.session_downlinks(session_id)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(DL_FIELDS)
        for r in rows:
            writer.writerow([r.get(c) for c in DL_FIELDS])
        headers = {"Content-Disposition":
                   f'attachment; filename="{session["run_label"]}_dl.csv"'}
        return Response(content=buf.getvalue(), media_type="text/csv", headers=headers)

    # --- Operaciones sobre el device --------------------------------------
    @app.post("/ping", dependencies=[Depends(require_token)])
    def ping():
        return {"seq": manager.enqueue_ping()}

    @app.post("/marco", dependencies=[Depends(require_token)])
    def marco():
        # Marco Polo de la radiosonda (RADIOSONDA-ESPEC): encola el downlink
        # fPort 30 [seq]. 409 sin sesion activa de la sonda radiosonda.
        return manager.enqueue_marco()

    @app.post("/profile", dependencies=[Depends(require_token)])
    def profile(body: ProfileRequest):
        return {"profile": manager.set_profile(body.profile, body.sonda)}

    # --- WebSocket ---------------------------------------------------------
    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        token = websocket.query_params.get("token")
        # Se acepta primero para poder cerrar con code 1008 de forma observable
        # por el cliente si el token no es valido (§7).
        await websocket.accept()
        if not ws_token_ok(token, config.campo_token):
            await websocket.close(code=1008)
            return

        hub.add(websocket)
        try:
            session = store.current_session()
            await hub.send_to(websocket, {
                "type": "hello", "version": VERSION,
                "mqtt_connected": manager.mqtt_connected, "session": session})
            # El control va por REST; aqui solo se drena lo que mande el cliente
            # (un {"type":"pong"} opcional de keepalive) para detectar el cierre.
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            hub.remove(websocket)

    return app


# NO se crea una instancia `app` a nivel de modulo a proposito: create_app() abre
# la SQLite y prepara el MQTT, y no queremos esos efectos por el mero hecho de
# importar el modulo (romperia los tests y cualquier import). En produccion se
# arranca en modo factoria:
#     uvicorn picaro_campo.main:create_app --factory --host 0.0.0.0 --port 8000
# Los tests llaman a create_app(...) con dependencias inyectadas.
