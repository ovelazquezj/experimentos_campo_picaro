#!/usr/bin/env python3
"""
cruzar.py  -  Cruza lo que la sonda ENVIO con lo que el servidor RECIBIO.

Por que hacen falta las dos fuentes: el servidor solo ve lo que le llego, y no
distingue "no se envio" de "se perdio en el aire". El PDR solo se puede calcular
si el denominador sale del log del propio dispositivo.

  Fuente (a)  CSV de la microSD, uno por corrida  ->  lo ENVIADO
  Fuente (b)  SQLite del dashboard                ->  lo RECIBIDO
  Union       (f_port, fcnt) acotada por ventana temporal de la corrida

El CSV del dispositivo lleva SIEMPRE la tension de bateria, en las seis
corridas. Del lado del servidor no: el payload es de longitud variable y en
CERRO16 (DR0/SF10) solo caben 11 bytes por el dwell time de 400 ms, asi que ahi
va sin la extension de bateria. Para cualquier analisis de bateria hay que usar
la fuente (a). La columna batt_mA va vacia siempre: el AXP2101 del T-Beam
Supreme no mide corriente de bateria, solo tension y porcentaje.

Salidas en el directorio indicado por --salida:
  <run_id>_cruzado.csv   una fila por uplink enviado, con si llego y su rssi/snr
  resumen.csv            una fila por corrida con las metricas
  resumen.txt            el mismo resumen legible, con el control de validez A/C

Uso tipico:
    python cruzar.py --sd ./datos_sd --db ../dashboard/picaro_telemetry.db
"""
import argparse
import csv
import math
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Constantes del experimento
# ---------------------------------------------------------------------------

# Posicion del gateway del laboratorio: se lee de sitios_privados.json (fuera
# de git, ver sitios.py). La plantilla la da redondeada.
from sitios import GATEWAY  # noqa: E402

# Matriz de corridas. Los intervalos NO son de eleccion libre: el servidor tiene
# rx1_delay = 5 s y no se toca, asi que en clase A no se puede transmitir hasta
# cerrar RX1 (5 s) y RX2 (6 s). El ciclo minimo real ronda los 6,5 s.
MATRIZ = {
    "URBANO":  {"dr": 1, "sf": 9,  "intervalo_s": 8, "fport": (11, 12)},
    "TERRAZA": {"dr": 3, "sf": 7,  "intervalo_s": 8, "fport": (13, 14)},
    "CERRO":   {"dr": 0, "sf": 10, "intervalo_s": 8, "fport": (15, 16)},
    # VUELO (D-64): 3 paquetes por rafaga, uno cada 20 s; solo clase A.
    "VUELO":   {"dr": 0, "sf": 10, "intervalo_s": 20, "fport": (17, None)},
}

# fPort por (escenario, clase). Etiqueta cada corrida sin gastar bytes de payload.
FPORT = {
    ("URBANO",  "A"): 11, ("URBANO",  "C"): 12,
    ("TERRAZA", "A"): 13, ("TERRAZA", "C"): 14,
    ("CERRO",   "A"): 15, ("CERRO",   "C"): 16,
    ("VUELO",   "A"): 17,
}

# Uplinks por corrida, fijado ANTES de tomar datos. Con n = 300 y p = 0,8 el
# error estandar del PDR es ~2,3 %: suficiente para comparar escenarios sin
# alargar las corridas de campo mas de la cuenta.
UPLINKS_OBJETIVO = 300
# VUELO: 55 rafagas x 3 paquetes = 55 minutos de vuelo simulado.
UPLINKS_OBJETIVO_ESC = {"VUELO": 165}

# Criterio de aceptacion del PDR, fijado ANTES de tomar datos (ver EXPERIMENTO.md).
PDR_MINIMO = {"URBANO": 0.80, "TERRAZA": 0.80, "CERRO": 0.50,
              # VUELO se mide a distancia y en LoS, como el cerro (D-64).
              "VUELO": 0.50}

