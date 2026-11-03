import json
"""
test_vuelo.py — Corrida VUELO (D-64, docs/VUELO-ESPEC.md): solo Clase A,
fPort 17, perfil terreno-a, objetivo 165 uplinks y metricas por tipo de paquete
y por rafaga.

Los uplinks se construyen como EVENTOS de ChirpStack (con el `object` que dara
el decoder de fPort 17) y pasan por parse_chirpstack_up, el mismo camino que la
ingesta MQTT real: asi se prueba tambien que P2/P3 sin posicion se guardan con
lat/lon null y que nada los trata como 0.
"""
from datetime import datetime, timezone

import pytest

from picaro_campo.config import CORRIDAS, Config
from picaro_campo.ingest import parse_chirpstack_up
from picaro_campo.sessions import SessionManager, WsHub
from picaro_campo.store import CampoStore
from tests.conftest import FakeChirpStack, auth_headers, make_config, make_uplink

FPORT_VUELO = 17
_COMUN = {"escenario": 4, "clase": "A", "escenario_nombre": "vuelo (puntos fijos)"}


def vuelo_object(tipo, rafaga, *, fix=True):
    """`object` del decoder de fPort 17 para un paquete P1/P2/P3 (VUELO-ESPEC)."""
    if tipo == 1:
        pos = ({"gps_fix": True, "latitude": 19.52, "longitude": -99.05,
                "altitude_m": 2890} if fix else
               {"gps_fix": False, "latitude": None, "longitude": None,
                "altitude_m": None})
        return {"tipo_paquete": "posicion", "rafaga": rafaga, **_COMUN, **pos}
    if tipo == 2:
        return {"tipo_paquete": "ambiente", "rafaga": rafaga, **_COMUN,
                "temperature_c": 14.25, "pressure_hpa": 712.3, "humidity_pct": 41,
                "battery_v": 3.92, "battery_pct": 81, "satellites": 8,
                "gps_fix": fix, "usb_powered": False, "charging": False,
                "gps_active": True, "mag_ok": True, "bme_ok": True}
    return {"tipo_paquete": "navegacion", "rafaga": rafaga, **_COMUN,
            "speed_kmh": 0.0, "heading_deg": None, "hdop": 1.2,
            "vspeed_ms": None, "uptime_s": 3600 + rafaga * 60}


def vuelo_event(f_cnt, tipo, rafaga, *, fport=FPORT_VUELO, fix=True):
    """Evento 'up' de ChirpStack v4 con el object de VUELO."""
    return {
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "deviceInfo": {"devEui": "0011223344550001"},
        "fCnt": f_cnt, "fPort": fport, "dr": 0,
        "rxInfo": [{"rssi": -121, "snr": -11.5, "gatewayId": "gw-test"}],
        "txInfo": {"frequency": 902300000},
        "object": vuelo_object(tipo, rafaga, fix=fix),
    }


def vuelo_rec(f_cnt, tipo, rafaga, **kw):
    return parse_chirpstack_up(vuelo_event(f_cnt, tipo, rafaga, **kw))


@pytest.fixture
def manager(tmp_path):
    cfg = make_config(tmp_path / "v.db")
    store = CampoStore(str(cfg.db_path))
    mgr = SessionManager(store, FakeChirpStack(), WsHub(), cfg)
    mgr.set_mqtt_connected(True)
    return mgr


# --- Config -------------------------------------------------------------------
def test_config_objetivo_por_corrida():
    cfg = Config(target_uplinks=250)             # como si TARGET_UPLINKS=250
    assert cfg.target_for("VUELO", "A") == 165
    assert cfg.target_for("URBANO", "A") == 250  # las demas siguen el global
    assert cfg.target_for("CERRO16", "C") == 250
    assert ("VUELO", "C") not in CORRIDAS


# --- Start --------------------------------------------------------------------
def test_start_vuelo_a(client, app):
    r = client.post("/session/start", json={"scenario": "VUELO", "class": "A"},
                    headers=auth_headers())
    assert r.status_code == 201
    s = r.json()["session"]
    assert s["expected_fport"] == 17
    assert s["profile"] == "terreno-a"
    assert s["target_uplinks"] == 165
    assert s["run_label"].endswith("-VUELO-A")
    assert app.state.chirpstack.profile_calls[-1] == "terreno-a"
    # metrics lleva el bloque vuelo desde el principio (vacio).
    m = client.get("/session/current", headers=auth_headers()).json()["metrics"]
    assert m["vuelo"]["por_tipo"] == {"posicion": 0, "ambiente": 0, "navegacion": 0}
    assert m["vuelo"]["rafaga_max"] is None


