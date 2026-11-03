"""
test_api.py — Tests de la API REST y el WebSocket con TestClient, sin red real.

Los uplinks se simulan llamando directamente a
`app.state.manager.ingest_record(rec)` (lo que en produccion haria el hilo de
MQTT). ChirpStack esta mockeado (FakeChirpStack). Cubre: auth 401, ciclo
start->uplinks->metrics->finish, 409 de doble sesion, fport_mismatch, CSV,
auto-finish al objetivo y los 503 de dependencias caidas.
"""
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from picaro_campo.chirpstack import ChirpStackError
from tests.conftest import (FakeChirpStack, TOKEN, auth_headers, make_config,
                            make_uplink)


# --- Salud y auth ------------------------------------------------------------
def test_health_sin_auth(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mqtt_connected"] is True
    assert body["version"]


def test_auth_falta_token(client):
    assert client.get("/sessions").status_code == 401


def test_auth_token_malo(client):
    r = client.get("/sessions", headers=auth_headers("otro"))
    assert r.status_code == 401


# --- Ciclo completo start -> uplinks -> metrics -> finish --------------------
def test_ciclo_completo(client, app):
    r = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                    headers=auth_headers())
    assert r.status_code == 201
    session = r.json()["session"]
    assert session["expected_fport"] == 11
    assert session["profile"] == "terreno-a"
    assert session["class"] == "A"          # la clave del wire es 'class'
    assert session["state"] == "capturing"
    assert session["run_label"].endswith("-URBANO-A")
    # 'start' cambio el perfil via ChirpStack.
    assert app.state.chirpstack.profile_calls == ["terreno-a"]

    sid = session["id"]
    # 3 uplinks con hueco en fCnt=3 (llegan 1,2,4) -> pdr_est = 3/4 = 0.75.
    app.state.manager.ingest_record(make_uplink(1, 11))
    app.state.manager.ingest_record(make_uplink(2, 11, battery_pct=None))
    app.state.manager.ingest_record(make_uplink(4, 11))

    m = client.get("/session/current", headers=auth_headers()).json()["metrics"]
    assert m["received"] == 3
    assert m["last_fcnt"] == 4
    assert m["gaps"] == 1
    assert m["pdr_est"] == 0.75
    assert m["expected_fport"] == 11
    assert m["battery_pct"] is None          # null NO se convierte en 0
    assert m["dist_gw_km_max"] is not None and m["dist_gw_km_max"] > 0
    assert m["rssi_last"] == -118

    r = client.post(f"/session/{sid}/finish", headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["session"]["state"] == "finished"

    # Ya no hay sesion activa.
    assert client.get("/session/current", headers=auth_headers()).json()["session"] is None

    detail = client.get(f"/sessions/{sid}", headers=auth_headers()).json()
    assert detail["summary"]["received"] == 3
    assert detail["summary"]["state"] == "finished"


# --- 409: una sola sesion capturando a la vez -------------------------------
def test_doble_sesion_409(client):
    client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                headers=auth_headers())
    r = client.post("/session/start", json={"scenario": "TERRAZA", "class": "C"},
                    headers=auth_headers())
    assert r.status_code == 409
    assert "detail" in r.json()


# --- Desajuste de fPort ------------------------------------------------------
def test_fport_mismatch_no_se_guarda(client, app):
    r = client.post("/session/start", json={"scenario": "CERRO16", "class": "C"},
                    headers=auth_headers())     # expected_fport = 16
    sid = r.json()["session"]["id"]

    # Uplink de OTRA corrida (fPort 15): genera warning y NO se guarda.
    app.state.manager.ingest_record(make_uplink(1, 15))

    warnings = [msg for msg in app.state.hub.history if msg.get("type") == "warning"]
    assert warnings, "deberia haberse emitido un warning por WS"
    assert warnings[-1]["kind"] == "fport_mismatch"
    assert warnings[-1]["expected"] == 16
    assert warnings[-1]["got"] == 15

    # No se guardo nada en la sesion.
    assert client.get("/session/current", headers=auth_headers()).json()["metrics"]["received"] == 0
    assert client.get(f"/sessions/{sid}/uplinks", headers=auth_headers()).json() == []