ALFA = 0.05          # nivel de significacion del control de validez A vs C
DELTA_PP_MAX = 5.0   # diferencia maxima tolerable en puntos porcentuales


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def haversine_km(a, b):
    """Distancia sobre la esfera entre dos (lat, lon) en grados decimales."""
    r = 6371.0088
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def parse_utc(s):
    """Acepta ISO-8601 con o sin Z, y epoch en segundos."""
    if s is None or s == "":
        return None
    s = str(s).strip()
    try:
        return datetime.fromtimestamp(float(s), timezone.utc)
    except (ValueError, OSError):
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_run_id(run_id):
    """'20260814-CERRO-C' -> ('20260814', 'CERRO', 'C', 1).

    El firmware añade un numero de intento cuando una corrida se aborto con el
    boton y se reanudo el mismo dia sobre el mismo escenario:

        20260814-CERRO16-C      primer intento  -> intento 1
        20260814-CERRO16-C-2    segundo intento -> intento 2

    Sin ese sufijo los dos intentos compartirian fichero y quedarian mezclados.
    Aqui se separan: son corridas DISTINTAS (ver elegir_representativa).

    Tolera CERRO16/CERRO y mayusculas/minusculas. Devuelve None si no encaja.
    """
    partes = str(run_id).strip().upper().split("-")

    # El sufijo de intento es el unico trozo puramente numerico al final. Se
    # separa ANTES de leer la clase: sin esto, '...-C-2' daria clase '2'.
    intento = 1
    if len(partes) >= 4 and partes[-1].isdigit():
        intento = int(partes[-1])
        partes = partes[:-1]

    if len(partes) < 3:
        return None
    fecha, esc, clase = partes[0], "-".join(partes[1:-1]), partes[-1]
    esc = esc.replace("CERRO16", "CERRO").replace("CERRO15", "CERRO")
    if (esc, clase) not in FPORT:
        return None
    return fecha, esc, clase, intento


def f(v, default=None):
    """A float, tolerando vacios y comas decimales."""
    if v is None or v == "":
        return default
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return default


def i(v, default=None):
    x = f(v)
    return default if x is None else int(x)