def test_start_vuelo_c_rechazado(client, app):
    r = client.post("/session/start", json={"scenario": "VUELO", "class": "C"},
                    headers=auth_headers())
    # Mismo error que cualquier combinacion invalida (p.ej. MARTE/A).
    otra = client.post("/session/start", json={"scenario": "MARTE", "class": "A"},
                       headers=auth_headers())
    assert r.status_code == otra.status_code == 400
    assert r.json()["detail"] == "corrida desconocida: VUELO/C"
    assert app.state.chirpstack.profile_calls == []   # ni se toco el perfil
    assert client.get("/session/current", headers=auth_headers()).json()["session"] is None


# --- Ingesta P2/P3 sin posicion ----------------------------------------------
def test_p2_p3_sin_posicion_se_guardan_con_null(manager):
    s = manager.start_session("VUELO", "A")
    for fc, tipo in ((0, 1), (1, 2), (2, 3)):
        assert manager.ingest_record(vuelo_rec(fc, tipo, 0)) is not None
    ups = manager.store.session_uplinks(s["id"])
    assert len(ups) == 3
    p1, p2, p3 = ups
    assert (p1["latitude"], p1["longitude"]) == (19.52, -99.05)
    for u in (p2, p3):
        assert u["latitude"] is None and u["longitude"] is None
        assert u["altitude_m"] is None
    assert p3["battery_v"] is None and p3["gps_fix"] is None


def test_metricas_toman_ultimo_valor_conocido_y_distancia_sin_nulls(manager):
    s = manager.start_session("VUELO", "A")
    for fc, tipo in ((0, 1), (1, 2), (2, 3)):         # el ultimo es un P3
        manager.ingest_record(vuelo_rec(fc, tipo, 0))
    m = manager.metrics(manager.store.get_session(s["id"]))
    # P3 no trae bateria ni satelites: se toman del ultimo P2, no null ni 0.
    assert m["battery_v"] == 3.92 and m["battery_pct"] == 81
    assert m["satellites"] == 8 and m["gps_fix"] is True
    # Distancia solo con el P1 (P2/P3 null no cuentan como (0,0)).
    assert m["dist_gw_km_max"] is not None and 0 < m["dist_gw_km_max"] < 20


def test_p1_sin_fix_no_da_distancia(manager):
    s = manager.start_session("VUELO", "A")
    manager.ingest_record(vuelo_rec(0, 1, 0, fix=False))
    manager.ingest_record(vuelo_rec(1, 2, 0, fix=False))
    m = manager.metrics(manager.store.get_session(s["id"]))
    assert m["dist_gw_km_max"] is None
    assert m["gps_fix"] is False


# --- Metricas por tipo y rafaga ----------------------------------------------
def test_metricas_por_tipo_y_rafaga(manager):
    s = manager.start_session("VUELO", "A")
    # rafaga 0 completa, 1 parcial (sin P2), 2 perdida, 3 parcial (solo P1).
    paquetes = [(0, 1, 0), (1, 2, 0), (2, 3, 0),
                (3, 1, 1), (5, 3, 1),
                (9, 1, 3)]
    for fc, tipo, raf in paquetes:
        manager.ingest_record(vuelo_rec(fc, tipo, raf))
    # Un duplicado del P3 de la rafaga 0 no la convierte en 4/3.
    manager.ingest_record(vuelo_rec(2, 3, 0))

    m = manager.metrics(manager.store.get_session(s["id"]))
    v = m["vuelo"]
    assert v["por_tipo"] == {"posicion": 3, "ambiente": 1, "navegacion": 3}
    assert v["rafagas_completas"] == 1
    assert v["rafagas_parciales"] == 2
    assert v["rafagas_perdidas"] == 1
    assert v["rafaga_max"] == 3
    assert v["rafagas_objetivo"] == 55
    # Formato clasico intacto: PDR sobre rango de fCnt, progreso sobre 165.
    assert m["received"] == 7
    assert m["progress_pct"] == round(100 * 10 / 165, 1)
    # El resumen tambien lo lleva (lista de sesiones de la app).
    assert manager.summary(manager.store.get_session(s["id"]))["vuelo"] == v


def test_uplink_sin_tipo_no_se_clasifica(manager):
    s = manager.start_session("VUELO", "A")
    manager.ingest_record(make_uplink(0, FPORT_VUELO))   # raw_json "{}" (decoder viejo)
    v = manager.metrics(manager.store.get_session(s["id"]))["vuelo"]
    assert v["por_tipo"] == {"posicion": 0, "ambiente": 0, "navegacion": 0}
    assert v["rafaga_max"] is None and v["rafagas_perdidas"] == 0


def test_auto_finish_vuelo_a_165(manager):
    s = manager.start_session("VUELO", "A")
    manager.ingest_record(vuelo_rec(0, 1, 0))
    manager.ingest_record(vuelo_rec(163, 2, 54))
    assert manager.store.get_session(s["id"])["state"] == "capturing"   # 164
    manager.ingest_record(vuelo_rec(164, 3, 54))                         # 165
    assert manager.store.get_session(s["id"])["state"] == "finished"