# --- Auto-finalizacion al alcanzar el objetivo ------------------------------
def test_auto_finish_al_objetivo(client, app):
    r = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                    headers=auth_headers())
    sid = r.json()["session"]["id"]

    app.state.manager.ingest_record(make_uplink(1, 11))   # primer uplink de la corrida
    assert client.get("/session/current", headers=auth_headers()).json()["session"] is not None

    # Cuando el RANGO de fCnt desde el inicio alcanza el objetivo (fCnt 1..300 =
    # 300 enviados), la sesion se cierra sola. Es el rango, no el fCnt absoluto.
    app.state.manager.ingest_record(make_uplink(300, 11))

    assert client.get("/session/current", headers=auth_headers()).json()["session"] is None
    assert client.get(f"/sessions/{sid}", headers=auth_headers()).json()["session"]["state"] == "finished"
    # Con la sesion cerrada, se puede arrancar otra.
    assert client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                       headers=auth_headers()).status_code == 201


# --- Borrado de sesion -------------------------------------------------------
def test_delete_sesion(client, app):
    r = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                    headers=auth_headers())
    sid = r.json()["session"]["id"]
    app.state.manager.ingest_record(make_uplink(1, 11))

    # No se puede borrar mientras captura.
    assert client.delete(f"/sessions/{sid}", headers=auth_headers()).status_code == 409

    client.post(f"/session/{sid}/finish", headers=auth_headers())
    # Ya finalizada: se borra (con sus uplinks) y desaparece de la lista.
    assert client.delete(f"/sessions/{sid}", headers=auth_headers()).status_code == 200
    assert client.get(f"/sessions/{sid}", headers=auth_headers()).status_code == 404
    # Sus uplinks tambien dejan de existir: la sesion ya no esta -> 404.
    assert client.get(f"/sessions/{sid}/uplinks", headers=auth_headers()).status_code == 404
    assert all(s["session"]["id"] != sid
               for s in client.get("/sessions", headers=auth_headers()).json())


def test_delete_inexistente(client):
    assert client.delete("/sessions/9999", headers=auth_headers()).status_code == 404


def test_delete_requiere_token(client):
    assert client.delete("/sessions/1").status_code == 401


# --- CSV ---------------------------------------------------------------------
def test_csv_con_run_label(client, app):
    r = client.post("/session/start", json={"scenario": "TERRAZA", "class": "C"},
                    headers=auth_headers())
    session = r.json()["session"]
    sid = session["id"]
    run_label = session["run_label"]

    app.state.manager.ingest_record(make_uplink(1, 14))
    app.state.manager.ingest_record(make_uplink(2, 14))

    r = client.get(f"/sessions/{sid}/csv", headers=auth_headers())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert f'filename="{run_label}.csv"' in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("ts,iso,dev_eui,f_cnt,f_port")   # cabecera del dashboard
    assert len(lines) == 3                                      # cabecera + 2 filas


# --- Gate de clase (D-60): la sesion NO se abre con la clase desajustada -----
def test_start_409_si_clase_desajustada(client, app):
    # El device hizo su JOIN cuando el perfil activo era Clase C (corrida
    # anterior): ChirpStack lo tiene congelado en C (issue #360) aunque 'start'
    # acabe de poner terreno-a.
    app.state.chirpstack.enabled_class = "C"
    r = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                    headers=auth_headers())
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "clase desajustada" in detail          # prefijo que la app detecta
    assert "rehaga el JOIN" in detail             # recuperacion primaria (D-62)
    assert "apaga y enciende" in detail           # respaldo manual (boton)
    # El perfil SI quedo puesto: es lo que hace que baste con rehacer el JOIN.
    assert app.state.chirpstack.profile_calls == ["terreno-a"]
    # No quedo ninguna sesion abierta.
    assert client.get("/session/current", headers=auth_headers()).json()["session"] is None
    # Y la app tambien lo ve por WS.
    warns = [m for m in app.state.hub.history if m.get("type") == "warning"]
    assert warns and warns[-1]["kind"] == "class_mismatch"
    assert warns[-1]["expected"] == "A" and warns[-1]["got"] == "C"

    # Tras "apagar y encender" (join nuevo con el perfil ya puesto), la clase
    # efectiva coincide y el mismo start entra.
    app.state.chirpstack.enabled_class = "A"
    assert client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                       headers=auth_headers()).status_code == 201


