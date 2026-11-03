"""
test_sessions.py — Tests de unidad del SessionManager, sin FastAPI ni red.

Se construye el manager directo (store SQLite temporal + ChirpStack falso + hub)
para probar la logica pura: numeracion de run_label (intentos), matematica de las
metricas, haversine, que el desajuste de fPort no guarda y la auto-finalizacion.
"""
import pytest

from picaro_campo.chirpstack import ChirpStackError
from picaro_campo.sessions import CampoError, SessionManager, WsHub, haversine_km
from picaro_campo.store import CampoStore
from tests.conftest import FakeChirpStack, make_config, make_uplink


@pytest.fixture
def manager(tmp_path):
    cfg = make_config(tmp_path / "u.db")
    store = CampoStore(str(cfg.db_path))
    mgr = SessionManager(store, FakeChirpStack(), WsHub(), cfg)
    mgr.set_mqtt_connected(True)     # sin broker real, se simula conectado
    return mgr


# --- run_label ---------------------------------------------------------------
def test_run_label_incrementa_intentos(manager):
    s1 = manager.start_session("URBANO", "A")
    base = s1["run_label"]
    assert base.endswith("-URBANO-A")
    manager.finish_session(s1["id"])           # hay que cerrar para abrir otra

    s2 = manager.start_session("URBANO", "A")
    assert s2["run_label"] == base + "-2"
    manager.finish_session(s2["id"])

    s3 = manager.start_session("URBANO", "A")
    assert s3["run_label"] == base + "-3"


# --- Estados -----------------------------------------------------------------
def test_una_sola_sesion_capturando(manager):
    manager.start_session("URBANO", "A")
    with pytest.raises(CampoError) as ei:
        manager.start_session("TERRAZA", "C")
    assert ei.value.status_code == 409


def test_abort_conserva_datos(manager):
    s = manager.start_session("URBANO", "A")
    manager.ingest_record(make_uplink(1, 11))
    manager.abort_session(s["id"])
    got = manager.store.get_session(s["id"])
    assert got["state"] == "aborted"
    assert got["ended_at"] is not None
    # Los datos capturados se conservan (§3).
    assert len(manager.store.session_uplinks(s["id"])) == 1


def test_start_sin_mqtt_es_503(manager):
    manager.set_mqtt_connected(False)
    with pytest.raises(CampoError) as ei:
        manager.start_session("URBANO", "A")
    assert ei.value.status_code == 503


def test_start_chirpstack_caido_propaga(manager):
    manager.chirpstack.fail = ChirpStackError("api caida")
    with pytest.raises(ChirpStackError):
        manager.start_session("URBANO", "A")
    # No debe quedar sesion abierta si el perfil no se pudo cambiar.
    assert manager.store.current_session() is None


# --- Metricas ----------------------------------------------------------------
def test_metricas_pdr_y_gaps(manager):
    s = manager.start_session("URBANO", "A")     # expected_fport 11
    manager.ingest_record(make_uplink(1, 11, rssi=-110, snr=-5.0))
    manager.ingest_record(make_uplink(2, 11, rssi=-120, snr=-9.0))
    manager.ingest_record(make_uplink(4, 11, rssi=-118, snr=-7.0))   # hueco en 3

    m = manager.metrics(manager.store.get_session(s["id"]))
    assert m["received"] == 3
    assert m["last_fcnt"] == 4
    assert m["gaps"] == 1                     # (4-1+1) - 3
    assert m["pdr_est"] == 0.75               # 3/4
    assert m["rssi_last"] == -118
    assert m["rssi_mean"] == round((-110 - 120 - 118) / 3, 1)
    assert m["progress_pct"] == round(100 * 4 / 300, 1)


def test_metricas_battery_pct_null(manager):
    s = manager.start_session("URBANO", "A")
    manager.ingest_record(make_uplink(1, 11, battery_pct=None, battery_v=3.70))
    m = manager.metrics(manager.store.get_session(s["id"]))
    assert m["battery_pct"] is None           # null, no 0
    assert m["battery_v"] == 3.70


def test_metricas_vacias(manager):
    s = manager.start_session("URBANO", "A")
    m = manager.metrics(manager.store.get_session(s["id"]))
    assert m["received"] == 0
    assert m["pdr_est"] is None
    assert m["last_fcnt"] is None


# --- Corridas consecutivas con el mismo fPort (bug de campo, ago-2026) -------
def test_sesiones_consecutivas_mismo_fport_no_mezclan_conteos(manager):
    """Dos corridas seguidas de la MISMA corrida (mismo fPort) sin reiniciar la
    sonda: el fCnt LoRaWAN continua (300, 301, …) pero los conteos de la sesion
    nueva parten de cero. Reproduce la serie 1 de campo (2026-08-18: una corrida
    completa fCnt 0..298 y la siguiente arranco en 299..598)."""
    s1 = manager.start_session("URBANO", "C")            # expected_fport 12
    for fc in (0, 1, 2, 3):
        manager.ingest_record(make_uplink(fc, 12))
    manager.finish_session(s1["id"])

    s2 = manager.start_session("URBANO", "C")            # mismo fPort 12
    assert s2["id"] != s1["id"]
    # La sonda NO se reinicio: el fCnt continua donde quedo la corrida anterior.
    manager.ingest_record(make_uplink(300, 12))
    manager.ingest_record(make_uplink(301, 12))

    m2 = manager.metrics(manager.store.get_session(s2["id"]))
    # El contador de la sesion nueva parte de cero: 2 recibidos, no 4+2.
    assert m2["received"] == 2
    # Y los "enviados" (received+gaps), la base del TX n/300 y del auto-finish,
    # tampoco arrastran nada: el rango de fCnt se mide DENTRO de la sesion.
    assert m2["received"] + m2["gaps"] == 2
    assert m2["progress_pct"] == round(100 * 2 / 300, 1)

    # Los uplinks quedaron ligados cada uno a SU sesion.
    assert len(manager.store.session_uplinks(s1["id"])) == 4
    assert len(manager.store.session_uplinks(s2["id"])) == 2

    # Y las metricas de la sesion vieja no se contaminaron con las nuevas.
    m1 = manager.metrics(manager.store.get_session(s1["id"]))
    assert m1["received"] == 4
    assert m1["last_fcnt"] == 3


