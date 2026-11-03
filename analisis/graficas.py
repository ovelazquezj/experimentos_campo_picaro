#!/usr/bin/env python3
"""
graficas.py  -  Genera las figuras del experimento a partir de la salida de
cruzar.py.

Entrada:  ./resultados/*_cruzado.csv  y  ./resultados/resumen.csv
Salida:   ./resultados/figuras/*.png

Figuras:
  1_pdr.png            PDR por escenario y clase (barras agrupadas)
  2_rssi_snr_dist.png  RSSI y SNR frente a distancia al gateway
  3_bateria.png        Descarga de bateria, clase A vs C, con pendiente
  4_latencia.png       Latencia de downlink A vs C  (requiere downlinks.csv)
  5_mapa.png           Puntos geograficos coloreados por RSSI

Uso:
    python graficas.py --resultados ./resultados
"""
import argparse
import csv
import math
import os
import sys
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")          # sin ventana: funciona por SSH y en scripts
import matplotlib.pyplot as plt

# Posicion del gateway del laboratorio, de sitios_privados.json (ver sitios.py)
from sitios import GATEWAY  # noqa: E402

# Un color por escenario, un estilo de linea por clase. Asi una figura en blanco
# y negro sigue distinguiendo las clases.
COLOR_ESC = {"URBANO": "#1f77b4", "TERRAZA": "#2ca02c", "CERRO": "#d62728"}
ESTILO_CLASE = {"A": "-", "C": "--"}
MARCA_CLASE = {"A": "o", "C": "s"}
ORDEN_ESC = ["URBANO", "TERRAZA", "CERRO"]