def test_start_pasa_con_aviso_si_clase_no_verificable(client, app):
    # ChirpStack viejo sin classEnabled: no se bloquea la campana, pero se avisa.
    app.state.chirpstack.enabled_class = None
    r = client.post("/session/start", json={"scenario": "URBANO", "class": "C"},
                    headers=auth_headers())
    assert r.status_code == 201
    warns = [m for m in app.state.hub.history if m.get("type") == "warning"]
    assert warns and warns[-1]["kind"] == "class_unverified"
    assert warns[-1]["expected"] == "C"


# --- 503 por dependencias caidas --------------------------------------------
def test_start_503_si_mqtt_desconectado(client, app):
    app.state.manager.set_mqtt_connected(False)
    r = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                    headers=auth_headers())
    assert r.status_code == 503
    app.state.manager.set_mqtt_connected(True)


def test_start_503_si_chirpstack_cae(client, app):
    app.state.chirpstack.fail = ChirpStackError("api caida")
    r = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                    headers=auth_headers())
    assert r.status_code == 503


def test_profile_503_si_chirpstack_cae(client, app):
    app.state.chirpstack.fail = ChirpStackError("api caida")
    r = client.post("/profile", json={"profile": "terreno-c"}, headers=auth_headers())
    assert r.status_code == 503


# --- Validacion de entrada (400) --------------------------------------------
def test_start_escenario_invalido_400(client):
    r = client.post("/session/start", json={"scenario": "MARTE", "class": "A"},
                    headers=auth_headers())
    assert r.status_code == 400


def test_start_cuerpo_incompleto_400(client):
    r = client.post("/session/start", json={"scenario": "URBANO"},
                    headers=auth_headers())
    assert r.status_code == 400


def test_profile_invalido_400(client):
    r = client.post("/profile", json={"profile": "no-existe"}, headers=auth_headers())
    assert r.status_code == 400


# --- Ping y perfil (camino feliz) -------------------------------------------
def test_ping_devuelve_seq_incremental(client, app):
    client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                headers=auth_headers())          # reinicia la secuencia a 0
    assert client.post("/ping", headers=auth_headers()).json()["seq"] == 1
    assert client.post("/ping", headers=auth_headers()).json()["seq"] == 2
    assert app.state.chirpstack.ping_calls == [1, 2]


def test_ping_sin_sesion_no_persiste(client, app):
    # Ping manual de diagnostico sin sesion: se envia pero no hay corrida a la
    # que ligarlo, asi que no queda en ninguna tabla.
    assert client.post("/ping", headers=auth_headers()).status_code == 200
    sid = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                      headers=auth_headers()).json()["session"]["id"]
    assert client.get(f"/sessions/{sid}/downlinks", headers=auth_headers()).json() == []


