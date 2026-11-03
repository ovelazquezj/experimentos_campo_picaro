import json

from picaro_mapa import procesar
from picaro_mapa.store import Store

# Evento `up` real (LR1121, LinkCheck sin payload) con dos gateways; EUIs de ejemplo.
EVENTO = {
    "time": "2026-10-17T15:54:34.473+00:00",
    "deviceInfo": {"tenantId": "t", "devEui": "aabbccddeeff0001", "tags": {}},
    "devAddr": "01234567", "dr": 3, "fCnt": 80, "fPort": 0, "object": {},
    "rxInfo": [
        {"gatewayId": "7076ffaabbccdd01", "rssi": -73, "snr": 15.0,
         "location": {"latitude": 22.16, "longitude": -102.27, "altitude": 1926.0}},
        {"gatewayId": "7076ffaabbccdd02", "rssi": -54, "snr": 14.5, "location": {}},
    ],
    "txInfo": {"frequency": 905300000, "modulation": {"lora": {"bandwidth": 125000, "spreadingFactor": 7}}},
}


def test_registro_sin_identificadores():
    reg = procesar.construir_registro(EVENTO, {"7076ffaabbccdd01": "GW-A"}, "s", {})
    txt = json.dumps(reg)
    for prohibido in ("aabbccddeeff0001", "7076ffaabbccdd01", "7076ffaabbccdd02", "01234567"):
        assert prohibido not in txt
    assert reg["datos"] is None and reg["pos"] is None
    assert reg["sf"] == 7 and reg["bw_khz"] == 125 and reg["freq_mhz"] == 905.3
    assert reg["rx"][0]["gw_nombre"] == "GW-A" and reg["rx"][0]["margen"] == 22.5
    assert reg["rx"][1]["gw_nombre"] == "gateway externo"


def test_posicion_codec_radiosonda():
    # Radiosonda-Terreno / ESP32_MECA: latitude/longitude/altitude_m
    obj = {"latitude": 21.88, "longitude": -102.29, "altitude_m": 1890, "gps_fix": True}
    assert procesar.extraer_posicion(obj, {}) == (21.88, -102.29, 1890.0)


def test_sin_fix_no_hay_posicion():
    assert procesar.extraer_posicion({"latitude": None, "longitude": None}, {}) is None
    assert procesar.extraer_posicion({"lat": 0, "lon": 0}, {}) is None
    # Codecs sin geolocalizacion (Heltec, Meteoro, LR1110 GNSS)
    assert procesar.extraer_posicion({"counter": 3, "vbat_mv": 4000}, {}) is None
    assert procesar.extraer_posicion({"sensores": {"dht11": True}, "lux": 10}, {}) is None


def test_posicion_anidada_y_override():
    assert procesar.extraer_posicion({"gps": {"Lat": 22.1, "Lng": -102.2}}, {}) == (22.1, -102.2, None)
    tags = {"geo_lat": "nav.y", "geo_lon": "nav.x"}
    assert procesar.extraer_posicion({"nav": {"y": 22.2, "x": -102.3}}, tags) == (22.2, -102.3, None)
    # Con override declarado no se adivina
    assert procesar.extraer_posicion({"latitude": 22.0, "longitude": -102.0}, tags) is None


def test_id_publico_estable():
    a = procesar.id_publico("s", "AABBCCDDEEFF0001")
    assert a == procesar.id_publico("s", "aabbccddeeff0001") and len(a) == 12
    assert a != procesar.id_publico("otro", "aabbccddeeff0001")


def test_store_historial_y_perdidos(tmp_path):
    st = Store(str(tmp_path / "m.db"), 7)
    import time
    base = time.time()
    for i, fcnt in enumerate([1, 2, 5, 6, 0, 1]):  # 2 perdidos, luego rejoin
        st.guardar("n", {"ts": None, "fcnt": fcnt, "rssi": -80, "snr": 5, "margen": 20,
                         "datos": {"temp": 20 + i, "ok": True, "s": {"x": 1}},
                         "pos": {"lat": 22.0, "lon": -102.0, "alt": None} if i == 2 else None})
    h = st.historial("n")
    assert h["uplinks"] == 6 and h["perdidos"] == 2
    assert set(h["serie"]["campos"]) == {"temp", "s.x"}
    assert all(len(v) == len(h["serie"]["ts"]) for v in h["serie"]["campos"].values())
    assert st.posicion("n")["lat"] == 22.0
    assert st.ultimo("n")["fcnt"] == 1
    assert base


def test_purga_conserva_el_ultimo(tmp_path):
    st = Store(str(tmp_path / "m.db"), 7)
    viejo = "2020-01-01T00:00:00+00:00"
    for f in (1, 2):
        st.guardar("apagado", {"ts": viejo, "fcnt": f})
    st.guardar("vivo", {"ts": None, "fcnt": 9})
    st.purgar()
    assert st.ultimo("apagado")["fcnt"] == 2      # se conserva: no vuelve a "sin datos"
    assert st.historial("apagado")["uplinks"] == 0  # pero no cuenta en la ventana de 7 dias
    assert st.ultimo("vivo")["fcnt"] == 9
