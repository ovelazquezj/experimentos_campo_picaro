#!/usr/bin/env python3
"""
cerro_20260927.py  -  Analisis de la jornada del Cerro del Muerto (2026-09-27).

Solo lado RECIBIDO (servidor): la microSD de la sonda aun no se ha descargado,
asi que el denominador sale de los huecos de fCnt, no del log del equipo. Es
valido aqui porque los uplinks son no confirmados y RadioLib no repite fCnt;
cuando llegue la microSD, cruzar.py dara el PDR definitivo.

Entradas (datos crudos locales, NO se publican; ver datos_*/LEEME.md):
  datos_app/20260927-CERRO16-A.csv       sesion 41 del microservicio (T-Beam)
  datos_app/20260927-CERRO16-A_dl.csv    pings encolados en esa sesion
  datos_lns/20260927_mqtt_ttgo_tbeam.jsonl  captura MQTT de ambos nodos
  datos_lns/20260927_chirpstack_log_sondas.txt  log de ChirpStack (joins/MIC)

Salida:  resultados/20260927_cerro/{resumen.txt, figuras/*.png}

Uso:  python cerro_20260927.py
"""
import base64
import collections
import csv
import json
import os
import statistics as st
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AQUI, "resultados", "20260927_cerro")
FIG = os.path.join(OUT, "figuras")

# EUIs reales de las placas y gateways: de sitios_privados.json (ver sitios.py)
from sitios import EUI  # noqa: E402
TBEAM, TTGO = EUI["tbeam"], EUI["ttgo"]
SENSECAP, GW00 = EUI["gw_sensecap_lab"], EUI["gw_itpa_gw00"]
CANALES = [903_900_000 + 200_000 * i for i in range(8)]     # US915 sub-banda 2

# Limite de demodulacion LoRa (SNR minimo, datasheet SX1261/2 / SX1302), dB
SNR_LIMITE = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0}
# Sensibilidad tipica del SX1302 a 125 kHz, dBm (datasheet, CR 4/5)
SENSIB = {7: -125.0, 10: -134.0}

# Paleta categorica validada (dataviz, slots 1 y 2) + tinta de texto
C_TBEAM, C_TTGO = "#2a78d6", "#eb6834"
TINTA, TINTA2, REJILLA = "#0b0b0b", "#52514e", "#e4e3df"


def toa_ms(pl_bytes, sf, bw=125_000, cr=1, preambulo=8, low_dr=None):
    """Time-on-air LoRa (formula de Semtech AN1200.13), header explicito, CRC on."""
    import math
    if low_dr is None:
        low_dr = 1 if (sf >= 11 and bw == 125_000) else 0
    ts = (2 ** sf) / bw * 1000
    num = 8 * pl_bytes - 4 * sf + 28 + 16
    n = 8 + max(math.ceil(num / (4 * (sf - 2 * low_dr))) * (cr + 4), 0)
    return (preambulo + 4.25) * ts + n * ts


def cargar_sesion(path):
    filas = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            e = json.loads(r["raw_json"])
            filas.append({
                "fcnt": int(r["f_cnt"]), "t": float(r["ts"]), "freq": int(r["freq"]),
                "rx": e.get("rxInfo", []), "alt": float(r["altitude_m"] or 0),
                "lat": float(r["latitude"] or 0), "lon": float(r["longitude"] or 0),
                "temp": float(r["temperature_c"]) if r["temperature_c"] else None,
                "pl": len(base64.b64decode(e.get("data", ""))),
            })
    return sorted(filas, key=lambda x: x["fcnt"])


def cargar_mqtt(path):
    ev = collections.defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for linea in f:
            topic, _, js = linea.partition(" ")
            try:
                e = json.loads(js)
            except ValueError:
                continue
            ev[(e["deviceInfo"]["devEui"], topic.rsplit("/", 1)[1])].append(e)
    return ev


def mejor_rx(rx):
    """El gateway con mejor SNR de un uplink (el que decide si llega)."""
    rx = [x for x in rx if x.get("snr") is not None]
    return max(rx, key=lambda x: x["snr"]) if rx else None


def perdidos(fcnts):
    s = set(fcnts)
    return [f for f in range(min(fcnts), max(fcnts) + 1) if f not in s]