# --- Downlinks enviados: persistencia y export (D-61) ------------------------
def test_export_incluye_downlinks_enviados(client, app):
    r = client.post("/session/start", json={"scenario": "TERRAZA", "class": "C"},
                    headers=auth_headers())
    session = r.json()["session"]
    sid, run_label = session["id"], session["run_label"]

    # Dos pings manuales durante la captura: se persisten ligados a la sesion.
    assert client.post("/ping", headers=auth_headers()).json()["seq"] == 1
    assert client.post("/ping", headers=auth_headers()).json()["seq"] == 2

    dls = client.get(f"/sessions/{sid}/downlinks", headers=auth_headers()).json()
    assert [d["seq"] for d in dls] == [1, 2]
    assert all(d["fport"] == 98 for d in dls)
    assert all(d["origin"] == "manual" for d in dls)
    assert all(d["iso"] for d in dls)

    # CSV hermano del de uplinks, con el sufijo _dl de la campana.
    r = client.get(f"/sessions/{sid}/downlinks/csv", headers=auth_headers())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert f'filename="{run_label}_dl.csv"' in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "seq,fport,ts,iso,origin"
    assert len(lines) == 3                       # cabecera + 2 envios

    # El ping_ack del WS lleva ahora el origen.
    acks = [m for m in app.state.hub.history if m.get("type") == "ping_ack"]
    assert acks[-1]["origin"] == "manual"


def test_downlinks_de_sesion_inexistente_404(client):
    assert client.get("/sessions/9999/downlinks", headers=auth_headers()).status_code == 404
    assert client.get("/sessions/9999/downlinks/csv", headers=auth_headers()).status_code == 404


# --- Ping automatico ligado a la sesion (D-61) -------------------------------
def test_auto_ping_dispara_persiste_y_muere_con_la_sesion(tmp_path):
    """Con un intervalo inyectado de milisegundos (no se duerme 60 s): mientras
    la sesion captura caen pings automaticos, persistidos y con la secuencia
    compartida; al cerrar la sesion el ciclo muere."""
    from fastapi.testclient import TestClient

    from picaro_campo.main import create_app
    from picaro_campo.store import CampoStore

    cfg = make_config(tmp_path / "campo.db", ping_interval_s=0.05)
    chirp = FakeChirpStack()
    store = CampoStore(str(cfg.db_path))
    application = create_app(config=cfg, chirpstack=chirp, store=store,
                             start_mqtt=False)
    with TestClient(application) as client:
        application.state.manager.set_mqtt_connected(True)
        r = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                        headers=auth_headers())
        assert r.status_code == 201
        sid = r.json()["session"]["id"]

        # Espera activa (con tope) a que el ciclo dispare al menos 2 pings.
        deadline = time.time() + 5.0
        while time.time() < deadline and len(chirp.ping_calls) < 2:
            time.sleep(0.01)
        assert len(chirp.ping_calls) >= 2, "el ping automatico no disparo"

        # Persistidos como 'auto', con la secuencia 1..n del camino compartido.
        dls = client.get(f"/sessions/{sid}/downlinks", headers=auth_headers()).json()
        assert dls, "los pings automaticos no se persistieron"
        assert all(d["origin"] == "auto" and d["fport"] == 98 for d in dls)
        assert [d["seq"] for d in dls] == list(range(1, len(dls) + 1))

        # Al cerrar la sesion, el ciclo muere: no caen mas pings.
        assert client.post(f"/session/{sid}/finish",
                           headers=auth_headers()).status_code == 200
        time.sleep(0.15)                  # deja aterrizar un tick en vuelo
        enviados = len(chirp.ping_calls)
        time.sleep(0.30)                  # varios intervalos despues...
        assert len(chirp.ping_calls) == enviados, \
            "el ping automatico siguio vivo tras cerrar la sesion"


def test_profile_ok(client, app):
    r = client.post("/profile", json={"profile": "ej09"}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["profile"] == "ej09"
    assert app.state.chirpstack.profile_calls == ["ej09"]


# --- WebSocket ---------------------------------------------------------------
def test_ws_token_malo_cierra_1008(client):
    with pytest.raises(WebSocketDisconnect) as ei:
        with client.websocket_connect("/ws?token=incorrecto") as ws:
            ws.receive_text()
    assert ei.value.code == 1008


def test_ws_hello_con_token_bueno(client):
    with client.websocket_connect(f"/ws?token={TOKEN}") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "hello"
    assert msg["mqtt_connected"] is True
    assert msg["session"] is None
    assert msg["version"]
