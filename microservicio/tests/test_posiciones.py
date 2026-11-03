"""
test_posiciones.py — Distancia medida con el GPS del telefono (D-65).

La T3 no tiene GPS: la app manda las posiciones del telefono a la sesion y el
servicio mide, para cada uplink, la distancia entre la posicion mas cercana en el
tiempo y el gateway que lo recibio (coordenadas de ChirpStack; si no las tiene,
GW_LAT/GW_LON). La posicion que traiga el payload no cuenta. La T-Beam no cambia.
"""
import csv
import io

import pytest

from picaro_campo.sessions import (CampoError, SessionManager, WsHub,
                                   haversine_km, posicion_cercana)
from picaro_campo.store import CampoStore
from tests.conftest import FakeChirpStack, auth_headers, make_config, make_uplink
from tests.test_sondas import t3_rec

GW_PABELLON = "00800000a0000003"
GW_LAB = "00800000a0000001"
LOC_PABELLON = (22.1614, -102.2690)
TEL = (22.1900, -102.2800)          # el telefono, a ~3,4 km del Kerlink


@pytest.fixture
def manager(tmp_path):
    cfg = make_config(tmp_path / "p.db")
    chirp = FakeChirpStack()
    chirp.gateway_locations = {GW_PABELLON: LOC_PABELLON}
    mgr = SessionManager(CampoStore(str(cfg.db_path)), chirp, WsHub(), cfg)
    mgr.set_mqtt_connected(True)
    return mgr


def _t3(f_cnt, tipo, rafaga, ts, gw=GW_PABELLON):
    rec = t3_rec(f_cnt, tipo, rafaga)
    rec["ts"] = ts
    rec["gateway_id"] = gw
    return rec


# --- Emparejado temporal ------------------------------------------------------
def test_posicion_cercana():
    ps = [{"ts": 100.0, "lat": 1}, {"ts": 200.0, "lat": 2}, {"ts": 900.0, "lat": 3}]
    assert posicion_cercana(ps, 140)["lat"] == 1
    assert posicion_cercana(ps, 160)["lat"] == 2
    assert posicion_cercana(ps, 480)["lat"] == 2        # a 280 s; la de 900, a 420
    assert posicion_cercana(ps, 560) is None            # 360 y 340 s: ninguna
    assert posicion_cercana(ps, 1300) is None           # todas a mas de 300 s
    assert posicion_cercana([], 100) is None


# --- Metricas -----------------------------------------------------------------
def test_distancia_telefono_al_gateway_que_recibio(manager):
    s = manager.start_session("VUELO", "A", "lora32")
    manager.add_posicion(s["id"], *TEL, alt_m=1930, precision_m=4.0, ts=1000.0)
    manager.ingest_record(_t3(0, 1, 0, ts=1010.0))
    m = manager.metrics(manager.store.current_session())
    esperada = haversine_km(*LOC_PABELLON, *TEL)
    assert m["dist_gw_km_max"] == round(esperada, 1)
    assert m["dist_gw_km_ultima"] == round(esperada, 3)
    assert m["gateway_ultimo"] == {"id": GW_PABELLON, "lat": LOC_PABELLON[0],
                                   "lon": LOC_PABELLON[1]}
    assert m["posicion_telefono"]["precision_m"] == 4.0
    # La posicion simulada del P1 (19.52, -99.05 en el test) habria dado
    # cientos de km: no se usa.
    assert m["dist_gw_km_max"] < 10


def test_gateway_sin_coordenadas_usa_gw_del_entorno(manager):
    s = manager.start_session("VUELO", "A", "lora32")
    manager.add_posicion(s["id"], *TEL, ts=1000.0)
    manager.ingest_record(_t3(0, 1, 0, ts=1000.0, gw=GW_LAB))
    m = manager.metrics(manager.store.current_session())
    cfg = manager.config
    assert m["dist_gw_km_ultima"] == round(haversine_km(cfg.gw_lat, cfg.gw_lon, *TEL), 3)
    assert m["gateway_ultimo"]["lat"] == cfg.gw_lat


def test_coordenadas_del_gateway_se_cachean(manager):
    s = manager.start_session("VUELO", "A", "lora32")
    manager.add_posicion(s["id"], *TEL, ts=1000.0)
    for f in range(3):
        manager.ingest_record(_t3(f, f + 1, 0, ts=1000.0 + f))
    assert manager.chirpstack.gateway_calls.count(GW_PABELLON) == 1


