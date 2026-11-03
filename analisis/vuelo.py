#!/usr/bin/env python3
"""
vuelo.py  -  Analisis de las corridas VUELO (D-64, docs/VUELO-ESPEC.md).

Cada corrida VUELO se hace desde UN punto fijo (un cerro, una azotea). El
resultado de la campana es un punto por corrida en el plano distancia -> margen,
que se compara con la curva que predijo la jornada del cerro del 2026-09-27
(analisis/resultados/20260927_cerro/INFORME.md §6):

    margen_SF10(d) = 12,8 dB - 20 log10(d / 15,27 km)        (n = 2, LoS)

Entradas
  datos_app/*-VUELO-A*.csv     lado RECIBIDO (CSV de la app / microservicio)
  datos_sd/*-VUELO-A*.csv      lado ENVIADO (microSD), opcional: si esta, el PDR
                               sale con el denominador real; si no, por fCnt

Salida: resultados/vuelo/{resumen.txt, puntos.csv, figuras/*.png}

Uso:  python vuelo.py
"""
import collections
import csv
import glob
import json
import math
import os
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AQUI, "resultados", "vuelo")

# Posicion del gateway del laboratorio, de sitios_privados.json (ver sitios.py)
from sitios import GATEWAY  # noqa: E402
GW_ALT_M = 1929.5            # antena del SenseCap, msnm (A-05)
LIMITE_SF10 = -15.0          # SNR minimo de demodulacion, dB (SX1302)
REF_D_KM, REF_MARGEN = 15.27, 12.8   # medida del cerro, 2026-09-27
TIPOS = ("posicion", "ambiente", "navegacion")

C_MEDIDO, C_MODELO, TINTA2, REJILLA = "#2a78d6", "#52514e", "#52514e", "#e4e3df"


def haversine_km(a, b):
    r = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def q(v, p):
    v = sorted(v)
    return v[int(round(p * (len(v) - 1)))] if v else None


def modelo_margen(d_km):
    return REF_MARGEN - 20 * math.log10(d_km / REF_D_KM)


def run_id_de(ruta):
    return os.path.splitext(os.path.basename(ruta))[0]


def cargar_recibido(ruta):
    filas = []
    with open(ruta, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("f_port") not in ("17", 17):
                continue
            obj = (json.loads(r["raw_json"]).get("object") or {}) if r.get("raw_json") else {}
            filas.append({
                "fcnt": int(r["f_cnt"]), "ts": float(r["ts"]),
                "rssi": float(r["rssi"]) if r["rssi"] else None,
                "snr": float(r["snr"]) if r["snr"] else None,
                # ChirpStack manda los numeros del object como double (0.0).
                "tipo": obj.get("tipo_paquete"),
                "rafaga": int(obj["rafaga"]) if obj.get("rafaga") is not None else None,
                "lat": obj.get("latitude"), "lon": obj.get("longitude"),
                "alt": obj.get("altitude_m"),
            })
    return sorted(filas, key=lambda x: x["fcnt"])


def cargar_enviado(run_id):
    ruta = os.path.join(AQUI, "datos_sd", run_id + ".csv")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if r.get("fcnt")]


def analizar(ruta):
    run_id = run_id_de(ruta)
    rx = cargar_recibido(ruta)
    if not rx:
        return None
    fc = [x["fcnt"] for x in rx]
    env = cargar_enviado(run_id)
    if env:
        aire = [r for r in env if (r.get("tx_rc") or "0") == "0"]
        denom, fuente = len(aire), "microSD"
    else:
        denom, fuente = max(fc) - min(fc) + 1, "fCnt"

    # Posicion del punto fijo: mediana de los P1 con fix (la sonda no se mueve).
    pos = [(x["lat"], x["lon"], x["alt"]) for x in rx if x["tipo"] == "posicion" and x["lat"] is not None]
    lat = st.median(p[0] for p in pos) if pos else None
    lon = st.median(p[1] for p in pos) if pos else None
    alt = st.median(p[2] for p in pos if p[2] is not None) if pos else None
    d_h = haversine_km((lat, lon), GATEWAY) if pos else None
    d = math.hypot(d_h, ((alt or GW_ALT_M) - GW_ALT_M) / 1000.0) if pos else None

    sn = [x["snr"] for x in rx if x["snr"] is not None]
    rs = [x["rssi"] for x in rx if x["rssi"] is not None]
    por_tipo = collections.Counter(x["tipo"] for x in rx)
    raf = collections.defaultdict(set)
    for x in rx:
        if x["rafaga"] is not None:
            raf[x["rafaga"]].add(x["tipo"])
    n_raf = (max(raf) + 1) if raf else 0
    completas = sum(1 for k in raf if len(raf[k]) == 3)
    return {
        "run_id": run_id, "fuente_denominador": fuente,
        "recibidos": len(rx), "denominador": denom, "pdr": len(rx) / denom if denom else None,
        "lat": lat, "lon": lon, "alt_m": alt,
        "dist_km": d, "dist_horiz_km": d_h,
        "desnivel_m": (alt - GW_ALT_M) if alt is not None else None,
        "rssi_media": st.mean(rs) if rs else None, "snr_media": st.mean(sn) if sn else None,
        "snr_p5": q(sn, .05),
        "margen_p5": (q(sn, .05) - LIMITE_SF10) if sn else None,
        "margen_modelo": modelo_margen(d) if d else None,
        "por_tipo": {t: por_tipo.get(t, 0) for t in TIPOS},
        "rafagas": n_raf, "rafagas_completas": completas,
        "rafagas_perdidas": sum(1 for k in range(n_raf) if k not in raf),
    }


