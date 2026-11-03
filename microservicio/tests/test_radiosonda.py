"""
test_radiosonda.py — Corrida RADIOSONDA y sonda `radiosonda`
(docs/RADIOSONDA-ESPEC.md): solo Clase C, perfil radiosonda-c, fPorts 20-23 de
telemetria + 30 del Marco Polo, objetivo 16 sin autofinalizar, sin ping
automatico y Marco Polo con RTT.

Los uplinks se construyen como EVENTOS de ChirpStack con el `object` que da el
codec de la radiosonda y pasan por parse_chirpstack_up, el mismo camino que la
ingesta MQTT real (igual que test_vuelo.py).
"""
import json
import time
from datetime import datetime, timezone

import pytest

from picaro_campo.chirpstack import ChirpStackClient, ChirpStackError
from picaro_campo.config import (CORRIDAS, PROFILE_IDS, SONDA_CORRIDAS, Config,
                                 sonda_admite)
from picaro_campo.ingest import parse_chirpstack_up
from picaro_campo.main import create_app
from picaro_campo.sessions import (CampoError, SessionManager, WsHub,
                                   radiosonda_lecturas, radiosonda_uplink_fields)
from picaro_campo.store import CampoStore
from tests.conftest import FakeChirpStack, auth_headers, make_config, make_uplink

EUI = "0011223344550001"            # la radiosonda comparte DevEUI con la tbeam
_COMUN = {"escenario_nombre": "radiosonda", "clase": "C"}
START = {"scenario": "RADIOSONDA", "class": "C", "sonda": "radiosonda"}


def rs_object(fport, **extra):
    """`object` del codec de la radiosonda para cada fPort (RADIOSONDA-ESPEC)."""
    if fport == 20:
        obj = {"tipo_paquete": "posicion", "gps_fix": True, "latitude": 19.52,
               "longitude": -99.05, "altitude_m": 18250, "satellites": 9}
    elif fport == 21:
        obj = {"tipo_paquete": "atmosfera", "ext_temperature_c": -41.25,
               "ext_pressure_hpa": 71.3, "ext_humidity_pct": 12, "tvoc_ppb": 40,
               "eco2_ppm": 410, "aqi": 1, "battery_pct": 77}
    elif fport == 22:
        obj = {"tipo_paquete": "ambiente", "aht_temperature_c": -12.5,
               "aht_humidity_pct": 20, "light_lux": 54000,
               "dht_temperature_c": -5, "dht_humidity_pct": 18,
               "battery_v": 3.91, "uptime_s": 1800}
    elif fport == 23:
        obj = {"tipo_paquete": "interno", "temperature_c": 8.75,
               "pressure_hpa": 71.9, "humidity_pct": 9, "ina_bus_v": 4.02,
               "ina_current_ma": 182.4, "lectura": 0, "gps_fix": True,
               "usb_powered": False, "charging": False, "gps_active": True}
    else:
        obj = {"tipo_paquete": "polo", "seq": 1, "rssi_dbm": -97, "snr_db": 6.25}
    obj.update(_COMUN)
    obj.update(extra)
    return obj


def rs_rec(f_cnt, fport, *, eui=EUI, rssi=-112, snr=-3.5, **extra):
    """Uplink de la radiosonda, tal como lo deja parse_chirpstack_up."""
    return parse_chirpstack_up({
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "deviceInfo": {"devEui": eui},
        "fCnt": f_cnt, "fPort": fport, "dr": 0,
        "rxInfo": [{"rssi": rssi, "snr": snr, "gatewayId": "gw-test"}],
        "txInfo": {"frequency": 902300000},
        "object": rs_object(fport, **extra),
    })


def lectura(mgr, f0, n_lectura=0, faltan=()):
    """Ingiere la rafaga de 4 uplinks de una lectura (fCnt f0..f0+3)."""
    for i, fport in enumerate((20, 21, 22, 23)):
        if fport in faltan:
            continue
        extra = {"lectura": n_lectura} if fport == 23 else {}
        mgr.ingest_record(rs_rec(f0 + i, fport, **extra))


@pytest.fixture
def manager(tmp_path):
    cfg = make_config(tmp_path / "r.db")
    mgr = SessionManager(CampoStore(str(cfg.db_path)), FakeChirpStack(), WsHub(), cfg)
    mgr.set_mqtt_connected(True)
    return mgr