def percentil(datos, p):
    """Percentil por interpolacion lineal. datos debe venir ordenado."""
    if not datos:
        return None
    if len(datos) == 1:
        return datos[0]
    k = (len(datos) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return datos[int(k)]
    return datos[lo] * (hi - k) + datos[hi] * (k - lo)


def media(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, nd=1, sufijo=""):
    return "n/d" if x is None else f"{x:.{nd}f}{sufijo}"


# ---------------------------------------------------------------------------
# Lectura de las fuentes
# ---------------------------------------------------------------------------

def leer_csv_dispositivo(ruta):
    """Fuente (a): lo que la sonda intento enviar. Una fila por uplink."""
    filas = []
    with open(ruta, newline="", encoding="utf-8-sig") as fh:
        for fila in csv.DictReader(fh):
            fila = {(k or "").strip(): v for k, v in fila.items()}
            if not fila.get("fcnt"):
                continue
            filas.append({
                "run_id":     (fila.get("run_id") or "").strip(),
                "fcnt":       i(fila.get("fcnt")),
                "utc":        parse_utc(fila.get("utc")),
                "lat":        f(fila.get("lat")),
                "lon":        f(fila.get("lon")),
                "alt":        f(fila.get("alt")),
                "sats":       i(fila.get("sats")),
                "fix":        i(fila.get("fix"), 0),
                "temp_c":     f(fila.get("temp_c")),
                "batt_mV":    f(fila.get("batt_mV")),
                "batt_mA":    f(fila.get("batt_mA")),
                "dr":         i(fila.get("dr")),
                "sf":         i(fila.get("sf")),
                "airtime_ms": f(fila.get("airtime_ms")),
                "tx_rc":      i(fila.get("tx_rc"), 0),
                # D-64: solo VUELO las rellena; vacias en las demas corridas.
                "tipo":       i(fila.get("tipo")),
                "rafaga":     i(fila.get("rafaga")),
            })
    filas.sort(key=lambda r: (r["fcnt"] if r["fcnt"] is not None else 0))
    return filas


def leer_recibidos(db, fport, desde, hasta):
    """Fuente (b): lo que llego al servidor, acotado a la corrida.

    Se filtra por f_port Y por ventana temporal. Solo por f_port no basta: si una
    corrida se repite (una parcial y su repeticion) ambas comparten f_port, y si
    el dispositivo rehizo el join el fCnt vuelve a empezar y podria colisionar.
    """
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    sql = "SELECT f_cnt, ts, rssi, snr, gateway_id, dr FROM telemetry WHERE f_port = ?"
    params = [fport]
    if desde is not None:
        sql += " AND ts >= ?"
        params.append(desde.timestamp())
    if hasta is not None:
        sql += " AND ts <= ?"
        params.append(hasta.timestamp())
    out = {}
    for r in con.execute(sql, params):
        if r["f_cnt"] is None:
            continue
        # Si el mismo fCnt llego por varios gateways, nos quedamos con el mejor RSSI.
        prev = out.get(r["f_cnt"])
        if prev is None or (r["rssi"] is not None and (prev["rssi"] is None or r["rssi"] > prev["rssi"])):
            out[r["f_cnt"]] = dict(r)
    con.close()
    return out


def leer_recibidos_app(app_dir, fport, desde, hasta):
    """Fuente (b) desde los CSV descargados de la app (flujo actual).

    Sustituye al SQLite del dashboard viejo: cada CSV de datos_app/ es lo que
    exporta el microservicio para una sesion, con las MISMAS columnas de
    telemetria (ts, f_cnt, f_port, rssi, snr, gateway_id, dr...). Se leen TODOS
    los CSV del directorio y se filtra por f_port + ventana temporal, igual que
    hacia la consulta SQL: asi una corrida repetida (misma etiqueta, otro
    intento) o un rejoin que reinicia el fCnt no se mezclan.
    """
    out = {}
    if not os.path.isdir(app_dir):
        return out
    d0 = desde.timestamp() if desde is not None else None
    d1 = hasta.timestamp() if hasta is not None else None
    for nombre in sorted(os.listdir(app_dir)):
        if not nombre.lower().endswith(".csv"):
            continue
        with open(os.path.join(app_dir, nombre), newline="", encoding="utf-8") as fh:
            for fila in csv.DictReader(fh):
                if i(fila.get("f_port")) != fport:
                    continue
                fc = i(fila.get("f_cnt"))
                if fc is None:
                    continue
                ts = f(fila.get("ts"))
                if ts is not None:
                    if d0 is not None and ts < d0:
                        continue
                    if d1 is not None and ts > d1:
                        continue
                rssi = f(fila.get("rssi"))
                rec = {"f_cnt": fc, "ts": ts, "rssi": rssi,
                       "snr": f(fila.get("snr")),
                       "gateway_id": (fila.get("gateway_id") or None),
                       "dr": i(fila.get("dr"))}
                prev = out.get(fc)
                # Mismo criterio que la fuente SQL: ante duplicados de fCnt, el de
                # mejor RSSI (p. ej. si llego por varios gateways).
                if prev is None or (rssi is not None
                                    and (prev["rssi"] is None or rssi > prev["rssi"])):
                    out[fc] = rec
    return out


# ---------------------------------------------------------------------------
# Cruce de una corrida
# ---------------------------------------------------------------------------

CAMPOS_CRUZADO = [
    "run_id", "escenario", "clase", "intento", "fport", "fcnt", "utc",
    "lat", "lon", "alt", "sats", "fix", "temp_c", "batt_mV", "batt_mA",
    "dr", "sf", "airtime_ms", "tx_rc", "en_aire", "recibido",
    "rssi", "snr", "gateway_id", "dist_gw_km", "tipo", "rafaga",
]


def cruzar_corrida(ruta_csv, recibidos_fn, salida, tolerancia_s):
    """Cruza un CSV de la microSD (enviado) contra el lado recibido.

    `recibidos_fn(fport, desde, hasta)` devuelve {fCnt: {rssi, snr, ...}}; puede
    venir de los CSV de la app (flujo actual) o del SQLite del dashboard (viejo).
    """
    enviados = leer_csv_dispositivo(ruta_csv)
    if not enviados:
        print(f"  [!] {os.path.basename(ruta_csv)}: sin filas utiles, se omite")
        return None

    run_id = enviados[0]["run_id"] or os.path.splitext(os.path.basename(ruta_csv))[0]
    ident = parse_run_id(run_id)
    if ident is None:
        print(f"  [!] {os.path.basename(ruta_csv)}: run_id '{run_id}' no reconocido "
              f"(se espera AAAAMMDD-ESCENARIO-CLASE[-INTENTO]), se omite")
        return None
    _, escenario, clase, intento = ident
    fport = FPORT[(escenario, clase)]

    tiempos = [r["utc"] for r in enviados if r["utc"]]
    desde = min(tiempos) - timedelta(seconds=tolerancia_s) if tiempos else None
    hasta = max(tiempos) + timedelta(seconds=tolerancia_s) if tiempos else None

    recibidos = recibidos_fn(fport, desde, hasta)

    filas, rssis, snrs, dists = [], [], [], []
    airtime_total = 0.0
    dist_recorrida = 0.0
    ant = None
    n_aire = n_rx = 0

    for r in enviados:
        en_aire = (r["tx_rc"] == 0)
        rx = recibidos.get(r["fcnt"]) if en_aire else None
        if en_aire:
            n_aire += 1
            airtime_total += r["airtime_ms"] or 0.0
        if rx:
            n_rx += 1
            if rx["rssi"] is not None:
                rssis.append(float(rx["rssi"]))
            if rx["snr"] is not None:
                snrs.append(float(rx["snr"]))

        d_gw = None
        if r["fix"] and r["lat"] is not None and r["lon"] is not None:
            d_gw = haversine_km((r["lat"], r["lon"]), GATEWAY)
            dists.append(d_gw)
            if ant is not None:
                dist_recorrida += haversine_km(ant, (r["lat"], r["lon"]))
            ant = (r["lat"], r["lon"])

        filas.append({
            "run_id": run_id, "escenario": escenario, "clase": clase,
            "intento": intento, "fport": fport,
            "fcnt": r["fcnt"],
            "utc": r["utc"].isoformat() if r["utc"] else "",
            "lat": r["lat"], "lon": r["lon"], "alt": r["alt"], "sats": r["sats"],
            "fix": r["fix"], "temp_c": r["temp_c"],
            "batt_mV": r["batt_mV"], "batt_mA": r["batt_mA"],
            "dr": r["dr"], "sf": r["sf"], "airtime_ms": r["airtime_ms"], "tx_rc": r["tx_rc"],
            "en_aire": int(en_aire), "recibido": int(bool(rx)),
            "rssi": rx["rssi"] if rx else None,
            "snr": rx["snr"] if rx else None,
            "gateway_id": rx["gateway_id"] if rx else None,
            "dist_gw_km": round(d_gw, 4) if d_gw is not None else None,
            "tipo": r.get("tipo"), "rafaga": r.get("rafaga"),
        })

    os.makedirs(salida, exist_ok=True)
    destino = os.path.join(salida, f"{run_id}_cruzado.csv")
    with open(destino, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS_CRUZADO)
        w.writeheader()
        w.writerows(filas)

    dur_s = (max(tiempos) - min(tiempos)).total_seconds() if len(tiempos) > 1 else 0.0
    n_total = len(enviados)
    rssis.sort(); snrs.sort()

    # Huerfanos: llegaron al servidor pero no constan en el log del dispositivo.
    # Sintoma tipico de una ventana temporal mal acotada o de dos corridas mezcladas.
    huerfanos = len([k for k in recibidos if k not in {r["fcnt"] for r in enviados}])

    return {
        "run_id": run_id, "escenario": escenario, "clase": clase,
        "intento": intento, "fport": fport,
        "enviados_total": n_total,
        "tx_fallidos": n_total - n_aire,
        "enviados_aire": n_aire,
        "recibidos": n_rx,
        "huerfanos": huerfanos,
        # PDR de propagacion: denominador = lo que de verdad salio por la antena.
        "pdr": (n_rx / n_aire) if n_aire else None,
        # PDR bruto: incluye los fallos de transmision del propio equipo.
        "pdr_bruto": (n_rx / n_total) if n_total else None,
        "rssi_medio": media(rssis), "rssi_p10": percentil(rssis, 10), "rssi_p90": percentil(rssis, 90),
        "snr_medio": media(snrs), "snr_p10": percentil(snrs, 10), "snr_p90": percentil(snrs, 90),
        "dist_gw_media_km": media(dists), "dist_gw_max_km": max(dists) if dists else None,
        "dist_recorrida_km": dist_recorrida,
        "airtime_total_s": airtime_total / 1000.0,
        "duracion_s": dur_s,
        "ciclo_trabajo_pct": (airtime_total / 1000.0 / dur_s * 100.0) if dur_s > 0 else None,
        "batt_inicial_mV": next((r["batt_mV"] for r in enviados if r["batt_mV"]), None),
        "batt_final_mV": next((r["batt_mV"] for r in reversed(enviados) if r["batt_mV"]), None),
        "completa": n_total >= UPLINKS_OBJETIVO_ESC.get(escenario, UPLINKS_OBJETIVO),
        "cumple_pdr": (n_rx / n_aire >= PDR_MINIMO[escenario]) if n_aire else False,
        "_fichero": destino,
    }


# ---------------------------------------------------------------------------
# Control de validez A vs C
# ---------------------------------------------------------------------------

def chi2_p(recibidos_a, n_a, recibidos_c, n_c):
    """p-valor de un chi-cuadrado 2x2 de proporciones. Devuelve (chi2, p)."""
    tabla = [[recibidos_a, n_a - recibidos_a], [recibidos_c, n_c - recibidos_c]]
    try:
        from scipy.stats import chi2_contingency
        chi2, p, _, _ = chi2_contingency(tabla, correction=True)
        return chi2, p
    except ImportError:
        # Sin scipy: chi2 con correccion de Yates y p por la funcion de
        # supervivencia de la chi-cuadrado con 1 gl, que es erfc(sqrt(x/2)).
        n = n_a + n_c
        filas = [n_a, n_c]
        cols = [recibidos_a + recibidos_c, n - (recibidos_a + recibidos_c)]
        if 0 in filas or 0 in cols:
            return None, None
        chi2 = 0.0
        for r in (0, 1):
            for c in (0, 1):
                esp = filas[r] * cols[c] / n
                chi2 += (abs(tabla[r][c] - esp) - 0.5) ** 2 / esp
        return chi2, math.erfc(math.sqrt(chi2 / 2.0))


def elegir_representativa(resumenes):
    """Una corrida por (escenario, clase): la de MAS uplinks enviados.

    Los intentos son corridas distintas y TODOS quedan en resumen.csv, pero la
    comparacion A vs C y las figuras necesitan una sola por celda. Se elige la
    mas completa porque un intento abortado a los 20 uplinks no describe el
    escenario, solo describe por que se aborto.

    Devuelve (representativas, descartadas). Las descartadas SE AVISAN: un
    descarte silencioso se leeria como "solo hubo una corrida", que es
    justamente el error que el sufijo de intento vino a evitar.
    """
    por_celda = {}
    for r in resumenes:
        por_celda.setdefault((r["escenario"], r["clase"]), []).append(r)

    representativas, descartadas = [], []
    for _, grupo in sorted(por_celda.items()):
        grupo = sorted(grupo, key=lambda x: (-x["enviados_total"], x["run_id"]))
        representativas.append(grupo[0])
        descartadas.extend(grupo[1:])
    return representativas, descartadas


def control_validez(resumenes):
    """La clase describe al receptor: no puede afectar al enlace de subida.

    Si el PDR difiere entre A y C en el MISMO escenario, el problema esta en el
    metodo (condiciones que cambiaron entre corridas), no en el hallazgo.

    Se exigen las DOS condiciones para dar la alarma: p < alfa Y |delta| > 5 pp.
    Con estos tamanos de muestra el chi-cuadrado marca como significativas
    diferencias de pocos puntos sin relevancia practica; pedir ambas evita
    descartar corridas buenas por significancia estadistica vacia.
    """
    out = []
    por_esc = {}
    # Solo la representativa de cada celda: comparar A contra C usando un
    # intento abortado daria una diferencia que es del metodo, no del enlace.
    representativas, _ = elegir_representativa(resumenes)
    for r in representativas:
        por_esc.setdefault(r["escenario"], {})[r["clase"]] = r
    for esc, d in sorted(por_esc.items()):
        if MATRIZ[esc]["fport"][1] is None:
            continue    # escenario solo clase A (VUELO): no hay A vs C que controlar
        a, c = d.get("A"), d.get("C")
        if not a or not c or not a["enviados_aire"] or not c["enviados_aire"]:
            out.append({"escenario": esc, "estado": "INCOMPLETO",
                        "detalle": "falta una de las dos clases"})
            continue
        chi2, p = chi2_p(a["recibidos"], a["enviados_aire"], c["recibidos"], c["enviados_aire"])
        delta_pp = (a["pdr"] - c["pdr"]) * 100.0
        significativo = (p is not None and p < ALFA)
        relevante = abs(delta_pp) > DELTA_PP_MAX
        if significativo and relevante:
            estado = "REVISAR"
        elif significativo:
            estado = "OK (dif. significativa pero < 5 pp: sin relevancia practica)"
        else:
            estado = "OK"
        out.append({"escenario": esc, "estado": estado, "chi2": chi2, "p": p,
                    "delta_pp": delta_pp, "pdr_a": a["pdr"], "pdr_c": c["pdr"]})
    return out


# ---------------------------------------------------------------------------
# Informes
# ---------------------------------------------------------------------------

CAMPOS_RESUMEN = [
    "run_id", "escenario", "clase", "intento", "fport", "enviados_total", "tx_fallidos",
    "enviados_aire", "recibidos", "huerfanos", "pdr", "pdr_bruto",
    "rssi_medio", "rssi_p10", "rssi_p90", "snr_medio", "snr_p10", "snr_p90",
    "dist_gw_media_km", "dist_gw_max_km", "dist_recorrida_km",
    "airtime_total_s", "duracion_s", "ciclo_trabajo_pct",
    "batt_inicial_mV", "batt_final_mV", "completa", "cumple_pdr",
]


def escribir_resumen(resumenes, validez, salida):
    with open(os.path.join(salida, "resumen.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS_RESUMEN, extrasaction="ignore")
        w.writeheader()
        for r in sorted(resumenes, key=lambda x: x["fport"]):
            w.writerow(r)

    lineas = []
    lineas.append("RESUMEN DE CORRIDAS")
    lineas.append("=" * 78)
    lineas.append("")
    lineas.append(f"{'corrida':22} {'env':>5} {'aire':>5} {'rx':>5} {'PDR':>7} "
                  f"{'RSSI':>7} {'SNR':>6} {'dist max':>9}  criterio")
    lineas.append("-" * 78)
    for r in sorted(resumenes, key=lambda x: x["fport"]):
        crit = "cumple" if r["cumple_pdr"] else f"NO (min {PDR_MINIMO[r['escenario']]*100:.0f}%)"
        if not r["completa"]:
            crit += " / PARCIAL"
        lineas.append(
            f"{r['run_id']:22} {r['enviados_total']:5d} {r['enviados_aire']:5d} "
            f"{r['recibidos']:5d} {fmt((r['pdr'] or 0)*100, 1, '%'):>7} "
            f"{fmt(r['rssi_medio'], 1):>7} {fmt(r['snr_medio'], 1):>6} "
            f"{fmt(r['dist_gw_max_km'], 2, ' km'):>9}  {crit}")
        if r["huerfanos"]:
            lineas.append(f"{'':22} [!] {r['huerfanos']} paquetes en el servidor sin "
                          f"correspondencia en el log del dispositivo")
    lineas.append("")
    lineas.append("PDR = recibidos / enviados_al_aire (excluye los fallos de TX del equipo).")
    lineas.append("La columna 'env' incluye los intentos fallidos; su diferencia con 'aire'")
    lineas.append("mide problemas del propio dispositivo, no de propagacion.")
    _, descartadas = elegir_representativa(resumenes)
    if descartadas:
        lineas.append("")
        lineas.append("INTENTOS MULTIPLES")
        lineas.append("=" * 78)
        lineas.append("Alguna combinacion escenario/clase tiene mas de una corrida: se aborto")
        lineas.append("con el boton y se reanudo. Todas estan arriba y en resumen.csv, pero el")
        lineas.append("control de validez y las figuras usan la MAS COMPLETA de cada celda.")
        lineas.append("No se han usado para comparar:")
        for r in sorted(descartadas, key=lambda x: (x["fport"], x["intento"])):
            lineas.append(f"  {r['run_id']:24} intento {r['intento']}  "
                          f"{r['enviados_total']:4d} uplinks")

    lineas.append("")
    lineas.append("CONTROL DE VALIDEZ  (clase A vs C en el mismo escenario)")
    lineas.append("=" * 78)
    lineas.append("La clase no puede afectar al enlace de subida. Una diferencia real")
    lineas.append(f"apunta a un problema de metodo. Alarma solo si p < {ALFA} Y |delta| > {DELTA_PP_MAX:.0f} pp.")
    lineas.append("")
    for v in validez:
        if v["estado"] == "INCOMPLETO":
            lineas.append(f"  {v['escenario']:10} INCOMPLETO — {v['detalle']}")
            continue
        lineas.append(
            f"  {v['escenario']:10} PDR A={fmt((v['pdr_a'] or 0)*100,1,'%')} "
            f"C={fmt((v['pdr_c'] or 0)*100,1,'%')}  "
            f"delta={v['delta_pp']:+.1f} pp  "
            f"chi2={fmt(v['chi2'],2)}  p={fmt(v['p'],4)}  -> {v['estado']}")
    texto = "\n".join(lineas)
    with open(os.path.join(salida, "resumen.txt"), "w", encoding="utf-8") as fh:
        fh.write(texto + "\n")
    return texto


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Cruza los CSV de la microSD (enviado) con los de la app (recibido).")
    ap.add_argument("--sd", default="./datos_sd",
                    help="directorio con los CSV de la microSD (lo ENVIADO)")
    ap.add_argument("--app", default="./datos_app",
                    help="directorio con los CSV descargados de la app (lo RECIBIDO). "
                         "Es la fuente por defecto del lado recibido.")
    ap.add_argument("--db", default=None,
                    help="ALTERNATIVA a --app: SQLite del dashboard viejo. Solo si se "
                         "indica, se usa el dashboard en vez de los CSV de la app.")
    ap.add_argument("--salida", default="./resultados",
                    help="directorio donde escribir los cruces y el resumen")
    ap.add_argument("--tolerancia-s", type=float, default=120.0,
                    help="holgura al acotar la ventana temporal de cada corrida")
    args = ap.parse_args()

    if not os.path.isdir(args.sd):
        sys.exit(f"[x] No existe el directorio de la microSD: {args.sd}")

    # Lado RECIBIDO: los CSV de la app por defecto; el dashboard solo si se pide.
    if args.db:
        if not os.path.isfile(args.db):
            sys.exit(f"[x] No existe la base de datos: {args.db}")
        recibidos_fn = lambda fp, d0, d1: leer_recibidos(args.db, fp, d0, d1)
        fuente = f"dashboard {args.db}"
    else:
        if not os.path.isdir(args.app):
            sys.exit(f"[x] No existe el directorio de la app: {args.app}. "
                     f"Pon ahi los CSV descargados de la app, o usa --db.")
        recibidos_fn = lambda fp, d0, d1: leer_recibidos_app(args.app, fp, d0, d1)
        fuente = f"CSV de la app en {args.app}"

    entradas = sorted(
        os.path.join(args.sd, n) for n in os.listdir(args.sd)
        if n.lower().endswith(".csv") and not n.lower().startswith("downlink")
    )
    if not entradas:
        sys.exit(f"[x] No hay CSV de corridas en {args.sd}")

    print(f"Cruzando {len(entradas)} corrida(s): microSD {args.sd}  x  {fuente}\n")
    resumenes = []
    for ruta in entradas:
        r = cruzar_corrida(ruta, recibidos_fn, args.salida, args.tolerancia_s)
        if r:
            resumenes.append(r)
            print(f"  {r['run_id']:22} {r['recibidos']}/{r['enviados_aire']} "
                  f"recibidos  PDR {fmt((r['pdr'] or 0)*100,1,'%')}")

    if not resumenes:
        sys.exit("\n[x] Ninguna corrida pudo procesarse.")

    print()
    print(escribir_resumen(resumenes, control_validez(resumenes), args.salida))
    print(f"\nEscrito en {os.path.abspath(args.salida)}")


if __name__ == "__main__":
    main()