def canal_de_perdidos(filas, desde=0):
    """RadioLib agota los 8 canales antes de repetir (selectChannels +
    channelFlags): cada bloque alineado de 8 fCnt usa cada canal una vez. Se
    busca la alineacion sin repeticiones y, en cada bloque con una sola perdida,
    el canal que falta es el del paquete perdido."""
    rx = {x["fcnt"]: x["freq"] for x in filas}
    hi = max(rx)
    def repes(o):
        n = 0
        for s in range(o - 8, hi + 1, 8):
            ch = [rx[f] for f in range(s, s + 8) if f in rx]
            n += len(ch) - len(set(ch))
        return n
    off = min(range(8), key=repes)
    res, ambiguos = {}, []
    for s in range(off - 8, hi + 1, 8):
        bloque = [f for f in range(s, s + 8) if f >= min(rx) and f <= hi]
        faltan = [f for f in bloque if f not in rx]
        if not faltan:
            continue
        libres = set(CANALES) - {rx[f] for f in bloque if f in rx}
        if len(faltan) == 1 and len(libres) == 1:
            res[faltan[0]] = libres.pop()
        else:
            ambiguos.append((faltan, sorted(libres)))
    return off, repes(off), res, ambiguos


def q(v, p):
    v = sorted(v)
    return v[int(round(p * (len(v) - 1)))]


def estadisticas(nombre, filas, sf, lineas):
    fc = [x["fcnt"] for x in filas]
    lost = perdidos(fc)
    esperados = max(fc) - min(fc) + 1
    best = [mejor_rx(x["rx"]) for x in filas]
    rs = [b["rssi"] for b in best if b]
    sn = [b["snr"] for b in best if b]
    gws = collections.Counter(g["gatewayId"] for x in filas for g in x["rx"])
    dt = [b["t"] - a["t"] for a, b in zip(filas, filas[1:]) if b["fcnt"] == a["fcnt"] + 1]
    pl = collections.Counter(x["pl"] for x in filas).most_common(1)[0][0]
    t0 = datetime.fromtimestamp(filas[0]["t"], timezone.utc)
    t1 = datetime.fromtimestamp(filas[-1]["t"], timezone.utc)
    rafagas = collections.Counter()
    run = 0
    for a, b in zip(lost, lost[1:] + [None]):
        run += 1
        if b != a + 1:
            rafagas[run] += 1
            run = 0
    lineas += [
        f"== {nombre} ==",
        f"  ventana UTC        {t0:%H:%M:%S} - {t1:%H:%M:%S}  ({(filas[-1]['t'] - filas[0]['t']) / 60:.1f} min)",
        f"  fCnt               {min(fc)}-{max(fc)}  esperados {esperados}  recibidos {len(fc)}  perdidos {len(lost)}",
        f"  PDR (por fCnt)     {100 * len(fc) / esperados:.1f} %",
        f"  rafagas de perdida {dict(sorted(rafagas.items()))}  (longitud: veces)",
        f"  intervalo mediano  {st.median(dt):.1f} s",
        f"  SF / payload       SF{sf}, {pl} B de FRMPayload -> PHY {pl + 13} B, ToA {toa_ms(pl + 13, sf):.0f} ms",
        f"  RSSI dBm           media {st.mean(rs):.1f}  mediana {st.median(rs):.0f}  p5 {q(rs, .05):.0f}  p95 {q(rs, .95):.0f}  [{min(rs)}, {max(rs)}]  sd {st.pstdev(rs):.1f}",
        f"  SNR dB             media {st.mean(sn):.2f}  mediana {st.median(sn):.2f}  p5 {q(sn, .05):.2f}  p95 {q(sn, .95):.2f}  [{min(sn)}, {max(sn)}]",
        f"  margen SNR p5      {q(sn, .05) - SNR_LIMITE[sf]:.1f} dB sobre el limite SF{sf} ({SNR_LIMITE[sf]} dB)",
        f"  margen RSSI p5     {q(rs, .05) - SENSIB[sf]:.0f} dB sobre la sensibilidad SF{sf} ({SENSIB[sf]} dBm)",
        f"  gateways           {dict(gws)}",
    ]
    return lost, rs, sn