def _start(mgr):
    return mgr.start_session("RADIOSONDA", "C", "radiosonda")


def _ws(hub, tipo):
    return [m for m in hub.history if m.get("type") == tipo]


# --- Config -------------------------------------------------------------------
def test_config_corrida_radiosonda():
    c = CORRIDAS[("RADIOSONDA", "C")]
    assert c["fports"] == (20, 21, 22, 23, 30)
    assert c["fports_objetivo"] == (20, 21, 22, 23)
    assert c["profile"] == "radiosonda-c" and "radiosonda-c" in PROFILE_IDS
    assert c["autofinaliza"] is False and c["ping_auto"] is False
    assert Config(target_uplinks=250).target_for("RADIOSONDA", "C") == 16
    assert ("RADIOSONDA", "A") not in CORRIDAS
    assert SONDA_CORRIDAS["radiosonda"] == {("RADIOSONDA", "C")}
    # Corrida exclusiva: ni tbeam (None = "todas") ni lora32 la abren.
    assert not sonda_admite("tbeam", "RADIOSONDA", "C")
    assert not sonda_admite("lora32", "RADIOSONDA", "C")
    assert sonda_admite("tbeam", "URBANO", "A")
    assert not sonda_admite("radiosonda", "URBANO", "A")


def test_dev_eui_radiosonda_del_entorno(monkeypatch):
    monkeypatch.setenv("DEV_EUI_RADIOSONDA", "00112233445500FF")
    cfg = Config.from_env()
    assert cfg.dev_eui_for("radiosonda") == "00112233445500ff"
    monkeypatch.delenv("DEV_EUI_RADIOSONDA")
    assert Config.from_env().dev_eui_for("radiosonda") == ""


# --- Start --------------------------------------------------------------------
def test_start_radiosonda_c(client, app):
    r = client.post("/session/start", json=START, headers=auth_headers())
    assert r.status_code == 201
    s = r.json()["session"]
    assert s["sonda"] == "radiosonda" and s["dev_eui"] == EUI
    assert s["expected_fport"] == 20 and s["profile"] == "radiosonda-c"
    assert s["target_uplinks"] == 16
    assert s["run_label"].endswith("-RADIOSONDA-C")
    chirp = app.state.chirpstack
    assert chirp.profile_calls[-1] == "radiosonda-c"
    assert chirp.class_euis[-1] == EUI
    m = client.get("/session/current", headers=auth_headers()).json()["metrics"]
    assert m["vuelo"] is None
    rs = m["radiosonda"]
    assert rs["por_tipo"] == {"posicion": 0, "atmosfera": 0, "ambiente": 0,
                              "interno": 0, "polo": 0}
    assert rs["telemetria_objetivo"] == 16 and rs["lecturas_completas"] == 0
    assert all(v is None for v in rs["ultima"].values())
    assert rs["rtt_ms_mean"] is None and rs["marcos_enviados"] == 0


@pytest.mark.parametrize("sonda", ["tbeam", "lora32"])
def test_otras_sondas_no_abren_radiosonda(client, app, sonda):
    r = client.post("/session/start",
                    json={"scenario": "RADIOSONDA", "class": "C", "sonda": sonda},
                    headers=auth_headers())
    assert r.status_code == 400 and "no admite" in r.json()["detail"]
    assert app.state.chirpstack.profile_calls == []


def test_sin_sonda_no_abre_radiosonda(client):
    """La app vieja no manda `sonda` (= tbeam): tampoco puede abrirla."""
    r = client.post("/session/start", json={"scenario": "RADIOSONDA", "class": "C"},
                    headers=auth_headers())
    assert r.status_code == 400


@pytest.mark.parametrize("scenario,class_", [("URBANO", "A"), ("CERRO16", "C"),
                                             ("VUELO", "A")])
def test_radiosonda_rechaza_las_demas_corridas(client, scenario, class_):
    r = client.post("/session/start",
                    json={"scenario": scenario, "class": class_, "sonda": "radiosonda"},
                    headers=auth_headers())
    assert r.status_code == 400 and "no admite" in r.json()["detail"]


