"""
test_sondas.py — Varias sondas, una sesion a la vez (D-65).

Cada sesion es de una sonda (`tbeam` por defecto, `lora32` la T3) y todo lo que
toca ChirpStack —perfil, gate de clase, ping— va al DevEUI de esa sonda. La T3
solo admite VUELO-A, y manda los mismos P1/P2/P3 que la T-Beam con los sensores
simulados en el firmware; sin gauge, su bateria llega sin porcentaje.
"""
import sqlite3
from datetime import datetime, timezone

import pytest

from picaro_campo.ingest import parse_chirpstack_up
from picaro_campo.sessions import CampoError, SessionManager, WsHub
from picaro_campo.store import CampoStore
from tests.conftest import FakeChirpStack, auth_headers, make_config, make_uplink
from tests.test_vuelo import vuelo_object

EUI_TBEAM = "0011223344550001"
EUI_T3 = "0011223344550003"


def t3_rec(f_cnt, tipo, rafaga, *, eui=EUI_T3):
    """Uplink de la T3 en VUELO, como lo deja parse_chirpstack_up."""
    obj = vuelo_object(tipo, rafaga)
    if tipo == 2:
        obj["battery_v"], obj["battery_pct"] = 4.12, None   # sin gauge
    return parse_chirpstack_up({
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "deviceInfo": {"devEui": eui},
        "fCnt": f_cnt, "fPort": 17, "dr": 0,
        "rxInfo": [{"rssi": -98, "snr": 4.5, "gatewayId": "gw-pabellon"}],
        "txInfo": {"frequency": 905300000},
        "object": obj,
    })


@pytest.fixture
def manager(tmp_path):
    cfg = make_config(tmp_path / "s.db")
    mgr = SessionManager(CampoStore(str(cfg.db_path)), FakeChirpStack(), WsHub(), cfg)
    mgr.set_mqtt_connected(True)
    return mgr


# --- Start --------------------------------------------------------------------
def test_sin_sonda_es_la_tbeam(client, app):
    """La app <= 2.1.0 no manda `sonda`: sus sesiones siguen siendo de la T-Beam."""
    r = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                    headers=auth_headers())
    assert r.status_code == 201
    s = r.json()["session"]
    assert s["sonda"] == "tbeam" and s["dev_eui"] == EUI_TBEAM
    chirp = app.state.chirpstack
    assert chirp.profile_euis[-1] == EUI_TBEAM
    assert chirp.class_euis[-1] == EUI_TBEAM


def test_lora32_vuelo_a(client, app):
    r = client.post("/session/start",
                    json={"scenario": "VUELO", "class": "A", "sonda": "lora32"},
                    headers=auth_headers())
    assert r.status_code == 201
    s = r.json()["session"]
    assert s["sonda"] == "lora32" and s["dev_eui"] == EUI_T3
    assert s["expected_fport"] == 17 and s["profile"] == "terreno-a"
    chirp = app.state.chirpstack
    assert chirp.profile_euis[-1] == EUI_T3    # el perfil se pone a la T3...
    assert chirp.class_euis[-1] == EUI_T3      # ...y el gate mira la T3


@pytest.mark.parametrize("scenario,class_", [("URBANO", "A"), ("CERRO16", "C"),
                                             ("TERRAZA", "A")])
def test_lora32_rechaza_las_demas_corridas(client, app, scenario, class_):
    r = client.post("/session/start",
                    json={"scenario": scenario, "class": class_, "sonda": "lora32"},
                    headers=auth_headers())
    assert r.status_code == 400
    assert "no admite" in r.json()["detail"]
    assert app.state.chirpstack.profile_calls == []   # no toco ChirpStack


def test_sonda_desconocida(client):
    r = client.post("/session/start",
                    json={"scenario": "VUELO", "class": "A", "sonda": "heltec"},
                    headers=auth_headers())
    assert r.status_code == 400