def fmt(v, p=1):
    return "-" if v is None else f"{v:.{p}f}"


def main():
    rutas = sorted(glob.glob(os.path.join(AQUI, "datos_app", "*-VUELO-A*.csv")))
    rutas = [r for r in rutas if not r.endswith("_dl.csv")]
    res = [r for r in (analizar(x) for x in rutas) if r]
    os.makedirs(os.path.join(OUT, "figuras"), exist_ok=True)

    L = ["Corridas VUELO (D-64). Margen = SNR p5 - limite SF10 (-15 dB).",
         f"Modelo: margen(d) = {REF_MARGEN} - 20 log10(d / {REF_D_KM} km)  [cerro 2026-09-27, n=2]", ""]
    for r in res:
        L += [f"== {r['run_id']} ==",
              f"  punto          {fmt(r['lat'], 5)}, {fmt(r['lon'], 5)}  alt {fmt(r['alt_m'], 0)} m"
              f"  (desnivel {fmt(r['desnivel_m'], 0)} m sobre el gateway)",
              f"  distancia      {fmt(r['dist_km'], 2)} km (horizontal {fmt(r['dist_horiz_km'], 2)})",
              f"  PDR            {fmt(100 * r['pdr'] if r['pdr'] is not None else None)} %"
              f"  ({r['recibidos']}/{r['denominador']}, denominador: {r['fuente_denominador']})",
              f"  por paquete    {r['por_tipo']}",
              f"  rafagas        {r['rafagas_completas']} completas de {r['rafagas']}  · {r['rafagas_perdidas']} perdidas",
              f"  RSSI / SNR     {fmt(r['rssi_media'])} dBm / {fmt(r['snr_media'], 2)} dB (p5 {fmt(r['snr_p5'], 2)})",
              f"  margen p5      {fmt(r['margen_p5'])} dB medido  vs  {fmt(r['margen_modelo'])} dB del modelo", ""]
    if not res:
        L.append("(sin corridas VUELO en datos_app/)")
    with open(os.path.join(OUT, "resumen.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    with open(os.path.join(OUT, "puntos.csv"), "w", newline="", encoding="utf-8") as fh:
        campos = [k for k in (res[0].keys() if res else []) if k != "por_tipo"] + list(TIPOS)
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for r in res:
            w.writerow({**{k: v for k, v in r.items() if k != "por_tipo"}, **r["por_tipo"]})
    print("\n".join(L))
    figura(res)


def figura(res):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ds = [x / 2 for x in range(1, 161)]
    ax.plot(ds, [modelo_margen(d) for d in ds], color=C_MODELO, lw=1.5, label="modelo (cerro, n = 2)")
    for reserva, estilo in ((10, ":"), (6, "--"), (0, "-")):
        ax.axhline(reserva, color=REJILLA if reserva else TINTA2, lw=1, ls=estilo)
        ax.text(80.5, reserva + .4, f"reserva {reserva} dB" if reserva else "límite", fontsize=8,
                color=TINTA2, ha="right")
    pts = [r for r in res if r["dist_km"] and r["margen_p5"] is not None]
    ax.plot([r["dist_km"] for r in pts], [r["margen_p5"] for r in pts], "o", ms=8, color=C_MEDIDO,
            mec="white", mew=2, label="VUELO medido (SNR p5)")
    for r in pts:
        ax.annotate(f"{r['run_id'][:8]}\n{100 * r['pdr']:.0f} %", (r["dist_km"], r["margen_p5"]),
                    textcoords="offset points", xytext=(6, 6), fontsize=8, color=TINTA2)
    ax.plot([REF_D_KM], [REF_MARGEN], "s", ms=7, color=C_MODELO, label="cerro 2026-09-27 (CERRO16-A)")
    ax.set_xlim(0, 80)
    ax.set_xlabel("distancia al gateway (km)")
    ax.set_ylabel("margen de SNR sobre SF10 (dB)")
    ax.set_title("VUELO: margen medido frente al modelo de alcance", loc="left", fontsize=11)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=REJILLA, lw=.8)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figuras", "margen_vs_distancia.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