def test_radiosonda_a_no_existe(client):
    r = client.post("/session/start",
                    json={"scenario": "RADIOSONDA", "class": "A", "sonda": "radiosonda"},
                    headers=auth_headers())
    assert r.status_code == 400
    assert r.json()["detail"] == "corrida desconocida: RADIOSONDA/A"


def test_gate_de_clase_409(client, app):
    """ChirpStack con la clase congelada en A (JOIN con el perfil de terreno-a):
    409 para que la app pida el re-join por BLE (D-60/D-62)."""
    app.state.chirpstack.enabled_class = "A"
    r = client.post("/session/start", json=START, headers=auth_headers())
    assert r.status_code == 409 and "clase desajustada" in r.json()["detail"]
    # El perfil bueno ya quedo puesto para el re-join.
    assert app.state.chirpstack.profile_calls[-1] == "radiosonda-c"
    assert client.get("/session/current", headers=auth_headers()).json()["session"] is None


def test_radiosonda_sin_dev_eui(tmp_path):
    cfg = make_config(tmp_path / "x.db")
    cfg.dev_eui_radiosonda = ""
    mgr = SessionManager(CampoStore(str(cfg.db_path)), FakeChirpStack(), WsHub(), cfg)
    mgr.set_mqtt_connected(True)
    with pytest.raises(CampoError) as e:
        _start(mgr)
    assert e.value.status_code == 400 and "no esta configurada" in e.value.detail


def test_sin_ping_automatico(tmp_path):
    """Con el ping automatico encendido, una sesion RADIOSONDA no lo arranca
    (el Marco Polo lo sustituye); una URBANO si."""
    from fastapi.testclient import TestClient
    cfg = make_config(tmp_path / "p.db", ping_interval_s=0.02)
    chirp = FakeChirpStack()
    application = create_app(config=cfg, chirpstack=chirp,
                             store=CampoStore(str(cfg.db_path)), start_mqtt=False)
    with TestClient(application) as c:
        application.state.manager.set_mqtt_connected(True)
        s = c.post("/session/start", json=START, headers=auth_headers()).json()["session"]
        time.sleep(0.15)
        assert chirp.ping_calls == []
        c.post(f"/session/{s['id']}/finish", headers=auth_headers())
        s2 = c.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                    headers=auth_headers()).json()["session"]
        deadline = time.time() + 2
        while not chirp.ping_calls and time.time() < deadline:
            time.sleep(0.02)
        assert chirp.ping_calls                       # control: aqui si hay ping
        # Se cierra antes de salir (como en test_api): el ciclo muere con ella.
        c.post(f"/session/{s2['id']}/finish", headers=auth_headers())


# --- Ingesta con varios fPorts ------------------------------------------------
def test_todos_los_fports_se_guardan_sin_desajuste(manager):
    s = _start(manager)
    for fc, fport in enumerate((20, 21, 22, 23, 30)):
        assert manager.ingest_record(rs_rec(fc, fport)) is not None
    assert len(manager.store.session_uplinks(s["id"])) == 5
    assert _ws(manager.hub, "warning") == []


def test_fport_ajeno_a_la_corrida_es_desajuste(manager):
    _start(manager)
    assert manager.ingest_record(make_uplink(0, 17)) is None
    w = _ws(manager.hub, "warning")[-1]
    assert w["kind"] == "fport_mismatch" and w["expected"] == 20 and w["got"] == 17


def test_fport_radiosonda_en_otra_corrida_es_desajuste(manager):
    manager.start_session("URBANO", "A")
    assert manager.ingest_record(rs_rec(0, 21)) is None
    w = _ws(manager.hub, "warning")[-1]
    assert w["expected"] == 11 and w["got"] == 21


def test_no_autofinaliza_y_progreso_cuenta_solo_telemetria(manager):
    s = _start(manager)
    f = 0
    for n in range(5):                     # 5 lecturas = 20 > 16 nominales
        lectura(manager, f, n)
        f += 4
        if n < 2:                          # Polos intercalados (no cuentan)
            manager.ingest_record(rs_rec(f, 30, seq=n + 1))
            f += 1
    sess = manager.store.get_session(s["id"])
    assert sess["state"] == "capturing"    # la cierra el operador
    m = manager.metrics(sess)
    assert m["radiosonda"]["telemetria_recibidos"] == 20
    assert m["radiosonda"]["por_tipo"]["polo"] == 2
    assert m["received"] == 22 and m["gaps"] == 0
    assert m["progress_pct"] == 100.0
    assert _ws(manager.hub, "session")[-1]["state"] == "capturing"