def test_sin_posicion_cercana_no_hay_distancia(manager):
    s = manager.start_session("VUELO", "A", "lora32")
    manager.add_posicion(s["id"], *TEL, ts=1000.0)
    manager.ingest_record(_t3(0, 1, 0, ts=2000.0))       # 1000 s despues
    m = manager.metrics(manager.store.current_session())
    assert m["dist_gw_km_max"] is None and m["dist_gw_km_ultima"] is None
    assert m["posicion_telefono"] is not None


def test_posicion_antes_del_primer_uplink(manager):
    s = manager.start_session("VUELO", "A", "lora32")
    manager.add_posicion(s["id"], *TEL, ts=1000.0)
    m = manager.metrics(manager.store.current_session())
    assert m["received"] == 0
    assert m["posicion_telefono"]["lat"] == TEL[0]


def test_tbeam_no_cambia(manager):
    """La T-Beam mide con su propio GPS contra GW_LAT/GW_LON, aunque el
    telefono mande posiciones."""
    s = manager.start_session("URBANO", "A")
    manager.add_posicion(s["id"], *TEL, ts=1000.0)
    manager.ingest_record(make_uplink(1, 11, lat=19.40, lon=-99.30))
    m = manager.metrics(manager.store.current_session())
    cfg = manager.config
    assert m["dist_gw_km_max"] == round(haversine_km(cfg.gw_lat, cfg.gw_lon, 19.40, -99.30), 1)
    assert m["posicion_telefono"] is None and m["dist_gw_km_ultima"] is None


def test_posicion_en_sesion_cerrada(manager):
    s = manager.start_session("VUELO", "A", "lora32")
    manager.abort_session(s["id"])
    with pytest.raises(CampoError) as e:
        manager.add_posicion(s["id"], *TEL)
    assert e.value.status_code == 409


# --- REST ---------------------------------------------------------------------
def test_rest_posicion_y_csv(client, app):
    app.state.chirpstack.gateway_locations = {GW_PABELLON: LOC_PABELLON}
    s = client.post("/session/start",
                    json={"scenario": "VUELO", "class": "A", "sonda": "lora32"},
                    headers=auth_headers()).json()["session"]
    r = client.post(f"/session/{s['id']}/posicion",
                    json={"lat": TEL[0], "lon": TEL[1], "precision_m": 5, "ts": 1000.0},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()["posicion"]["lat"] == TEL[0]
    assert app.state.hub.history[-2]["type"] == "posicion"

    app.state.manager.ingest_record(_t3(0, 1, 0, ts=1005.0))

    pos = client.get(f"/sessions/{s['id']}/posiciones", headers=auth_headers()).json()
    assert len(pos) == 1

    filas = list(csv.DictReader(io.StringIO(
        client.get(f"/sessions/{s['id']}/csv", headers=auth_headers()).text)))
    assert filas[0]["tel_lat"] == str(TEL[0])
    assert float(filas[0]["dist_gw_km"]) == pytest.approx(
        haversine_km(*LOC_PABELLON, *TEL), abs=1e-3)

    r = client.get(f"/sessions/{s['id']}/posiciones/csv", headers=auth_headers())
    assert r.status_code == 200 and "_pos.csv" in r.headers["content-disposition"]


@pytest.mark.parametrize("cuerpo", [{"lat": 95, "lon": 0}, {"lat": 0, "lon": 200},
                                    {"lat": 0}, {"lat": 0, "lon": 0, "precision_m": -1}])
def test_rest_posicion_invalida(client, cuerpo):
    s = client.post("/session/start",
                    json={"scenario": "VUELO", "class": "A", "sonda": "lora32"},
                    headers=auth_headers()).json()["session"]
    r = client.post(f"/session/{s['id']}/posicion", json=cuerpo, headers=auth_headers())
    assert r.status_code == 400


def test_rest_posicion_sesion_inexistente(client):
    r = client.post("/session/999/posicion", json={"lat": 0, "lon": 0},
                    headers=auth_headers())
    assert r.status_code == 404


def test_borrar_sesion_borra_posiciones(manager):
    s = manager.start_session("VUELO", "A", "lora32")
    manager.add_posicion(s["id"], *TEL)
    manager.abort_session(s["id"])
    manager.delete_session(s["id"])
    assert manager.store.session_posiciones(s["id"]) == []