def main():
    os.makedirs(FIG, exist_ok=True)
    L = []

    # --- T-Beam: sesion 41 (CERRO16-A) --------------------------------------
    tb = cargar_sesion(os.path.join(AQUI, "datos_app", "20260927-CERRO16-A.csv"))
    lost_tb, rs_tb, sn_tb = estadisticas("T-Beam Supreme  CERRO16-A  (sesion 41, DR0/SF10, clase A)", tb, 10, L)
    alt = [x["alt"] for x in tb if x["alt"]]
    temp = [x["temp"] for x in tb if x["temp"] is not None]
    L.append(f"  posicion           {tb[0]['lat']:.5f}, {tb[0]['lon']:.5f}  alt {min(alt):.0f}-{max(alt):.0f} m  T {min(temp)}-{max(temp)} C")

    # Por canal
    off, rep, chl, amb = canal_de_perdidos(tb)
    rx_ch = collections.Counter(x["freq"] for x in tb)
    lost_ch = collections.Counter(chl.values())
    L.append(f"  ciclo de canales   alineacion fCnt%8={off}, repeticiones dentro de bloque = {rep} (0 = ciclo de 8 confirmado)")
    L.append("  canal MHz   recibidos  perdidos(inferidos)  PDR   RSSI  SNR")
    for ch in CANALES:
        sel = [mejor_rx(x["rx"]) for x in tb if x["freq"] == ch]
        n_rx, n_l = rx_ch[ch], lost_ch[ch]
        L.append(f"    {ch / 1e6:7.1f}   {n_rx:5d}      {n_l:5d}            {100 * n_rx / (n_rx + n_l):5.1f}  "
                 f"{st.mean(s['rssi'] for s in sel if s):6.1f} {st.mean(s['snr'] for s in sel if s):5.2f}")
    for faltan, libres in amb:
        L.append(f"    ambiguo: fCnt {faltan} -> uno de {[c / 1e6 for c in libres]}")
    ult = max(lost_tb)
    L.append(f"  ultima perdida     fCnt {ult}; de ahi al final ({max(x['fcnt'] for x in tb)}) no se pierde ninguno")

    # Downlinks (pings) de la sesion
    with open(os.path.join(AQUI, "datos_app", "20260927-CERRO16-A_dl.csv"), encoding="utf-8") as f:
        dl = list(csv.DictReader(f))
    org = collections.Counter(d["origin"] for d in dl)
    L.append(f"  pings encolados    {len(dl)} {dict(org)}  (entrega en la sonda: pendiente de la microSD)")

    # --- TTGO: captura MQTT ---------------------------------------------------
    ev = cargar_mqtt(os.path.join(AQUI, "datos_lns", "20260927_mqtt_ttgo_tbeam.jsonl"))
    tt = []
    for e in ev[(TTGO, "up")]:
        tt.append({"fcnt": e["fCnt"], "t": datetime.fromisoformat(e["time"][:26] + "+00:00").timestamp(),
                   "freq": e["txInfo"]["frequency"], "rx": e["rxInfo"], "alt": 0, "lat": 0, "lon": 0,
                   "temp": None, "pl": len(base64.b64decode(e.get("data", "")))})
    tt.sort(key=lambda x: x["fcnt"])
    L.append("")
    lost_tt, rs_tt, sn_tt = estadisticas("TTGO T3 (LMIC)  referencia  (captura MQTT, DR3/SF7, clase A, ADR on)", tt, 7, L)
    L.append(f"  perdidos           fCnt {lost_tt}")

    # Solape: T-Beam en la misma ventana que el TTGO
    t_ini, t_fin = tt[0]["t"], tt[-1]["t"]
    tb_sol = [x for x in tb if t_ini <= x["t"] <= t_fin]
    fc = [x["fcnt"] for x in tb_sol]
    L.append("")
    L.append(f"== Comparacion en la ventana comun ({len(tt)} uplinks TTGO) ==")
    L.append(f"  T-Beam SF10: PDR {100 * len(fc) / (max(fc) - min(fc) + 1):.1f} %  SNR medio "
             f"{st.mean(mejor_rx(x['rx'])['snr'] for x in tb_sol if mejor_rx(x['rx'])):.2f} dB")
    L.append(f"  TTGO   SF7 : PDR {100 * len(tt) / (max(x['fcnt'] for x in tt) - min(x['fcnt'] for x in tt) + 1):.1f} %  "
             f"SNR medio {st.mean(sn_tt):.2f} dB")

    # --- Clase C: el re-join que no cerro -----------------------------------
    L.append("")
    L.append("== Corridas CERRO16-C (sesiones 42 y 43): 0 uplinks ==")
    with open(os.path.join(AQUI, "datos_lns", "20260927_chirpstack_log_sondas.txt"), encoding="utf-8") as f:
        log = f.read().splitlines()
    joins = [l[11:19] + "  DevNonce " + l.rsplit("dev_nonce=", 1)[1]
             for l in log if TBEAM in l and "Device-nonce validated" in l]
    mic = [l[11:19] for l in log if "Invalid MIC" in l]
    L.append("  JoinRequest aceptados: " + " | ".join(joins))
    L.append(f"  JoinRequest con MIC invalido: {len(mic)}  ({mic[0]} ... {mic[-1]})")
    L.append("    " + " ".join(mic))

    with open(os.path.join(OUT, "resumen.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))

    figuras(tb, tt, lost_tb, chl, rx_ch, lost_ch, sn_tb, sn_tt)


def estilo(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(TINTA2)
    ax.tick_params(colors=TINTA2, labelsize=9)
    ax.grid(axis="y", color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)


def figuras(tb, tt, lost_tb, chl, rx_ch, lost_ch, sn_tb, sn_tt):
    plt.rcParams.update({"font.size": 10, "text.color": TINTA, "axes.labelcolor": TINTA2})
    ts = lambda x: datetime.fromtimestamp(x["t"], timezone.utc)

    # 1. RSSI y SNR en el tiempo (dos paneles, mismo eje x: no es doble eje)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True)
    for filas, color, nom in ((tb, C_TBEAM, "T-Beam SF10"), (tt, C_TTGO, "TTGO SF7")):
        b = [(ts(x), mejor_rx(x["rx"])) for x in filas]
        b = [(t, r) for t, r in b if r]
        a1.plot([t for t, _ in b], [r["rssi"] for _, r in b], "o", ms=3.5, color=color, label=nom, alpha=.85)
        a2.plot([t for t, _ in b], [r["snr"] for _, r in b], "o", ms=3.5, color=color, label=nom, alpha=.85)
    # Perdidas del T-Beam como marcas en la base del panel RSSI
    t_de = {x["fcnt"]: x["t"] for x in tb}
    for f in lost_tb:
        prev = max(k for k in t_de if k < f)
        t = datetime.fromtimestamp(t_de[prev] + 8.0 * (f - prev), timezone.utc)
        a1.axvline(t, ymin=0, ymax=.06, color=TINTA2, lw=1.2)
    a2.axhline(SNR_LIMITE[10], color=C_TBEAM, lw=1, ls="--")
    a2.axhline(SNR_LIMITE[7], color=C_TTGO, lw=1, ls="--")
    a2.text(a2.get_xlim()[0], SNR_LIMITE[10] + .4, " limite SF10", color=TINTA2, fontsize=8)
    a2.text(a2.get_xlim()[0], SNR_LIMITE[7] + .4, " limite SF7", color=TINTA2, fontsize=8)
    a1.set_ylabel("RSSI (dBm)")
    a2.set_ylabel("SNR (dB)")
    a1.set_title("Cerro del Muerto -> SenseCap del laboratorio (15,3 km, LoS) · 2026-09-27",
                 loc="left", fontsize=11, color=TINTA)
    a1.plot([], [], "|", color=TINTA2, ms=10, mew=1.2, label="T-Beam perdido")
    a1.legend(frameon=False, loc="upper right", fontsize=9)
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    a2.set_xlabel("hora UTC")
    for a in (a1, a2):
        estilo(a)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "1_rssi_snr_tiempo.png"), dpi=150)
    plt.close(fig)

    # 2. Recibidos y perdidos por canal (T-Beam): barras apiladas con gap
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = range(len(CANALES))
    rec = [rx_ch[c] for c in CANALES]
    per = [lost_ch[c] for c in CANALES]
    ax.bar(x, rec, width=.62, color=C_TBEAM, label="recibidos", edgecolor="white", linewidth=2)
    ax.bar(x, per, bottom=rec, width=.62, color="none", edgecolor=TINTA2, hatch="////",
           linewidth=1, label="perdidos (canal inferido)")
    for i, (r, p) in enumerate(zip(rec, per)):
        ax.text(i, r + p + .6, f"{100 * r / (r + p):.0f} %", ha="center", fontsize=9, color=TINTA)
    ax.set_ylim(0, max(r + p for r, p in zip(rec, per)) * 1.15)
    ax.set_xticks(list(x), [f"{c / 1e6:.1f}" for c in CANALES])
    ax.set_xlabel("canal (MHz) — PDR encima de cada barra")
    ax.set_ylabel("uplinks")
    ax.set_title("T-Beam CERRO16-A: casi todas las pérdidas caen en 905,3 MHz", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    estilo(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "2_perdidas_por_canal.png"), dpi=150)
    plt.close(fig)

    # 3. Distribucion de SNR con el margen hasta el limite de cada SF
    fig, ax = plt.subplots(figsize=(9, 4.2))
    bins = [b / 2 for b in range(-42, 14)]
    ax.hist(sn_tb, bins=bins, color=C_TBEAM, alpha=.85, label="T-Beam SF10", edgecolor="white", linewidth=1)
    ax.hist(sn_tt, bins=bins, color=C_TTGO, alpha=.85, label="TTGO SF7", edgecolor="white", linewidth=1)
    for sf, color in ((10, C_TBEAM), (7, C_TTGO)):
        ax.axvline(SNR_LIMITE[sf], color=color, ls="--", lw=1.2)
        ax.text(SNR_LIMITE[sf] + .2, ax.get_ylim()[1] * .9, f"límite SF{sf}", color=TINTA2, fontsize=8)
    ax.set_xlabel("SNR en el gateway (dB)")
    ax.set_ylabel("uplinks")
    ax.set_title("Margen de SNR: ~15 dB en SF10 frente a ~8 dB en SF7", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    estilo(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "3_snr_margen.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
