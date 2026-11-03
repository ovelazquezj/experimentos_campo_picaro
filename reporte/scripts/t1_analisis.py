#!/usr/bin/env python3
"""
t1_analisis.py - Analisis experimental y estadistico de las pruebas de terreno (T1).

Lee SOLO los CSV anonimizados de ../datos/ (sesiones, telemetria, downlinks,
latencias, pdr, sitios, perfil_cerro). No toca datos crudos ni el servidor.

Salidas:
  ../figuras/t1_*.png           figuras (matplotlib, 150 dpi)
  ../borradores/t1_cifras/*.csv tablas con todas las cifras que cita el borrador
  stdout                        resumen legible de cada resultado

Uso (desde cualquier carpeta):
    python -I t1_analisis.py

Es autocontenido: no importa nada fuera de esta carpeta. La regresion lineal
simple pendiente() es la misma del analisis original del proyecto.

Convencion de las figuras: coma decimal y signo menos tipografico, como el texto
del reporte.
"""
import math
import os

import matplotlib
matplotlib.use("Agg")          # sin ventana
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter
from scipy import stats

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.normpath(os.path.join(AQUI, "..", "datos"))
FIGURAS = os.path.normpath(os.path.join(AQUI, "..", "figuras"))
CIFRAS = os.path.normpath(os.path.join(AQUI, "..", "borradores", "t1_cifras"))

import matplotlib.pyplot as plt  # noqa: E402

MENOS = "\u2212"


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


def coma(x, d=1, signo=False):
    """Numero con coma decimal y signo menos tipografico (convencion del reporte)."""
    t = f"{x:+.{d}f}" if signo else f"{x:.{d}f}"
    return t.replace(".", ",").replace("-", MENOS)


_FMT = FuncFormatter(lambda v, _p: f"{v:g}".replace(".", ",").replace("-", MENOS))

os.makedirs(FIGURAS, exist_ok=True)
os.makedirs(CIFRAS, exist_ok=True)

# ---------------------------------------------------------------------------
# Estilo (skill dataviz: paleta de referencia, modo claro)
# ---------------------------------------------------------------------------
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TENUE = "#898781"
REJILLA = "#e1e0d9"
EJE = "#c3c2b7"
C_A = "#2a78d6"      # serie 1 (azul): Clase A / serie principal
C_C = "#eb6834"      # serie 2 (naranja): Clase C
C_3 = "#1baf7a"      # serie 3 (aqua): segunda medida de una misma entidad
COLOR_CLASE = {"A": C_A, "C": C_C}

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE,
    "savefig.facecolor": SUPERFICIE, "axes.edgecolor": EJE,
    "axes.labelcolor": TINTA_2, "xtick.color": TINTA_2, "ytick.color": TINTA_2,
    "text.color": TINTA, "axes.titlecolor": TINTA, "axes.titlesize": 11.5,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelsize": 10, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "legend.fontsize": 9, "lines.linewidth": 2,
    "font.size": 10,
})


def guardar(fig, nombre):
    # Coma decimal en los ejes lineales con formateador automatico.
    for ax in fig.axes:
        for eje, escala in ((ax.xaxis, ax.get_xscale()), (ax.yaxis, ax.get_yscale())):
            if escala == "linear" and type(eje.get_major_formatter()).__name__ == "ScalarFormatter":
                eje.set_major_formatter(_FMT)
    ruta = os.path.join(FIGURAS, nombre)
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  figura: {nombre}")


def tabla(df, nombre):
    df.to_csv(os.path.join(CIFRAS, nombre), index=False, encoding="utf-8")