def test_progreso_a_mitad(manager):
    s = _start(manager)
    lectura(manager, 0)
    manager.ingest_record(rs_rec(4, 30))           # el Polo no suma
    lectura(manager, 5, 1, faltan=(22,))
    m = manager.metrics(manager.store.get_session(s["id"]))
    assert m["progress_pct"] == round(100 * 7 / 16, 1)


# --- Metricas: lecturas y ultimo valor conocido ------------------------------
def test_lecturas_completas_y_parciales(manager):
    s = _start(manager)
    lectura(manager, 0, 0)                                  # completa
    lectura(manager, 4, 1, faltan=(21, 23))                 # parcial (20+22)
    # Lectura 2 con un Polo colado a mitad de rafaga: 20, POLO, 21, 22, 23.
    manager.ingest_record(rs_rec(8, 20))
    manager.ingest_record(rs_rec(9, 30))
    manager.ingest_record(rs_rec(10, 21))
    manager.ingest_record(rs_rec(11, 22))
    manager.ingest_record(rs_rec(12, 23, lectura=2))
    manager.ingest_record(rs_rec(12, 23, lectura=2))        # duplicado
    lectura(manager, 13, 3, faltan=(20, 21, 22))            # parcial (solo 23)
    rs = manager.metrics(manager.store.get_session(s["id"]))["radiosonda"]
    assert rs["lecturas_completas"] == 2
    assert rs["lecturas_parciales"] == 2
    assert rs["lectura_ultima"] == 3


def test_agrupado_por_fcnt():
    # 20@0 (lectura k) y 23@7 (lectura k+1): 4 fCnt de mas -> dos lecturas.
    assert radiosonda_lecturas([(0, 0), (7, 3)]) == [{0}, {3}]
    # 20@0 y 21@3 (dos Polos en medio, uno perdido): misma lectura.
    assert radiosonda_lecturas([(0, 0), (3, 1)]) == [{0, 1}]
    # 22@2 y 21@5: el tipo no avanza -> lectura nueva.
    assert radiosonda_lecturas([(2, 2), (5, 1)]) == [{2}, {1}]


def test_ultima_lectura_conocida_sin_nulls(manager):
    s = _start(manager)
    lectura(manager, 0)
    # Lectura siguiente con el BME280 externo caido (sentinelas -> null) y sin
    # fix: los null no tapan los ultimos valores buenos.
    manager.ingest_record(rs_rec(4, 20, gps_fix=False, latitude=None,
                                 longitude=None, altitude_m=None, satellites=3))
    manager.ingest_record(rs_rec(5, 21, ext_temperature_c=None,
                                 ext_pressure_hpa=None, ext_humidity_pct=None,
                                 battery_pct=74))
    m = manager.metrics(manager.store.get_session(s["id"]))
    u = m["radiosonda"]["ultima"]
    assert u["ext_temperature_c"] == -41.25 and u["ext_pressure_hpa"] == 71.3
    assert u["battery_pct"] == 74 and u["satellites"] == 3
    assert u["latitude"] == 19.52 and u["gps_fix"] is False
    assert u["ina_current_ma"] == 182.4 and u["light_lux"] == 54000
    assert "seq" not in u and "tipo_paquete" not in u
    # Metricas clasicas: ultimo paquete que TRAJO cada magnitud.
    assert m["battery_pct"] == 74 and m["battery_v"] == 3.91
    # Distancia solo con el fPort 20 con coordenadas.
    assert m["dist_gw_km_max"] is not None and 0 < m["dist_gw_km_max"] < 20
    assert manager.summary(manager.store.get_session(s["id"]))["radiosonda"] \
        == m["radiosonda"]


def test_otras_corridas_radiosonda_null(manager):
    s = manager.start_session("URBANO", "A")
    manager.ingest_record(make_uplink(1, 11))
    m = manager.metrics(manager.store.get_session(s["id"]))
    assert m["radiosonda"] is None
    assert manager.summary(manager.store.get_session(s["id"]))["radiosonda"] is None