def f(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return default


def parse_utc(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def cargar_cruzados(directorio):
    """Devuelve ({(escenario, clase): [filas]}, descartados) de los *_cruzado.csv.

    Si una celda tiene varios intentos (corrida abortada con el boton y
    reanudada) se queda con el MAS COMPLETO, igual que hace cruzar.py para el
    control de validez. No es solo consistencia: concatenar dos intentos
    falsearia la pendiente de bateria, que se mide sobre el tiempo transcurrido
    DENTRO de una corrida, y dibujaria un salto ficticio en el mapa al volver
    del final de un intento al principio del siguiente.
    """
    por_run = defaultdict(list)
    celda_de = {}
    for nombre in sorted(os.listdir(directorio)):
        if not nombre.endswith("_cruzado.csv"):
            continue
        with open(os.path.join(directorio, nombre), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rid = r.get("run_id") or os.path.basename(nombre)
                por_run[rid].append(r)
                celda_de[rid] = (r["escenario"], r["clase"])

    mejor = {}
    for rid, filas in por_run.items():
        celda = celda_de[rid]
        if celda not in mejor or len(filas) > len(por_run[mejor[celda]]):
            mejor[celda] = rid

    datos, descartados = {}, []
    for rid in sorted(por_run):
        celda = celda_de[rid]
        if mejor[celda] == rid:
            datos[celda] = por_run[rid]
        else:
            descartados.append((rid, len(por_run[rid])))
    return datos, descartados


def cargar_resumen(directorio):
    ruta = os.path.join(directorio, "resumen.csv")
    if not os.path.isfile(ruta):
        return []
    with open(ruta, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def guardar(fig, ruta):
    fig.tight_layout()
    fig.savefig(ruta, dpi=140)
    plt.close(fig)
    print(f"  {os.path.basename(ruta)}")


# ---------------------------------------------------------------------------
# 1. PDR por escenario y clase
# ---------------------------------------------------------------------------

def fig_pdr(resumen, salida):
    if not resumen:
        return
    escenarios = [e for e in ORDEN_ESC if any(r["escenario"] == e for r in resumen)]
    if not escenarios:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    ancho = 0.35
    xs = range(len(escenarios))
    for k, clase in enumerate(["A", "C"]):
        vals, etiquetas = [], []
        for e in escenarios:
            # De haber varios intentos, el mas completo. Coger el primero que
            # aparezca dibujaria en la grafica de portada una corrida que quiza
            # se aborto a los 20 uplinks, sin que nada lo delatara.
            candidatos = [x for x in resumen
                          if x["escenario"] == e and x["clase"] == clase]
            r = max(candidatos, key=lambda x: f(x.get("enviados_total"), 0)) \
                if candidatos else None
            v = (f(r["pdr"]) * 100) if r and f(r["pdr"]) is not None else 0.0
            vals.append(v)
            etiquetas.append(f"{v:.1f}%" if r else "n/d")
        pos = [x + (k - 0.5) * ancho for x in xs]
        barras = ax.bar(pos, vals, ancho, label=f"Clase {clase}",
                        color=["#4c72b0" if clase == "A" else "#dd8452"] * len(vals),
                        edgecolor="black", linewidth=0.6)
        for b, t in zip(barras, etiquetas):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, t,
                    ha="center", va="bottom", fontsize=9)

    # Umbrales de aceptacion fijados antes de tomar datos.
    for e, umbral in [("URBANO", 80), ("TERRAZA", 80), ("CERRO", 50)]:
        if e in escenarios:
            x = escenarios.index(e)
            ax.plot([x - 0.5, x + 0.5], [umbral, umbral], color="red",
                    linestyle=":", linewidth=1.5)
    ax.plot([], [], color="red", linestyle=":", label="criterio de aceptacion")

    ax.set_xticks(list(xs))
    ax.set_xticklabels(escenarios)
    ax.set_ylabel("PDR (%)")
    ax.set_ylim(0, 108)
    ax.set_title("Tasa de entrega (PDR) por escenario y clase")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    guardar(fig, os.path.join(salida, "1_pdr.png"))


# ---------------------------------------------------------------------------
# 2. RSSI y SNR frente a distancia
# ---------------------------------------------------------------------------

def fig_rssi_snr(datos, salida):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    hay = False
    for (esc, clase), filas in sorted(datos.items()):
        pts = [(f(r["dist_gw_km"]), f(r["rssi"]), f(r["snr"])) for r in filas
               if r["recibido"] == "1" and f(r["dist_gw_km"]) is not None]
        if not pts:
            continue
        hay = True
        d = [p[0] for p in pts]
        ax1.scatter(d, [p[1] for p in pts], s=10, alpha=0.5,
                    color=COLOR_ESC.get(esc, "gray"), marker=MARCA_CLASE[clase],
                    label=f"{esc} {clase}")
        ax2.scatter(d, [p[2] for p in pts], s=10, alpha=0.5,
                    color=COLOR_ESC.get(esc, "gray"), marker=MARCA_CLASE[clase],
                    label=f"{esc} {clase}")
    if not hay:
        plt.close(fig)
        print("  [!] 2_rssi_snr_dist.png omitida: no hay paquetes recibidos con posicion")
        return
    ax1.set_ylabel("RSSI (dBm)"); ax1.grid(alpha=0.3); ax1.legend(fontsize=8, ncol=2)
    ax1.set_title("Calidad de enlace frente a distancia al gateway")
    ax2.set_ylabel("SNR (dB)"); ax2.set_xlabel("Distancia al gateway (km)")
    ax2.grid(alpha=0.3)
    guardar(fig, os.path.join(salida, "2_rssi_snr_dist.png"))


# ---------------------------------------------------------------------------
# 3. Descarga de bateria
# ---------------------------------------------------------------------------

def pendiente(xs, ys):
    """Regresion lineal simple. Devuelve la pendiente (unidades de y por x)."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def fig_bateria(datos, salida):
    """Descarga de bateria. El dato viene SIEMPRE del CSV de la microSD.

    No se puede tomar del lado servidor: el payload es de longitud variable y en
    CERRO16 (DR0/SF10) solo caben 11 bytes por el dwell time de 400 ms, asi que
    ahi el uplink va sin la extension de bateria. En el CSV del dispositivo si
    esta, en las seis corridas, porque ese log no pasa por la radio.

    Aviso metodologico: estas curvas NO sirven para comparar la autonomia de
    clase A frente a C. En una corrida de ~40 min la diferencia de consumo entre
    ambas queda por debajo del ruido de la lectura del PMU. La autonomia se mide
    en banco (ver la Adenda 1 de EXPERIMENTO.md); esta figura solo documenta que
    la bateria aguanto la corrida.
    """
    fig, ax = plt.subplots(figsize=(9, 5))
    hay = False
    sin_bateria = []
    resumen_pendientes = []
    for (esc, clase), filas in sorted(datos.items()):
        pts = []
        for r in filas:
            t, mv = parse_utc(r["utc"]), f(r["batt_mV"])
            if t and mv:
                pts.append((t, mv))
        if len(pts) < 2:
            sin_bateria.append(f"{esc} {clase}")
            continue
        hay = True
        t0 = pts[0][0]
        mins = [(t - t0).total_seconds() / 60.0 for t, _ in pts]
        mv = [v for _, v in pts]
        ax.plot(mins, mv, ESTILO_CLASE[clase], color=COLOR_ESC.get(esc, "gray"),
                linewidth=1.4, label=f"{esc} {clase}")
        m = pendiente(mins, mv)
        if m is not None:
            resumen_pendientes.append((esc, clase, m * 60.0))   # mV/hora
    if not hay:
        plt.close(fig)
        print("  [!] 3_bateria.png omitida: no hay lecturas de bateria en los CSV "
              "de la microSD (¿se cruzaron solo datos del servidor?)")
        return
    if sin_bateria:
        print(f"  [!] 3_bateria.png: sin lecturas de bateria en {', '.join(sin_bateria)}. "
              "El dato vive en el CSV de la microSD, no en el uplink.")
    ax.set_xlabel("Tiempo desde el inicio de la corrida (min)")
    ax.set_ylabel("Tension de bateria (mV)")
    ax.set_title("Descarga de bateria durante las corridas\n"
                 "(no comparable entre clases: la autonomia se mide en banco)",
                 fontsize=11)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncol=2)

    if resumen_pendientes:
        txt = "Pendiente (mV/h):\n" + "\n".join(
            f"  {e} {c}: {m:+.1f}" for e, c, m in resumen_pendientes)
        ax.text(0.98, 0.02, txt, transform=ax.transAxes, ha="right", va="bottom",
                fontsize=8, family="monospace",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
    guardar(fig, os.path.join(salida, "3_bateria.png"))


# ---------------------------------------------------------------------------
# 4. Latencia de downlink
# ---------------------------------------------------------------------------

def fig_latencia(ruta_downlinks, salida):
    """Formato esperado de downlinks.csv:

        run_id,seq,utc_enviado,utc_recibido

    La latencia se calcula como utc_recibido - utc_enviado. Es donde la clase C
    deberia ganar por goleada: en clase A el downlink espera al siguiente
    uplink, en clase C llega casi de inmediato.
    """
    if not os.path.isfile(ruta_downlinks):
        print("  [!] 4_latencia.png omitida: no existe downlinks.csv "
              "(columnas: run_id,seq,utc_enviado,utc_recibido)")
        return
    por_clase = defaultdict(list)
    with open(ruta_downlinks, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            run = (r.get("run_id") or "").strip().upper()
            clase = run.split("-")[-1] if "-" in run else ""
            t0, t1 = parse_utc(r.get("utc_enviado")), parse_utc(r.get("utc_recibido"))
            if clase in ("A", "C") and t0 and t1:
                lat = (t1 - t0).total_seconds()
                if lat >= 0:
                    por_clase[clase].append(lat)
    if not por_clase:
        print("  [!] 4_latencia.png omitida: downlinks.csv sin filas utilizables")
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    for clase in ("A", "C"):
        if por_clase.get(clase):
            ax1.hist(por_clase[clase], bins=20, alpha=0.6, label=f"Clase {clase}")
    ax1.set_xlabel("Latencia (s)"); ax1.set_ylabel("Nº de downlinks")
    ax1.set_title("Distribucion de latencia"); ax1.legend(); ax1.grid(alpha=0.3)

    clases = [c for c in ("A", "C") if por_clase.get(c)]
    # Las etiquetas se ponen aparte: el parametro 'labels' de boxplot cambio de
    # nombre en matplotlib 3.9 y asi funciona en cualquier version.
    ax2.boxplot([por_clase[c] for c in clases])
    ax2.set_xticklabels([f"Clase {c}" for c in clases])
    ax2.set_ylabel("Latencia (s)"); ax2.set_title("Comparativa"); ax2.grid(alpha=0.3)
    for i, c in enumerate(clases, start=1):
        v = sorted(por_clase[c])
        mediana = v[len(v) // 2]
        ax2.text(i, mediana, f" mediana {mediana:.2f}s  n={len(v)}",
                 va="center", fontsize=8)
    guardar(fig, os.path.join(salida, "4_latencia.png"))


# ---------------------------------------------------------------------------
# 5. Mapa
# ---------------------------------------------------------------------------

def fig_mapa(datos, salida):
    fig, ax = plt.subplots(figsize=(8.5, 8))
    hay = False
    rx_lat, rx_lon, rx_rssi, perd_lat, perd_lon = [], [], [], [], []
    for filas in datos.values():
        for r in filas:
            lat, lon = f(r["lat"]), f(r["lon"])
            if lat is None or lon is None or r["fix"] != "1":
                continue
            hay = True
            if r["recibido"] == "1" and f(r["rssi"]) is not None:
                rx_lat.append(lat); rx_lon.append(lon); rx_rssi.append(f(r["rssi"]))
            else:
                perd_lat.append(lat); perd_lon.append(lon)
    if not hay:
        plt.close(fig)
        print("  [!] 5_mapa.png omitida: no hay posiciones con fix")
        return
    if rx_lat:
        sc = ax.scatter(rx_lon, rx_lat, c=rx_rssi, cmap="viridis", s=14, alpha=0.85)
        fig.colorbar(sc, ax=ax, label="RSSI (dBm)")
    if perd_lat:
        ax.scatter(perd_lon, perd_lat, marker="x", color="red", s=22,
                   label=f"perdidos ({len(perd_lat)})")
    ax.scatter([GATEWAY[1]], [GATEWAY[0]], marker="*", s=320, color="black",
               edgecolor="white", linewidth=0.8, label="gateway", zorder=5)
    ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud")
    ax.set_title("Cobertura: posiciones y RSSI")
    ax.grid(alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    # Proporcion correcta: un grado de longitud mide menos que uno de latitud.
    lat_media = sum(rx_lat + perd_lat) / max(1, len(rx_lat + perd_lat))
    ax.set_aspect(1.0 / math.cos(math.radians(lat_media)))
    guardar(fig, os.path.join(salida, "5_mapa.png"))


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Figuras del experimento de terreno.")
    ap.add_argument("--resultados", default="./resultados",
                    help="directorio de salida de cruzar.py")
    ap.add_argument("--downlinks", default=None,
                    help="CSV de downlinks (por defecto <resultados>/../datos_sd/downlinks.csv)")
    args = ap.parse_args()

    if not os.path.isdir(args.resultados):
        sys.exit(f"[x] No existe {args.resultados}. Ejecuta antes cruzar.py")

    datos, descartados = cargar_cruzados(args.resultados)
    if not datos:
        sys.exit(f"[x] No hay ficheros *_cruzado.csv en {args.resultados}")
    resumen = cargar_resumen(args.resultados)

    if descartados:
        print("[!] Hay varios intentos de la misma corrida. Se usa el mas completo;")
        print("    estos NO entran en las figuras (siguen en resumen.csv):")
        for rid, n in descartados:
            print(f"      {rid}  ({n} uplinks)")
        print()

    salida = os.path.join(args.resultados, "figuras")
    os.makedirs(salida, exist_ok=True)
    downlinks = args.downlinks or os.path.join(
        os.path.dirname(os.path.abspath(args.resultados)), "datos_sd", "downlinks.csv")

    print(f"Generando figuras en {os.path.abspath(salida)}\n")
    fig_pdr(resumen, salida)
    fig_rssi_snr(datos, salida)
    fig_bateria(datos, salida)
    fig_latencia(downlinks, salida)
    fig_mapa(datos, salida)
    print("\nListo.")


if __name__ == "__main__":
    main()