def test_metrics_ws_tras_nueva_sesion_no_acumula(manager):
    """El broadcast de metricas tras el primer uplink de la segunda sesion ya
    dice received=1 (lo que pinta la app): no 'target+1'."""
    s1 = manager.start_session("URBANO", "A")            # expected_fport 11
    for fc in range(3):
        manager.ingest_record(make_uplink(fc, 11))
    manager.finish_session(s1["id"])

    manager.start_session("URBANO", "A")
    manager.ingest_record(make_uplink(3, 11))            # fCnt continua

    metricas = [m for m in manager.hub.history if m.get("type") == "metrics"]
    assert metricas[-1]["received"] == 1
    assert metricas[-1]["gaps"] == 0


# --- Desajuste de fPort ------------------------------------------------------
def test_mismatch_no_guarda_y_avisa(manager):
    s = manager.start_session("CERRO16", "C")    # expected 16
    res = manager.ingest_record(make_uplink(1, 15))   # otra corrida
    assert res is None
    assert manager.metrics(manager.store.get_session(s["id"]))["received"] == 0
    warns = [m for m in manager.hub.history if m.get("type") == "warning"]
    assert warns and warns[-1]["expected"] == 16 and warns[-1]["got"] == 15


def test_fport_ajeno_se_ignora_sin_warning(manager):
    manager.start_session("URBANO", "A")         # expected 11
    manager.ingest_record(make_uplink(1, 99))    # fPort fuera de 11..16
    warns = [m for m in manager.hub.history if m.get("type") == "warning"]
    assert warns == []


# --- Auto-finalizacion -------------------------------------------------------
def test_auto_finish(manager):
    s = manager.start_session("URBANO", "A")
    # Un uplink con fCnt alto POR SI SOLO no finaliza: el progreso se mide por el
    # RANGO de fCnt desde el inicio (recibidos+gaps), no por el fCnt absoluto. Asi
    # una segunda corrida que arranca con el contador ya alto no se cierra sola.
    manager.ingest_record(make_uplink(300, 11))
    assert manager.store.get_session(s["id"])["state"] == "capturing"
    # Al observarse un rango de 300 (fCnt 1..300, aunque casi todo se perdiera),
    # la sonda ha enviado el objetivo y SI auto-finaliza.
    manager.ingest_record(make_uplink(1, 11))
    assert manager.store.get_session(s["id"])["state"] == "finished"
    assert manager.store.current_session() is None


# --- Haversine ---------------------------------------------------------------
def test_haversine_conocido():
    d = haversine_km(19.0, -99.0, 20.0, -99.0)
    assert 110 < d < 112     # 1 grado de latitud ~ 111 km


# --- Gate de clase (D-60) ----------------------------------------------------
def test_gate_clase_desajustada_no_abre_sesion(manager):
    # JOIN congelado en Clase A (issue #360) y corrida de Clase C.
    manager.chirpstack.enabled_class = "A"
    with pytest.raises(CampoError) as ei:
        manager.start_session("URBANO", "C")
    assert ei.value.status_code == 409
    assert "clase desajustada" in ei.value.detail
    assert manager.store.current_session() is None
    warns = [m for m in manager.hub.history if m.get("type") == "warning"]
    assert warns[-1]["kind"] == "class_mismatch"
    assert warns[-1]["expected"] == "C" and warns[-1]["got"] == "A"


def test_gate_clase_coincidente_abre(manager):
    manager.chirpstack.enabled_class = "C"
    s = manager.start_session("URBANO", "C")
    assert s["state"] == "capturing"
    assert [m for m in manager.hub.history if m.get("type") == "warning"] == []


# --- Ping --------------------------------------------------------------------
def test_ping_resetea_en_start(manager):
    manager.start_session("URBANO", "A")
    assert manager.enqueue_ping() == 1
    assert manager.enqueue_ping() == 2
    manager.finish_session(manager.store.current_session()["id"])
    manager.start_session("TERRAZA", "C")        # nueva corrida -> seq vuelve a 1
    assert manager.enqueue_ping() == 1


def test_ping_manual_y_auto_comparten_secuencia_y_persisten(manager):
    s = manager.start_session("URBANO", "A")
    assert manager.enqueue_ping() == 1                    # manual
    assert manager.enqueue_ping(origin="auto") == 2       # auto: misma secuencia
    assert manager.enqueue_ping() == 3                    # manual

    dls = manager.store.session_downlinks(s["id"])
    assert [(d["seq"], d["origin"]) for d in dls] == \
        [(1, "manual"), (2, "auto"), (3, "manual")]
    assert all(d["fport"] == 98 for d in dls)


def test_ping_auto_sin_sesion_no_envia(manager):
    # El tick automatico que llega justo despues de cerrarse la sesion no
    # dispara nada (el manual suelto si se permite, como diagnostico).
    assert manager.enqueue_ping(origin="auto") is None
    assert manager.chirpstack.ping_calls == []
    assert manager.enqueue_ping() == 1                    # manual suelto: pasa