# --- Clave `radiosonda` de cada uplink (REST y WS) -----------------------------
def test_uplink_expone_campos_radiosonda(client, app):
    sid = client.post("/session/start", json=START,
                      headers=auth_headers()).json()["session"]["id"]
    mgr = app.state.manager
    for fc, fport in enumerate((20, 21, 22, 23, 30)):
        mgr.ingest_record(rs_rec(fc, fport))
    ups = client.get(f"/sessions/{sid}/uplinks", headers=auth_headers()).json()
    assert all("raw_json" not in u and u["vuelo"] is None for u in ups)
    pos, atm, amb, intr, polo = (u["radiosonda"] for u in ups)
    assert set(pos) == {"tipo_paquete", "gps_fix", "latitude", "longitude",
                        "altitude_m", "satellites"}
    assert set(atm) == {"tipo_paquete", "ext_temperature_c", "ext_pressure_hpa",
                        "ext_humidity_pct", "tvoc_ppb", "eco2_ppm", "aqi",
                        "battery_pct"}
    assert set(amb) == {"tipo_paquete", "aht_temperature_c", "aht_humidity_pct",
                        "light_lux", "dht_temperature_c", "dht_humidity_pct",
                        "battery_v", "uptime_s"}
    assert set(intr) == {"tipo_paquete", "temperature_c", "pressure_hpa",
                         "humidity_pct", "ina_bus_v", "ina_current_ma", "lectura",
                         "gps_fix", "usb_powered", "charging", "gps_active"}
    assert set(polo) == {"tipo_paquete", "seq", "rssi_dbm", "snr_db"}
    assert pos["tipo_paquete"] == "posicion" and pos["altitude_m"] == 18250
    assert atm["eco2_ppm"] == 410 and amb["dht_temperature_c"] == -5
    assert polo["rssi_dbm"] == -97
    # Las columnas clasicas tambien se llenan desde el object del codec.
    assert ups[0]["latitude"] == 19.52 and ups[1]["battery_pct"] == 77
    assert ups[3]["temperature_c"] == 8.75
    ws = _ws(app.state.hub, "uplink")
    assert ws[-1]["radiosonda"] == polo and "raw_json" not in ws[-1]


def test_uplink_otra_corrida_radiosonda_null(client, app):
    sid = client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                      headers=auth_headers()).json()["session"]["id"]
    app.state.manager.ingest_record(make_uplink(1, 11))
    ups = client.get(f"/sessions/{sid}/uplinks", headers=auth_headers()).json()
    assert ups[0]["radiosonda"] is None
    assert _ws(app.state.hub, "uplink")[-1]["radiosonda"] is None


def test_floats_de_chirpstack_vuelven_enteros():
    row = {"f_port": 23, "raw_json": json.dumps(
        {"object": rs_object(23, lectura=7.0, humidity_pct=9.0)})}
    v = radiosonda_uplink_fields(row)
    assert v["lectura"] == 7 and isinstance(v["lectura"], int)
    assert isinstance(v["humidity_pct"], int)
    assert isinstance(v["temperature_c"], float)
    polo = radiosonda_uplink_fields({"f_port": 30, "raw_json": json.dumps(
        {"object": rs_object(30, seq=4.0, rssi_dbm=-101.0)})})
    assert polo["seq"] == 4 and polo["rssi_dbm"] == -101
    assert isinstance(polo["rssi_dbm"], int)


def test_object_sin_tipo_se_clasifica_por_fport():
    v = radiosonda_uplink_fields({"f_port": 22, "raw_json": "{}"})
    assert v["tipo_paquete"] == "ambiente" and v["battery_v"] is None
    assert radiosonda_uplink_fields({"f_port": 17, "raw_json": "{}"}) is None


# --- Marco Polo ---------------------------------------------------------------
def test_marco_sin_sesion_409(client, app):
    r = client.post("/marco", headers=auth_headers())
    assert r.status_code == 409
    assert app.state.chirpstack.marco_calls == []


def test_marco_en_sesion_de_otra_sonda_409(client, app):
    client.post("/session/start", json={"scenario": "URBANO", "class": "A"},
                headers=auth_headers())
    assert client.post("/marco", headers=auth_headers()).status_code == 409
    assert app.state.chirpstack.marco_calls == []