def wilson(k, n, z=1.959964):
    """IC de Wilson al 95 % (EXPERIMENTO §8.2)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    medio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centro - medio), min(1.0, centro + medio))


def pct(x, d=1):
    return "n/d" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.{d}f} %"


def seccion(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
ses = pd.read_csv(os.path.join(DATOS, "sesiones.csv"))
tel = pd.read_csv(os.path.join(DATOS, "telemetria.csv"), parse_dates=["ts_utc"])
dls = pd.read_csv(os.path.join(DATOS, "downlinks.csv"), parse_dates=["ts_utc"])
lat = pd.read_csv(os.path.join(DATOS, "latencias.csv"),
                  parse_dates=["ts_encolado_utc", "ts_txack_utc", "uplink_previo_utc"])
pdr_sd = pd.read_csv(os.path.join(DATOS, "pdr.csv"))
perfil = pd.read_csv(os.path.join(DATOS, "perfil_cerro.csv"))

SONDA_CORTA = {"radiosonda PiCARO (T-Beam Supreme)": "T-Beam",
               "radiosonda PiCARO (T3/LoRa32)": "T3/LoRa32"}
ses["sonda_c"] = ses["sonda"].map(SONDA_CORTA)
validas = ses[ses["valida_para_analisis"] == 1].copy()

# ---------------------------------------------------------------------------
# 0. Sesiones validas y excluidas
# ---------------------------------------------------------------------------
seccion("0. Sesiones validas y excluidas")


def categoria_motivo(m):
    cats = []
    for parte in str(m).split(" | "):
        if parte.startswith("aborted con N="):
            cats.append("abortada con N < 30")
        elif parte.startswith("banco:"):
            cats.append("banco documentado con etiqueta de otro escenario")
        elif parte.startswith("repetida"):
            cats.append("repetida (abortada y rehecha el mismo dia)")
        elif parte.startswith("incidente"):
            cats.append("incidente de la sesion 66")
    return cats


excl = ses[ses["valida_para_analisis"] == 0].copy()
excl["categorias"] = excl["motivo_exclusion"].apply(categoria_motivo)
filas = []
for cat in ["abortada con N < 30", "banco documentado con etiqueta de otro escenario",
            "repetida (abortada y rehecha el mismo dia)", "incidente de la sesion 66"]:
    ids = [int(r.session_id) for r in excl.itertuples() if cat in r.categorias]
    filas.append({"motivo": cat, "sesiones": len(ids), "ids": ";".join(map(str, ids))})
t_excl = pd.DataFrame(filas)
print(f"Sesiones totales {len(ses)} | validas {len(validas)} | excluidas {len(excl)}")
print("(una sesion puede tener varios motivos)")
print(t_excl.to_string(index=False))
tabla(t_excl, "exclusiones.csv")

# ---------------------------------------------------------------------------
# 1. PDR por sesion (microSD si existe; si no, huecos de fCnt)
# ---------------------------------------------------------------------------
seccion("1. PDR por escenario, sitio y clase (Wilson 95 %)")

sd_por_sesion = pdr_sd.set_index("session_id")
filas = []
for r in validas.itertuples():
    if r.session_id in sd_por_sesion.index:
        s = sd_por_sesion.loc[r.session_id]
        k, n, metodo = int(s.recibidos), int(s.enviados_aire), "microSD"
    else:
        if pd.isna(r.fcnt_min):
            continue
        k = int(r.recibidos)
        n = int(r.fcnt_max - r.fcnt_min + 1)
        metodo = "huecos fCnt"
    lo, hi = wilson(k, n)
    filas.append({"session_id": r.session_id, "run_label": r.run_label,
                  "sonda": r.sonda_c, "escenario": r.escenario, "clase": r.clase,
                  "sitio": r.sitio, "recibidos": k, "intentados": n,
                  "pdr": k / n, "ic95_inf": lo, "ic95_sup": hi, "metodo": metodo,
                  "dist_gw_mediana_km": r.dist_gw_mediana_km})
pdr_ses = pd.DataFrame(filas)
tabla(pdr_ses.round(4), "pdr_por_sesion.csv")

# Celdas de analisis. URBANO se separa por sitio: la etiqueta URBANO incluye
# mediciones estaticas junto a un gateway (sitio LAB_BANCO / ITPA).
def celda(r):
    if r.escenario == "VUELO":
        return f"VUELO {r.sonda} @ {r.sitio}"
    if r.escenario == "URBANO" and r.sitio == "URBANO_MOVIL":
        return "URBANO movil"
    if r.escenario == "URBANO":
        return f"Banco ({r.sitio})"
    return r.escenario


pdr_ses["celda"] = pdr_ses.apply(celda, axis=1)
CRITERIO = {"URBANO movil": 0.80, "TERRAZA": 0.80, "CERRO16": 0.50}

filas = []
for (c, cl), g in pdr_ses.groupby(["celda", "clase"], sort=False):
    k, n = g.recibidos.sum(), g.intentados.sum()
    lo, hi = wilson(k, n)
    het = float("nan")
    if len(g) > 1 and 0 < k < n:
        cont = np.array([g.recibidos, g.intentados - g.recibidos]).T
        het = stats.chi2_contingency(cont, correction=False)[1]
    filas.append({"celda": c, "clase": cl, "sesiones": len(g),
                  "ids": ";".join(map(str, g.session_id)), "recibidos": k,
                  "intentados": n, "pdr_agregado": k / n, "ic95_inf": lo, "ic95_sup": hi,
                  "pdr_min_sesion": g.pdr.min(), "pdr_max_sesion": g.pdr.max(),
                  "p_heterogeneidad": het, "criterio": CRITERIO.get(c, float("nan"))})
pdr_celda = pd.DataFrame(filas)
print(pdr_celda.assign(
    pdr=lambda d: d.pdr_agregado.map(pct),
    ic=lambda d: [f"[{pct(a)}; {pct(b)}]" for a, b in zip(d.ic95_inf, d.ic95_sup)],
    rango=lambda d: [f"{pct(a)}-{pct(b)}" for a, b in zip(d.pdr_min_sesion, d.pdr_max_sesion)],
)[["celda", "clase", "sesiones", "ids", "recibidos", "intentados", "pdr", "ic", "rango",
   "p_heterogeneidad"]].to_string(index=False))
tabla(pdr_celda.round(4), "pdr_por_celda.csv")

# H1: chi2 entre escenarios de propagacion (URBANO movil, TERRAZA, CERRO16).
seccion("1b. Contrastes H1 (escenario) y H2 (clase)")
h = pdr_ses[pdr_ses.celda.isin(["URBANO movil", "TERRAZA", "CERRO16"])]
agg = h.groupby("celda")[["recibidos", "intentados"]].sum()
cont = np.array([agg.recibidos, agg.intentados - agg.recibidos]).T
chi2, p, gl, _ = stats.chi2_contingency(cont, correction=False)
print(f"H1 chi2 = {chi2:.1f}, gl = {gl}, p = {p:.2e}  (celdas: {', '.join(agg.index)})")
contrastes = [{"contraste": "H1 escenario (URBANO movil, TERRAZA, CERRO16)",
               "chi2": chi2, "gl": gl, "p": p, "delta_pp": float("nan")}]

for c in ["TERRAZA", "URBANO movil", "Banco (LAB_BANCO)"]:
    g = pdr_ses[pdr_ses.celda == c].groupby("clase")[["recibidos", "intentados"]].sum()
    if set(g.index) != {"A", "C"}:
        continue
    cont = np.array([g.recibidos, g.intentados - g.recibidos]).T
    chi2, p, gl, _ = stats.chi2_contingency(cont, correction=False)
    pa = g.loc["A"].recibidos / g.loc["A"].intentados
    pc = g.loc["C"].recibidos / g.loc["C"].intentados
    d = 100 * (pa - pc)
    problema = (p < 0.05) and abs(d) > 5
    print(f"H2 {c}: PDR A {pct(pa)} vs C {pct(pc)}; delta {d:+.1f} pp; chi2 {chi2:.2f}, "
          f"p {p:.3g} -> {'PROBLEMA DE METODO' if problema else 'sin problema de metodo'}")
    contrastes.append({"contraste": f"H2 clase en {c}", "chi2": chi2, "gl": gl, "p": p,
                       "delta_pp": d})
tabla(pd.DataFrame(contrastes), "contrastes_pdr.csv")

# H5: viabilidad del cerro.
c41 = pdr_ses[pdr_ses.celda == "CERRO16"].iloc[0]
snr41 = tel[tel.session_id == c41.session_id].snr_db
print(f"H5 CERRO16-A: PDR {pct(c41.pdr)} [{pct(c41.ic95_inf)}; {pct(c41.ic95_sup)}], "
      f"SNR mediano {snr41.median():.2f} dB (criterio >= 50 % y >= -15 dB)")

# --- Figura 1: PDR por sesion y agregado ------------------------------------
ORDEN_CELDAS = ["Banco (LAB_BANCO)", "Banco (ITPA)", "URBANO movil", "TERRAZA", "CERRO16"]
ETIQ = {"Banco (LAB_BANCO)": "Banco junto al\nlaboratorio\n(etiqueta URBANO)",
        "Banco (ITPA)": "Banco en el\ncampus ITPA\n(etiqueta URBANO)",
        "URBANO movil": "URBANO\nmóvil\n0–6 km",
        "TERRAZA": "TERRAZA\n2,8 km\n(SF7)",
        "CERRO16": "CERRO16\n15,2 km\n(SF10)"}
fig, ax = plt.subplots(figsize=(10, 5.2))
for i, c in enumerate(ORDEN_CELDAS):
    for j, cl in enumerate(["A", "C"]):
        g = pdr_ses[(pdr_ses.celda == c) & (pdr_ses.clase == cl)].sort_values("pdr")
        if g.empty:
            continue
        base = i + (j - 0.5) * 0.36
        xs = base + np.linspace(-0.09, 0.09, len(g)) if len(g) > 1 else [base]
        ax.errorbar(xs, 100 * g.pdr, yerr=[100 * (g.pdr - g.ic95_inf), 100 * (g.ic95_sup - g.pdr)],
                    fmt="o", ms=5, color=COLOR_CLASE[cl], ecolor=COLOR_CLASE[cl],
                    elinewidth=1, capsize=0, alpha=0.55, zorder=2)
        a = pdr_celda[(pdr_celda.celda == c) & (pdr_celda.clase == cl)].iloc[0]
        ax.errorbar([base + 0.14], [100 * a.pdr_agregado],
                    yerr=[[100 * (a.pdr_agregado - a.ic95_inf)], [100 * (a.ic95_sup - a.pdr_agregado)]],
                    fmt="D", ms=8, color=COLOR_CLASE[cl], mec=SUPERFICIE, mew=1.5,
                    elinewidth=2, capsize=0, zorder=3)
        ax.annotate(f"{100 * a.pdr_agregado:.0f} %", (base + 0.14, 100 * a.pdr_agregado),
                    xytext=(7, 0), textcoords="offset points", va="center",
                    fontsize=8.5, color=TINTA)
    if c in CRITERIO:
        ax.hlines(100 * CRITERIO[c], i - 0.45, i + 0.45, colors=TINTA_2,
                  linestyles=(0, (4, 3)), linewidth=1.2, zorder=1)
ax.text(2.47, 81.5, "criterio 80 %", fontsize=8, color=TINTA_2, ha="right")
ax.text(4.47, 51.5, "criterio 50 %", fontsize=8, color=TINTA_2, ha="right")
ax.set_xticks(range(len(ORDEN_CELDAS)))
ax.set_xticklabels([ETIQ[c] for c in ORDEN_CELDAS], fontsize=8.5)
ax.set_ylim(-3, 108)
ax.set_ylabel("PDR (%)")
ax.set_title("PDR de las sesiones válidas por escenario y clase (IC 95 % de Wilson)")
ax.plot([], [], "o", color=C_A, alpha=0.55, label="Clase A, sesión")
ax.plot([], [], "D", color=C_A, ms=7, label="Clase A, agregado")
ax.plot([], [], "o", color=C_C, alpha=0.55, label="Clase C, sesión")
ax.plot([], [], "D", color=C_C, ms=7, label="Clase C, agregado")
ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, -0.2))
ax.grid(axis="x", visible=False)
guardar(fig, "t1_pdr_escenario_clase.png")

# ---------------------------------------------------------------------------
# 2. RSSI y SNR frente a distancia; presupuesto de enlace y Fresnel
# ---------------------------------------------------------------------------
seccion("2. RSSI/SNR frente a distancia y presupuesto de enlace")

# Presupuesto de enlace documentado (bitacora del proyecto): a 15,266 km,
# FSPL 115,3 dB y potencia recibida en LoS -85,8 dBm. De ahi la constante
# PIRE + Grx = -85,8 + 115,3 = 29,5 dB, y Prx(d) = 29,5 - FSPL(d).
F_MHZ = 915.0


def fspl_db(d_km):
    return 20 * np.log10(d_km) + 20 * np.log10(F_MHZ) + 32.44


K_ENLACE = -85.8 + fspl_db(15.266)
SENS = {"SF10": -88.4 - 43.6, "SF7": -88.4 - 36.6}   # bitacora del proyecto
SNR_LIM = {7: -7.5, 9: -12.5, 10: -15.0}            # limite de demodulacion (Semtech)
print(f"Constante del presupuesto: PIRE+Grx = {K_ENLACE:.1f} dB; sensibilidad SF10 "
      f"{SENS['SF10']:.1f} dBm, SF7 {SENS['SF7']:.1f} dBm")

conpos = tel[tel.session_id.isin(validas.session_id) & tel.dist_gw_mejor_km.notna()].copy()
conpos = conpos.merge(validas[["session_id", "sitio"]], on="session_id")
conpos["d_plot"] = conpos.dist_gw_mejor_km.clip(lower=0.05)

# Resumen por sitio y SF, con margen de SNR en el p10 y "piso de ruido aparente"
# (RSSI - SNR) en los paquetes con SNR < 0, donde esa resta es informativa.
filas = []
for (s, sf), g in conpos.groupby(["sitio", "sf"]):
    neg = g[g.snr_db < 0]
    d = g.dist_gw_mejor_km.median()
    filas.append({"sitio": s, "sf": sf, "uplinks": len(g), "sesiones": g.session_id.nunique(),
                  "dist_mediana_km": d, "rssi_mediana": g.rssi_dbm.median(),
                  "rssi_p10": g.rssi_dbm.quantile(0.1), "snr_mediana": g.snr_db.median(),
                  "snr_p10": g.snr_db.quantile(0.1),
                  "margen_snr_p10_db": g.snr_db.quantile(0.1) - SNR_LIM.get(sf, float("nan")),
                  "rssi_presupuesto_los": (K_ENLACE - fspl_db(max(d, 0.05))),
                  "exceso_perdida_db": (K_ENLACE - fspl_db(max(d, 0.05))) - g.rssi_dbm.median(),
                  "ruido_aparente_dbm": (neg.rssi_dbm - neg.snr_db).median() if len(neg) >= 5 else float("nan"),
                  "n_snr_neg": len(neg)})
rf = pd.DataFrame(filas).sort_values("dist_mediana_km")
print(rf.round(1).to_string(index=False))
tabla(rf.round(2), "rf_por_sitio.csv")

# Exponente de perdidas: regresion de la mediana de RSSI por sesion contra
# 10*log10(d), solo sesiones estaticas recibidas por el gateway del laboratorio
# con d >= 0,1 km. Es un ajuste DESCRIPTIVO: mezcla geometrias muy distintas
# (banco urbano NLOS a 0,1-0,3 km y un unico punto LoS a 15,2 km).
est = conpos[(conpos.gw_mejor == "picaro-lab-ags-001") &
             conpos.sitio.isin(["LAB_BANCO", "TERRAZA", "CERRO16"])]
med = est.groupby("session_id").agg(d=("dist_gw_mejor_km", "median"),
                                    rssi=("rssi_dbm", "median")).query("d >= 0.1")
x = list(10 * np.log10(med.d))
m = pendiente(x, list(med.rssi))
n_exp = -m
b = np.mean(med.rssi) - m * np.mean(x)
res = med.rssi - (b + m * np.array(x))
print(f"Ajuste log-distancia (gateway del laboratorio, {len(med)} sesiones estaticas): "
      f"n = {n_exp:.2f}, RSSI(1 km) = {b:.1f} dBm, desv. tipica residual {res.std(ddof=2):.1f} dB")
pd.DataFrame([{"sesiones": len(med), "n_exponente": n_exp, "rssi_1km_dbm": b,
               "residuo_sd_db": res.std(ddof=2)}]).round(3).to_csv(
    os.path.join(CIFRAS, "ajuste_log_distancia.csv"), index=False)

# Fresnel (perfil SRTM agregado por km, sin los extremos): margen minimo.
imin = perfil.margen_min_m.idxmin()
print(f"Fresnel: margen minimo {perfil.margen_min_m[imin]:+d} m en el km "
      f"{perfil.km_ini[imin]}-{perfil.km_fin[imin]:g}; r1 maximo {perfil.fresnel_r1_max_m.max()} m; "
      f"mediana de los minimos por km {perfil.margen_min_m.median():.0f} m")

# --- Figura 2: RSSI y SNR frente a distancia --------------------------------
ETQ_SITIO = {"LAB_BANCO": "banco lab.", "URBANO_MOVIL": "URBANO móvil", "TERRAZA": "TERRAZA",
             "CERRO16": "CERRO16", "ITPA": "campus ITPA", "PUNTO_NE": "punto NE"}
fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 8.2), sharex=True)
for ax, col in [(a1, "rssi_dbm"), (a2, "snr_db")]:
    ax.scatter(conpos.d_plot, conpos[col], s=7, color=TENUE, alpha=0.25, lw=0,
               label="uplink recibido", zorder=1)
    ms = conpos.groupby(["session_id", "sitio", "sf"]).agg(
        d=("d_plot", "median"), v=(col, "median")).reset_index()
    ax.scatter(ms.d, ms.v, s=34, color=C_A, edgecolor=SUPERFICIE, lw=1, zorder=3,
               label="mediana de una sesión")
for s, g in rf.groupby("sitio"):
    r0 = g.iloc[0]
    a1.annotate(ETQ_SITIO.get(s, s),
                (max(r0.dist_mediana_km, 0.05), r0.rssi_mediana), xytext=(6, 8),
                textcoords="offset points", fontsize=8, color=TINTA_2)
dd = np.logspace(np.log10(0.05), np.log10(20), 100)
a1.plot(dd, K_ENLACE - fspl_db(dd), color=TINTA, lw=1.4, ls=(0, (5, 3)),
        label="presupuesto LoS (espacio libre)")
a1.plot(dd, b - 10 * n_exp * np.log10(dd), color=C_C, lw=1.6,
        label=f"ajuste log-distancia descriptivo, n = {coma(n_exp)}")
for nombre, v in SENS.items():
    a1.axhline(v, color=TINTA_2, lw=1, ls=":")
    a1.text(19.5, v + 1.2, f"sensibilidad {nombre} ({coma(v, 0)} dBm)", fontsize=8, color=TINTA_2, ha="right")
a1.set_ylabel("RSSI (dBm)")
a1.set_title("RSSI y SNR del gateway que mejor recibió cada uplink, frente a la distancia")
a1.legend(loc="upper right", ncol=1, fontsize=8)
a1.set_ylim(-136, -30)
for sf, v in SNR_LIM.items():
    a2.axhline(v, color=TINTA_2, lw=1, ls=":")
    a2.text(19.5, v + 0.5, f"límite de demodulación SF{sf} ({coma(v, 1, True)} dB)", fontsize=8, color=TINTA_2, ha="right")
a2.set_ylabel("SNR (dB)")
a2.set_xlabel("Distancia al gateway (km, escala logarítmica)")
a2.set_xscale("log")
a2.set_xticks([0.1, 0.3, 1, 3, 10, 15])
a2.set_xticklabels(["0,1", "0,3", "1", "3", "10", "15"])
fig.text(0.01, -0.01, "Distancias < 0,05 km se dibujan en 0,05 km. Sesiones válidas con distancia conocida "
         "(GPS de la sonda o, en la T3, del teléfono). El presupuesto LoS usa la constante del gateway del laboratorio "
         "(bitácora del proyecto);\n"
         "el ajuste, solo descriptivo, usa 12 sesiones estáticas de ese gateway. URBANO móvil solo aporta los uplinks recibidos.", fontsize=8, color=TINTA_2)
fig.tight_layout()
guardar(fig, "t1_rssi_snr_distancia.png")

# --- Figura 3: perfil del trayecto al cerro ---------------------------------
fig, ax = plt.subplots(figsize=(10, 4.2))
anchos = perfil.km_fin - perfil.km_ini
ax.bar(perfil.km_ini, perfil.margen_min_m, width=anchos * 0.92, align="edge", color=C_A,
       label="margen mínimo en el km (techo admisible − terreno)")
ax.plot(perfil.km_ini + anchos / 2, perfil.fresnel_r1_max_m, "o-", color=C_C, lw=1.4, ms=4,
        label="radio máximo de la 1.ª zona de Fresnel, r₁")
ax.axhline(0, color=TINTA, lw=1)
ax.annotate(f"mínimo {coma(perfil.margen_min_m[imin], 0, True)} m",
            (perfil.km_ini[imin] + anchos[imin] / 2, perfil.margen_min_m[imin]), xytext=(0, 6),
            textcoords="offset points", ha="center", fontsize=8.5, color=TINTA)
ax.set_xlim(0, perfil.km_fin.max())
ax.set_ylim(0, 300)
ax.set_xlabel("Distancia desde el gateway del laboratorio (km)")
ax.set_ylabel("Metros")
ax.set_title("Trayecto laboratorio–Cerro del Muerto: despeje de la 1.ª zona de Fresnel, por kilómetro")
ax.legend(loc="upper left", fontsize=8.5)
ax.grid(axis="x", visible=False)
fig.text(0.01, -0.03, "Perfil SRTM de 30 m. Techo admisible = línea de vista − (0,6 · r₁ + abombamiento, k = 4/3). "
         "Sin los dos extremos del trayecto, donde r₁ = 0 (ver el diccionario de datos).", fontsize=8, color=TINTA_2)
guardar(fig, "t1_perfil_fresnel_cerro.png")

# ---------------------------------------------------------------------------
# 3. Clase A frente a Clase C: entrega de downlinks, latencia del ping y RTT
# ---------------------------------------------------------------------------
seccion("3. Downlinks: entrega, latencia (Clase A) y RTT de red")

# Ventana con captura de txack: sesion 41 desde las 08:17 locales (14:17 UTC)
# segun DICCIONARIO; 62-64 completas. Se cuentan los pings encolados en esa
# ventana y cuantos tienen txack emparejado (salieron por el aire).
VENTANA_TX = {41: pd.Timestamp("2026-09-27T14:17:00Z")}
filas = []
for sid, g in dls.groupby("session_id"):
    s = ses[ses.session_id == sid].iloc[0]
    ini = VENTANA_TX.get(sid)
    gl = g if ini is None else g[g.ts_utc >= ini]
    tx = lat[lat.session_id == sid]
    capt = sid in (41, 62, 63, 64)
    filas.append({"session_id": sid, "run_label": s.run_label, "sonda": s.sonda_c,
                  "clase": s.clase, "valida": int(s.valida_para_analisis),
                  "uplinks": int(s.recibidos), "pings_encolados": len(g),
                  "txack_capturado": int(capt),
                  "pings_en_ventana_txack": len(gl) if capt else None,
                  "pings_emitidos": tx.seq.nunique() if capt else None})
ent = pd.DataFrame(filas)
ent["frac_emitidos"] = ent.pings_emitidos / ent.pings_en_ventana_txack
print(ent[ent.txack_capturado == 1].to_string(index=False))
porclase = ent.groupby("clase").agg(sesiones=("session_id", "size"),
                                    pings=("pings_encolados", "sum"),
                                    uplinks=("uplinks", "sum"))
print("Pings encolados por clase (todas las sesiones con pings, sin la 66):")
print(porclase.to_string())
cpings = ent[ent.clase == "C"]
print("Sesiones Clase C con pings:", cpings[["session_id", "run_label", "uplinks", "pings_encolados"]]
      .to_string(index=False))
tabla(ent.round(4), "entrega_downlinks.csv")

# Latencia: modelo de Clase A. Si el ping se encola en un instante al azar del
# ciclo de uplink T, espera U(0, T) al siguiente uplink y sale en RX1 (5 s):
# lat ~ U(5, T + 5); mediana T/2 + 5. Un uplink perdido anade T.
RX1 = 5.0
periodo = (tel.sort_values("ts_utc").groupby("session_id")
           .apply(lambda g: (g.ts_utc.diff().dt.total_seconds() / g.f_cnt.diff()).median(),
                  include_groups=False))
lat["enc_a_uplink_s"] = (lat.uplink_previo_utc - lat.ts_encolado_utc).dt.total_seconds()
GRUPOS = [("Sesión 41 · CERRO16-A\nT-Beam, SF10, 15,2 km\n(válida)", [41]),
          ("Sesiones 62–63 · VUELO-A\nT3, SF10, 12,3 km\n(fuera del conjunto válido)", [62, 63]),
          ("Sesión 64 · VUELO-A\nT3, SF10, 12,3 km\n(válida)", [64])]
filas = []
for nombre, ids in GRUPOS:
    g = lat[lat.session_id.isin(ids)]
    T = float(np.median([periodo[i] for i in ids]))
    v = g.lat_tx_estimada_s
    filas.append({"grupo": nombre.replace("\n", " "), "sesiones": ";".join(map(str, ids)),
                  "n": len(v), "periodo_uplink_s": T, "mediana_s": v.median(),
                  "p25_s": v.quantile(.25), "p75_s": v.quantile(.75), "min_s": v.min(),
                  "max_s": v.max(), "teoria_mediana_s": T / 2 + RX1,
                  "teoria_min_s": RX1, "teoria_max_s": T + RX1,
                  "frac_sobre_teoria_max": float((v > T + RX1 + 0.5).mean()),
                  "enc_a_uplink_mediana_s": g.enc_a_uplink_s.median(),
                  "enc_a_uplink_rango_s": f"{g.enc_a_uplink_s.min():.2f}-{g.enc_a_uplink_s.max():.2f}",
                  "criterio_H4_A": v.median() >= 0.4 * T})
lat_res = pd.DataFrame(filas)
print(lat_res.round(2).to_string(index=False))
tabla(lat_res.round(3), "latencia_clase_a.csv")

# Fase ping-uplink en 62-63: el ciclo de ping (60 s) es multiplo exacto del
# ciclo de VUELO (20 s), asi que la fase se conserva de un ping al siguiente.
g6 = lat[lat.session_id.isin([62, 63])]
print(f"62-63: el ping se encola entre {g6.enc_a_uplink_s.min():.2f} y {g6.enc_a_uplink_s.max():.2f} s "
      f"antes de un uplink (fase casi fija: 60 s = 3 x 20 s)")
g41 = lat[lat.session_id == 41]
print(f"41: encolado-a-uplink entre {g41.enc_a_uplink_s.min():.2f} y {g41.enc_a_uplink_s.max():.2f} s; "
      f"perdida de uplink en la sesion {1 - c41.pdr:.3f}")

# RTT de red (inferido): en el SenseCAP por UDP el txack llega al aceptar la
# orden, asi que dt(uplink->txack) = subida gateway->LNS + proceso + bajada
# LNS->gateway + ack. En Basics Station y Kerlink el ack es posterior a emitir.
rtt = lat.groupby("gw_tx").dt_uplink_txack_s.agg(["size", "median", "min", "max"])
print("dt uplink -> txack por gateway (s):")
print(rtt.round(3).to_string())
tabla(rtt.reset_index().round(3), "rtt_uplink_txack.csv")

# --- Figura 4: latencia del ping (Clase A) ---------------------------------
fig, ax = plt.subplots(figsize=(10, 4.8))
rng = np.random.default_rng(1)
for i, (nombre, ids) in enumerate(GRUPOS):
    r = lat_res.iloc[i]
    ax.add_patch(plt.Rectangle((i - 0.32, r.teoria_min_s), 0.64, r.teoria_max_s - r.teoria_min_s,
                               color=C_A, alpha=0.10, lw=0, zorder=0))
    ax.hlines(r.teoria_mediana_s, i - 0.32, i + 0.32, colors=C_A, lw=1, ls=(0, (4, 3)), zorder=1)
    v = lat[lat.session_id.isin(ids)].lat_tx_estimada_s
    ax.scatter(i + rng.uniform(-0.18, 0.18, len(v)), v, s=30, color=C_A, edgecolor=SUPERFICIE,
               lw=1, zorder=3)
    ax.hlines(v.median(), i - 0.3, i + 0.3, colors=TINTA, lw=2.2, zorder=4)
    ax.annotate(f"mediana {coma(v.median())} s\nn = {len(v)}", (i + 0.33, v.median()),
                xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5)
ax.set_yscale("log")
ax.set_yticks([3, 5, 10, 20, 50, 100, 200])
ax.set_yticklabels(["3", "5", "10", "20", "50", "100", "200"])
ax.set_xticks(range(len(GRUPOS)))
ax.set_xticklabels([g[0] for g in GRUPOS], fontsize=8.5)
ax.set_xlim(-0.6, len(GRUPOS) - 0.1)
ax.set_ylabel("Latencia estimada encolado → emisión (s, escala log.)")
ax.set_title("Latencia del ping de downlink en Clase A (la campaña no tiene medidas de Clase C)")
ax.add_patch(plt.Rectangle((0, 0), 0, 0, color=C_A, alpha=0.15, label="rango teórico U(5 s, T + 5 s)"))
ax.plot([], [], color=C_A, lw=1, ls=(0, (4, 3)), label="mediana teórica T/2 + 5 s")
ax.plot([], [], color=TINTA, lw=2.2, label="mediana medida")
ax.legend(loc="upper left", fontsize=8.5)
ax.grid(axis="x", visible=False)
guardar(fig, "t1_latencia_ping_clase_a.png")

# ---------------------------------------------------------------------------
# 4. Corridas VUELO: telemetria de 11 bytes, T-Beam frente a T3
# ---------------------------------------------------------------------------
seccion("4. Corridas VUELO (fPort 17, 11 bytes en tres paquetes por rafaga)")


def airtime_ms(pl, sf, bw=125e3, cr=1, preamb=8, h=0, crc=1):
    """Tiempo en el aire LoRa (Semtech AN1200.13)."""
    ts = (2 ** sf) / bw * 1000
    de = 1 if ts > 16 else 0
    num_ = 8 * pl - 4 * sf + 28 + 16 * crc - 20 * h
    nsym = 8 + max(math.ceil(num_ / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return (preamb + 4.25) * ts + nsym * ts


PHY = 11 + 13   # FRMPayload + MHDR(1) + FHDR(7) + FPort(1) + MIC(4)
at = airtime_ms(PHY, 10)
print(f"Airtime de un paquete VUELO (24 B PHY, SF10/125 kHz): {at:.1f} ms; "
      f"3 por minuto -> ciclo de trabajo {3 * at / 600:.2f} %")

v = tel[tel.f_port == 17].copy()
filas = []
for sid, g in v.groupby("session_id"):
    s = ses[ses.session_id == sid].iloc[0]
    n_raf = int(g.rafaga.max()) + 1
    por_raf = g.groupby("rafaga").tipo_paquete.nunique()
    compl = int((por_raf == 3).sum())
    pdr_f = s.recibidos / (s.fcnt_max - s.fcnt_min + 1)
    lo, hi = wilson(int(s.recibidos), int(s.fcnt_max - s.fcnt_min + 1))
    snr_gw01 = g.snr_gw01.median()
    filas.append({"session_id": sid, "run_label": s.run_label, "sonda": s.sonda_c,
                  "sitio": s.sitio, "valida": int(s.valida_para_analisis),
                  "uplinks": len(g), "pdr_fcnt": pdr_f, "ic95_inf": lo, "ic95_sup": hi,
                  "rafagas": n_raf, "rafagas_completas": compl,
                  "frac_rafagas_completas": compl / n_raf,
                  "frac_rafagas_con_posicion": (g[g.tipo_paquete == "posicion"].rafaga.nunique()) / n_raf,
                  "gw_mejor": g.gw_mejor.mode().iat[0], "dist_mediana_km": g.dist_gw_mejor_km.median(),
                  "rssi_mediana": g.rssi_dbm.median(), "snr_mediana": g.snr_db.median(),
                  "snr_gw01_mediana": snr_gw01, "frac_2_gateways": (g.n_gateways >= 2).mean(),
                  "bateria_v_ini": g.sort_values("ts_utc").bateria_v.dropna().head(3).median(),
                  "bateria_v_fin": g.sort_values("ts_utc").bateria_v.dropna().tail(3).median(),
                  "temp_c_mediana": g.temperatura_c.median()})
vu = pd.DataFrame(filas)
print(vu.round(3).to_string(index=False))
tabla(vu.round(4), "vuelo_por_sesion.csv")

# Comparacion en el mismo sitio (TERRAZA, 2,8 km del laboratorio): T-Beam en
# las corridas TERRAZA (SF7, 11 B no; payload del escenario) frente a T3 VUELO (SF10).
ter = rf[rf.sitio == "TERRAZA"]
print("TERRAZA por SF (T-Beam SF7 / T3 SF10):")
print(ter[["sf", "uplinks", "sesiones", "rssi_mediana", "snr_mediana", "snr_p10", "margen_snr_p10_db",
           "ruido_aparente_dbm"]].round(1).to_string(index=False))
t_ter = pdr_ses[pdr_ses.sitio == "TERRAZA"][["session_id", "sonda", "escenario", "clase", "recibidos",
                                             "intentados", "pdr", "ic95_inf", "ic95_sup", "metodo"]]
print(t_ter.round(3).to_string(index=False))
k1 = t_ter[t_ter.sonda == "T-Beam"][["recibidos", "intentados"]].sum()
k2 = t_ter[t_ter.sonda == "T3/LoRa32"][["recibidos", "intentados"]].sum()
cont = np.array([[k1.recibidos, k1.intentados - k1.recibidos], [k2.recibidos, k2.intentados - k2.recibidos]])
chi2, p, _, _ = stats.chi2_contingency(cont, correction=False)
print(f"TERRAZA T-Beam SF7 {pct(k1.recibidos / k1.intentados)} vs T3 SF10 {pct(k2.recibidos / k2.intentados)}: "
      f"chi2 {chi2:.1f}, p {p:.2g} (diferencia confundida con SF, placa y fecha)")
tabla(t_ter.round(4), "terraza_tbeam_vs_t3.csv")

# PUNTO_NE: sesiones 63 y 64, mismo sitio y gateway, minutos de diferencia.
filas = []
for sid in (62, 63, 64):
    g = tel[tel.session_id == sid]
    neg = g[g.snr_gw01 < 0]
    filas.append({"session_id": sid, "valida": int(ses.loc[ses.session_id == sid, "valida_para_analisis"].iat[0]),
                  "uplinks": len(g), "rssi_gw01_mediana": g.rssi_gw01.median(),
                  "snr_gw01_mediana": g.snr_gw01.median(),
                  "ruido_aparente_gw01_dbm": (neg.rssi_gw01 - neg.snr_gw01).median() if len(neg) >= 5 else float("nan"),
                  "frac_recibido_gw00": g.rssi_gw00.notna().mean(),
                  "snr_mejor_mediana": g.snr_db.median(), "snr_mejor_p10": g.snr_db.quantile(0.1),
                  "margen_sf10_mediana_db": g.snr_db.median() - SNR_LIM[10],
                  "margen_sf10_p10_db": g.snr_db.quantile(0.1) - SNR_LIM[10]})
pne = pd.DataFrame(filas)
print("PUNTO_NE, gateway ITPA-IOT-GW01-kibts:")
print(pne.round(2).to_string(index=False))
tabla(pne.round(3), "punto_ne_62_64.csv")

# --- Figura 5: VUELO por sesion ----------------------------------------------
vv = vu[vu.valida == 1].sort_values("dist_mediana_km", na_position="first")
fig, ax = plt.subplots(figsize=(10, 4.6))
x = np.arange(len(vv))
w = 0.36
b1 = ax.bar(x - w / 2 - 0.01, 100 * vv.pdr_fcnt, w, color=C_A, label="PDR por fCnt (IC 95 % Wilson)")
ax.errorbar(x - w / 2 - 0.01, 100 * vv.pdr_fcnt,
            yerr=[np.clip(100 * (vv.pdr_fcnt - vv.ic95_inf), 0, None),
                  np.clip(100 * (vv.ic95_sup - vv.pdr_fcnt), 0, None)],
            fmt="none", ecolor=TINTA_2, elinewidth=1)
b2 = ax.bar(x + w / 2 + 0.01, 100 * vv.frac_rafagas_completas, w, color=C_3,
            label="ráfagas completas (P1+P2+P3)")
for bars, vals in [(b1, vv.pdr_fcnt), (b2, vv.frac_rafagas_completas)]:
    for bb, val in zip(bars, vals):
        ax.text(bb.get_x() + bb.get_width() / 2, 2, f"{100 * val:.0f} %", ha="center",
                va="bottom", fontsize=8.5, color="#ffffff", fontweight="bold")
etq = []
for r in vv.itertuples():
    d = "" if pd.isna(r.dist_mediana_km) else f", {coma(r.dist_mediana_km)} km"
    etq.append(f"Sesión {r.session_id}\n{ETQ_SITIO.get(r.sitio, r.sitio)}{d}\n{r.gw_mejor.replace('ITPA-IOT-', '')}")
ax.set_xticks(x)
ax.set_xticklabels(etq, fontsize=8)
ax.set_ylim(0, 108)
ax.set_ylabel("Porcentaje (%)")
ax.set_title("Corridas VUELO válidas (radiosonda PiCARO T3/LoRa32, SF10, 11 B cada 20 s)")
ax.legend(loc="upper right", bbox_to_anchor=(1, 1.02), ncol=2, fontsize=8.5)
ax.grid(axis="x", visible=False)
guardar(fig, "t1_vuelo_t3_sesiones.png")

print("\nListo. Cifras en", CIFRAS)
