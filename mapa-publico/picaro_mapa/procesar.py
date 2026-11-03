"""Funciones puras: de un evento `up` de ChirpStack al registro publico.

Nada de aqui modifica ni interpreta el codec de cada equipo: el `object`
decodificado se publica tal cual. Lo unico que se busca dentro es la posicion.
"""
import hashlib
import hmac

# SNR minimo de demodulacion LoRa por SF (dB). margen = SNR - minimo.
SNR_MIN = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}

CLAVES_LAT = {"lat", "latitude", "latitud"}
CLAVES_LON = {"lon", "lng", "long", "longitude", "longitud"}
CLAVES_ALT = {"alt", "altitude", "altitude_m", "altitud", "alt_m"}


def id_publico(secreto: str, identificador: str) -> str:
    """ID opaco y estable: HMAC del EUI. No se puede revertir sin el secreto."""
    return hmac.new(secreto.encode(), identificador.lower().encode(), hashlib.sha256).hexdigest()[:12]


def margen(snr, sf):
    if snr is None or sf not in SNR_MIN:
        return None
    return round(snr - SNR_MIN[sf], 1)


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _coord_valida(lat, lon) -> bool:
    return (lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
            and not (lat == 0 and lon == 0))


def _por_ruta(obj, ruta: str):
    for parte in ruta.split("."):
        if not isinstance(obj, dict) or parte not in obj:
            return None
        obj = obj[parte]
    return obj


def _buscar_par(obj, prof=0):
    """Primer dict (hasta 3 niveles) con una clave de latitud y otra de longitud."""
    if not isinstance(obj, dict) or prof > 3:
        return None
    claves = {k.lower(): k for k in obj}
    klat = next((claves[k] for k in CLAVES_LAT if k in claves), None)
    klon = next((claves[k] for k in CLAVES_LON if k in claves), None)
    if klat and klon:
        lat, lon = _num(obj[klat]), _num(obj[klon])
        if _coord_valida(lat, lon):
            kalt = next((claves[k] for k in CLAVES_ALT if k in claves), None)
            return lat, lon, (_num(obj[kalt]) if kalt else None)
    for v in obj.values():
        r = _buscar_par(v, prof + 1)
        if r:
            return r
    return None


def extraer_posicion(objeto, tags_perfil: dict):
    """(lat, lon, alt) del payload decodificado, o None.

    Prioridad: campos declarados en los tags del device profile
    (`geo_lat`, `geo_lon`, `geo_alt`, rutas con puntos) y si no, deteccion
    por nombres tipicos.
    """
    if not isinstance(objeto, dict) or not objeto:
        return None
    if tags_perfil.get("geo_lat") and tags_perfil.get("geo_lon"):
        lat = _num(_por_ruta(objeto, tags_perfil["geo_lat"]))
        lon = _num(_por_ruta(objeto, tags_perfil["geo_lon"]))
        if _coord_valida(lat, lon):
            alt = _num(_por_ruta(objeto, tags_perfil["geo_alt"])) if tags_perfil.get("geo_alt") else None
            return lat, lon, alt
        return None
    return _buscar_par(objeto)


def construir_registro(ev: dict, nombres_gw: dict, secreto: str, tags_perfil: dict) -> dict:
    """Registro publico de un uplink. Sin DevEUI, DevAddr, EUIs de gateway ni IPs."""
    tx = ev.get("txInfo") or {}
    lora = ((tx.get("modulation") or {}).get("lora")) or {}
    sf = lora.get("spreadingFactor")
    objeto = ev.get("object")
    if not isinstance(objeto, dict) or not objeto:
        objeto = None

    rx = []
    for r in ev.get("rxInfo") or []:
        gw = (r.get("gatewayId") or "").lower()
        snr = r.get("snr")
        rx.append({
            "gw": id_publico(secreto, gw) if gw else None,
            "gw_nombre": nombres_gw.get(gw, "gateway externo"),
            "rssi": r.get("rssi"),
            "snr": snr,
            "margen": margen(snr, sf),
        })
    rx.sort(key=lambda x: (x["snr"] is None, -(x["snr"] or 0)))
    mejor = rx[0] if rx else {}

    pos = extraer_posicion(objeto, tags_perfil)
    return {
        "ts": ev.get("time"),
        "fcnt": ev.get("fCnt"),
        "fport": ev.get("fPort"),
        "dr": ev.get("dr"),
        "sf": sf,
        "bw_khz": (lora.get("bandwidth") or 0) // 1000 or None,
        "freq_mhz": round(tx["frequency"] / 1e6, 1) if tx.get("frequency") else None,
        "datos": objeto,
        "rx": rx,
        "rssi": mejor.get("rssi"),
        "snr": mejor.get("snr"),
        "margen": mejor.get("margen"),
        "pos": {"lat": pos[0], "lon": pos[1], "alt": pos[2]} if pos else None,
    }


def ubicaciones_gw(ev: dict) -> dict:
    """Posicion que reporta cada gateway en rxInfo (p. ej. con GPS propio)."""
    out = {}
    for r in ev.get("rxInfo") or []:
        loc = r.get("location") or {}
        lat, lon = _num(loc.get("latitude")), _num(loc.get("longitude"))
        if r.get("gatewayId") and _coord_valida(lat, lon):
            out[r["gatewayId"].lower()] = (lat, lon)
    return out