def test_marco_exige_token(client):
    assert client.post("/marco").status_code == 401


def test_marco_polo_completo(client, app):
    sid = client.post("/session/start", json=START,
                      headers=auth_headers()).json()["session"]["id"]
    r = client.post("/marco", headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["seq"] == 1 and body["enqueued_at"].endswith("+00:00")
    chirp = app.state.chirpstack
    assert chirp.marco_calls == [1] and chirp.marco_euis == [EUI]
    assert chirp.ping_calls == []
    ack = _ws(app.state.hub, "marco_ack")[-1]
    assert ack == {"type": "marco_ack", "seq": 1, "enqueued_at": body["enqueued_at"]}
    # Pendiente: aun sin Polo.
    mp = client.get(f"/sessions/{sid}/marcopolo", headers=auth_headers()).json()
    assert mp == [{"seq": 1, "enqueued_at": body["enqueued_at"], "received_at": None,
                   "rtt_ms": None, "rssi_dbm": None, "snr_db": None,
                   "gw_rssi": None, "gw_snr": None}]

    app.state.manager.ingest_record(rs_rec(0, 30, seq=1, rssi_dbm=-97,
                                           snr_db=6.25, rssi=-110, snr=-2.5))
    polo = _ws(app.state.hub, "polo")[-1]
    assert set(polo) == {"type", "seq", "rtt_ms", "rssi_dbm", "snr_db", "gw_rssi",
                         "gw_snr", "received_at"}
    assert polo["seq"] == 1 and isinstance(polo["rtt_ms"], int) and polo["rtt_ms"] >= 0
    assert (polo["rssi_dbm"], polo["snr_db"]) == (-97, 6.25)
    assert (polo["gw_rssi"], polo["gw_snr"]) == (-110, -2.5)
    # Orden de difusion: uplink, polo y luego metrics (que ya trae el RTT).
    tipos = [m["type"] for m in app.state.hub.history]
    i = len(tipos) - 1 - tipos[::-1].index("polo")
    assert tipos[i - 1] == "uplink" and tipos[i + 1] == "metrics"
    rs = app.state.hub.history[i + 1]["radiosonda"]
    assert rs["marcos_enviados"] == 1 and rs["polos_recibidos"] == 1
    assert rs["rtt_ms_min"] == rs["rtt_ms_max"] == polo["rtt_ms"]
    assert rs["telemetria_recibidos"] == 0          # el Polo no es lectura

    mp = client.get(f"/sessions/{sid}/marcopolo", headers=auth_headers()).json()
    assert mp[0]["received_at"] == polo["received_at"]
    assert mp[0]["rtt_ms"] == polo["rtt_ms"] and mp[0]["gw_rssi"] == -110

    # El Marco tambien queda entre los downlinks ENVIADOS (cruce con la microSD).
    dls = client.get(f"/sessions/{sid}/downlinks", headers=auth_headers()).json()
    assert [(d["seq"], d["fport"], d["origin"]) for d in dls] == [(1, 30, "marco")]


def test_rtt_medio_min_max(manager):
    s = _start(manager)
    for seq, retraso in ((1, 1.5), (2, 3.0), (3, None)):
        manager.enqueue_marco()
        if retraso is None:
            continue                                # el Polo 3 nunca llega
        fila = manager.store.session_marcopolo(s["id"])[-1]
        # Se fija la hora de encolado para que el RTT sea determinista.
        manager.store._conn.execute("UPDATE marcopolo SET enqueued_ts=? WHERE id=?",
                                    (time.time() - retraso, fila["id"]))
        manager.ingest_record(rs_rec(seq, 30, seq=seq))
    rs = manager.metrics(manager.store.get_session(s["id"]))["radiosonda"]
    assert rs["marcos_enviados"] == 3 and rs["polos_recibidos"] == 2
    assert 1450 <= rs["rtt_ms_min"] <= 1600 and 2950 <= rs["rtt_ms_max"] <= 3100
    assert rs["rtt_ms_mean"] == round((rs["rtt_ms_min"] + rs["rtt_ms_max"]) / 2, 1)
    mp = manager.session_marcopolo(s["id"])
    assert mp[2]["received_at"] is None and mp[2]["rtt_ms"] is None


def test_polo_sin_marco_pendiente(manager):
    s = _start(manager)
    manager.ingest_record(rs_rec(0, 30, seq=42))
    polo = _ws(manager.hub, "polo")[-1]
    assert polo["seq"] == 42 and polo["rtt_ms"] is None
    # Un Polo repetido tras emparejar tampoco se inventa RTT.
    manager.enqueue_marco()
    manager.ingest_record(rs_rec(1, 30, seq=1))
    manager.ingest_record(rs_rec(2, 30, seq=1))
    assert _ws(manager.hub, "polo")[-1]["rtt_ms"] is None
    rs = manager.metrics(manager.store.get_session(s["id"]))["radiosonda"]
    assert rs["polos_recibidos"] == 1 and rs["polos_sin_marco"] == 2
    assert rs["marcos_enviados"] == 1


def test_polo_empareja_el_marco_mas_reciente(manager):
    """El seq es ciclico: un Marco viejo sin respuesta con el mismo seq no se
    lleva el Polo del nuevo."""
    s = _start(manager)
    manager._marco_seq = 254
    assert manager.enqueue_marco()["seq"] == 255
    assert manager.enqueue_marco()["seq"] == 1          # ciclo 255 -> 1
    manager._marco_seq = 0
    assert manager.enqueue_marco()["seq"] == 1          # otro Marco seq 1
    manager.ingest_record(rs_rec(0, 30, seq=1))
    mp = manager.session_marcopolo(s["id"])
    assert [m["rtt_ms"] is not None for m in mp] == [False, False, True]


def test_seq_del_marco_se_reinicia_con_la_sesion(manager):
    s = _start(manager)
    manager.enqueue_marco()
    manager.enqueue_marco()
    manager.finish_session(s["id"])
    _start(manager)
    assert manager.enqueue_marco()["seq"] == 1


def test_marco_con_chirpstack_caido_503_sin_pendiente(client, app):
    sid = client.post("/session/start", json=START,
                      headers=auth_headers()).json()["session"]["id"]
    app.state.chirpstack.fail = ChirpStackError("sin red")
    r = client.post("/marco", headers=auth_headers())
    assert r.status_code == 503
    app.state.chirpstack.fail = None
    assert client.get(f"/sessions/{sid}/marcopolo", headers=auth_headers()).json() == []
    assert _ws(app.state.hub, "marco_ack") == []


def test_marcopolo_sesion_inexistente_404(client):
    assert client.get("/sessions/999/marcopolo", headers=auth_headers()).status_code == 404


def test_borrar_sesion_borra_marcopolo(manager):
    s = _start(manager)
    manager.enqueue_marco()
    manager.abort_session(s["id"])
    manager.delete_session(s["id"])
    assert manager.store.session_marcopolo(s["id"]) == []


def test_enqueue_marco_del_cliente_real(monkeypatch):
    """El cliente real encola fPort 30 con el seq como unico byte."""
    cli = ChirpStackClient("http://cs.invalido", "t", "00112233445500ff", {})
    llamadas = []
    monkeypatch.setattr(cli, "_request",
                        lambda m, p, b=None: llamadas.append((m, p, b)) or {})
    cli.enqueue_marco(7)
    metodo, ruta, body = llamadas[0]
    assert (metodo, ruta) == ("POST", "/api/devices/00112233445500ff/queue")
    q = body["queueItem"]
    assert q["fPort"] == 30 and q["data"] == "Bw==" and q["confirmed"] is False


# --- CSV ----------------------------------------------------------------------
def test_csv_de_sesion_radiosonda(client, app):
    """El CSV de uplinks es el de siempre: los campos de la radiosonda sin
    columna propia viajan en raw_json, igual que en VUELO."""
    sid = client.post("/session/start", json=START,
                      headers=auth_headers()).json()["session"]["id"]
    lectura(app.state.manager, 0)
    r = client.get(f"/sessions/{sid}/csv", headers=auth_headers())
    assert r.status_code == 200
    lineas = r.text.strip().splitlines()
    assert len(lineas) == 5 and "ext_temperature_c" in lineas[2]
    assert "-RADIOSONDA-C.csv" in r.headers["content-disposition"]