def test_fport_17_en_otra_corrida_es_desajuste(manager):
    manager.start_session("URBANO", "A")
    assert manager.ingest_record(vuelo_rec(0, 1, 0)) is None
    warns = [m for m in manager.hub.history if m.get("type") == "warning"]
    assert warns[-1]["expected"] == 11 and warns[-1]["got"] == 17


# --- Las corridas antiguas no cambian ----------------------------------------
@pytest.mark.parametrize("scenario,class_,fport,profile", [
    ("URBANO", "A", 11, "terreno-a"), ("URBANO", "C", 12, "terreno-c"),
    ("TERRAZA", "A", 13, "terreno-a"), ("TERRAZA", "C", 14, "terreno-c"),
    ("CERRO16", "A", 15, "terreno-a"), ("CERRO16", "C", 16, "terreno-c"),
])
def test_corridas_antiguas_sin_cambios(manager, scenario, class_, fport, profile):
    s = manager.start_session(scenario, class_)
    assert (s["expected_fport"], s["profile"], s["target_uplinks"]) == (fport, profile, 300)
    manager.ingest_record(make_uplink(1, fport, battery_pct=None))
    m = manager.metrics(manager.store.get_session(s["id"]))
    assert m["vuelo"] is None
    assert m["battery_pct"] is None              # null del ultimo, sin "rellenar"
    assert m["progress_pct"] == round(100 * 1 / 300, 1)
    assert manager.summary(manager.store.get_session(s["id"]))["vuelo"] is None


# --- Clave `vuelo` de cada uplink (REST y WS) ---------------------------------
def test_uplink_expone_campos_vuelo_sin_raw_json(client, app):
    client.post("/session/start", json={"scenario": "VUELO", "class": "A"},
                headers=auth_headers())
    sid = client.get("/session/current", headers=auth_headers()).json()["session"]["id"]
    mgr = app.state.manager
    mgr.ingest_record(vuelo_rec(0, 2, 7))                # P2
    mgr.ingest_record(vuelo_rec(1, 3, 7))                # P3

    ups = client.get(f"/sessions/{sid}/uplinks", headers=auth_headers()).json()
    assert all("raw_json" not in u for u in ups)
    p2, p3 = ups[0]["vuelo"], ups[1]["vuelo"]
    assert set(p2) == {"tipo_paquete", "rafaga", "humidity_pct", "speed_kmh",
                       "heading_deg", "hdop", "vspeed_ms", "uptime_s",
                       "mag_ok", "bme_ok"}
    assert p2["tipo_paquete"] == "ambiente" and p2["rafaga"] == 7
    assert p2["humidity_pct"] == 41 and p2["mag_ok"] is True
    assert p2["hdop"] is None                            # no lo trae P2 -> null
    assert p3["tipo_paquete"] == "navegacion" and p3["hdop"] == 1.2
    assert p3["heading_deg"] is None and p3["uptime_s"] == 3600 + 7 * 60
    assert p3["humidity_pct"] is None

    # El mensaje WS 'uplink' lleva la misma clave, tampoco raw_json.
    ws = [m for m in app.state.hub.history if m.get("type") == "uplink"]
    assert ws[-1]["vuelo"] == p3 and "raw_json" not in ws[-1]


def test_uplink_otra_corrida_vuelo_null(client, app):
    client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                headers=auth_headers())
    sid = client.get("/session/current", headers=auth_headers()).json()["session"]["id"]
    app.state.manager.ingest_record(make_uplink(1, 11))
    ups = client.get(f"/sessions/{sid}/uplinks", headers=auth_headers()).json()
    assert ups[0]["vuelo"] is None
    ws = [m for m in app.state.hub.history if m.get("type") == "uplink"]
    assert ws[-1]["vuelo"] is None


def test_rafaga_como_float_de_chirpstack():
    """ChirpStack manda los numeros del object como double (rafaga 0.0): tienen
    que contar igual que los enteros (hallado en banco, sesion 44)."""
    from picaro_campo.sessions import vuelo_metrics, vuelo_uplink_fields
    ups = [{"f_port": FPORT_VUELO,
            "raw_json": json.dumps({"object": vuelo_object(t, float(r))})}
           for r in (0, 1) for t in (1, 2, 3)]
    m = vuelo_metrics(ups)
    assert m["rafagas_completas"] == 2 and m["rafaga_max"] == 1
    v = vuelo_uplink_fields(ups[2])
    assert v["rafaga"] == 0 and isinstance(v["rafaga"], int)
    assert isinstance(v["uptime_s"], int)