def test_sonda_sin_dev_eui_en_el_servidor(tmp_path):
    cfg = make_config(tmp_path / "x.db")
    cfg.dev_eui_lora32 = ""
    mgr = SessionManager(CampoStore(str(cfg.db_path)), FakeChirpStack(), WsHub(), cfg)
    mgr.set_mqtt_connected(True)
    with pytest.raises(CampoError) as e:
        mgr.start_session("VUELO", "A", "lora32")
    assert e.value.status_code == 400 and "no esta configurada" in e.value.detail


# --- Ingesta ------------------------------------------------------------------
def test_sesion_lora32_ignora_a_la_tbeam(manager):
    manager.start_session("VUELO", "A", "lora32")
    # La T-Beam encendida a la vez, incluso en el mismo fPort: no es de esta sesion.
    assert manager.ingest_record(make_uplink(5, 17)) is None
    assert manager.ingest_record(t3_rec(0, 1, 0)) is not None
    s = manager.store.current_session()
    assert manager.metrics(s)["received"] == 1


def test_sesion_tbeam_ignora_a_la_t3(manager):
    manager.start_session("VUELO", "A")
    assert manager.ingest_record(t3_rec(0, 1, 0)) is None
    assert manager.ingest_record(make_uplink(1, 17)) is not None


def test_metricas_vuelo_de_la_t3(manager):
    """Rafagas por tipo y bateria en V sin porcentaje. Sin posiciones del
    telefono no hay distancia: la del P1 es simulada y no cuenta."""
    manager.start_session("VUELO", "A", "lora32")
    f = 0
    for rafaga in range(2):
        for tipo in (1, 2, 3):
            if (rafaga, tipo) == (1, 2):
                f += 1
                continue                       # se pierde P2 de la rafaga 1
            manager.ingest_record(t3_rec(f, tipo, rafaga))
            f += 1
    m = manager.metrics(manager.store.current_session())
    assert m["received"] == 5 and m["gaps"] == 1
    assert m["vuelo"]["rafagas_completas"] == 1
    assert m["vuelo"]["rafagas_parciales"] == 1
    assert m["battery_v"] == 4.12 and m["battery_pct"] is None
    assert m["dist_gw_km_max"] is None and m["gps_fix"] is True


def test_ping_va_a_la_sonda_de_la_sesion(manager):
    manager.start_session("VUELO", "A", "lora32")
    manager.enqueue_ping()
    assert manager.chirpstack.ping_euis[-1] == EUI_T3


def test_ping_sin_sesion_va_a_la_tbeam(manager):
    manager.enqueue_ping()
    assert manager.chirpstack.ping_euis[-1] == EUI_TBEAM


def test_profile_por_sonda(client, app):
    r = client.post("/profile", json={"profile": "terreno-a", "sonda": "lora32"},
                    headers=auth_headers())
    assert r.status_code == 200
    assert app.state.chirpstack.profile_euis[-1] == EUI_T3


# --- Migracion de la SQLite de produccion -----------------------------------
def test_base_anterior_a_d65_se_migra(tmp_path):
    """La base de produccion ya existe sin las columnas nuevas: al abrirla se
    anaden, y las sesiones viejas quedan como de la T-Beam."""
    db = tmp_path / "vieja.db"
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_label TEXT NOT NULL,
        scenario TEXT NOT NULL, class TEXT NOT NULL, expected_fport INTEGER NOT NULL,
        profile TEXT NOT NULL, state TEXT NOT NULL, target_uplinks INTEGER NOT NULL,
        started_at REAL NOT NULL, ended_at REAL, notes TEXT)""")
    con.execute("INSERT INTO sessions (run_label, scenario, class, expected_fport, "
                "profile, state, target_uplinks, started_at) VALUES "
                "('20260929-VUELO-A','VUELO','A',17,'terreno-a','finished',165,1.0)")
    con.commit()
    con.close()

    store = CampoStore(str(db))
    vieja = store.get_session(1)
    assert vieja["sonda"] == "tbeam" and vieja["dev_eui"] is None
    nueva = store.create_session(run_label="x", scenario="VUELO", class_="A",
                                 expected_fport=17, profile="terreno-a",
                                 target_uplinks=165, sonda="lora32", dev_eui=EUI_T3)
    assert nueva["sonda"] == "lora32"
