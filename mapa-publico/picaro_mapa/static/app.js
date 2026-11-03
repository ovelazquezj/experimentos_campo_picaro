// picaro-mapa — cliente. Todo el texto que viene de los codecs se inserta con
// textContent (nunca innerHTML): lo escribe cada equipo y no es de confianza.
"use strict";

const estado = { nodos: new Map(), gateways: [], itpa: null, dias: 7, sel: null, hist: null };
const capas = { nodos: new Map(), gws: L.layerGroup(), lineas: L.layerGroup() };
const $ = (s) => document.querySelector(s);

// ------------------------------------------------------------------ utilidades
function el(tag, attrs, ...hijos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const h of hijos.flat()) if (h != null && h !== false) e.append(h instanceof Node ? h : String(h));
  return e;
}
const fmt = (v, d = 1) => (v == null ? "—" : Number(v).toFixed(d));
function hace(ms) {
  if (!ms) return "sin datos";
  const s = Math.max(0, (Date.now() - ms) / 1000);
  if (s < 60) return `hace ${Math.round(s)} s`;
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
  return `hace ${Math.round(s / 86400)} d`;
}
const hora = (ms) => new Date(ms).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "medium" });
function claseMargen(m) {
  if (m == null) return "nada";
  return m >= 10 ? "bueno" : m >= 5 ? "regular" : "malo";
}
const COLOR = () => {
  const cs = getComputedStyle(document.documentElement);
  return (c) => cs.getPropertyValue(`--${c}`).trim();
};
// Situacion por tiempo sin uplink: activo < 1 h <= inactivo (gris) < 24 h <= oculto
// (fuera del mapa, en la seccion de inactivos de la lista). Sin uplink: "sindatos".
// Un activo conserva el color de su ultimo margen; pasados 5 min se atenua.
const ATENUADO_MS = 5 * 60e3;
const INACTIVO_MS = 3600e3;
const OCULTO_MS = 24 * 3600e3;
function situacion(n) {
  if (!n.ultimo) return "sindatos";
  const e = Date.now() - n.ultimo.ts;
  return e < INACTIVO_MS ? "activo" : e < OCULTO_MS ? "inactivo" : "oculto";
}
const viejo = (n) => situacion(n) !== "activo";
const atenuado = (n) => situacion(n) === "activo" && Date.now() - n.ultimo.ts >= ATENUADO_MS;
const enMapa = (n) => situacion(n) !== "oculto";

function aplanar(obj, pref = "", out = []) {
  for (const [k, v] of Object.entries(obj || {})) {
    const clave = pref + k;
    if (v && typeof v === "object" && !Array.isArray(v)) aplanar(v, clave + ".", out);
    else out.push([clave, Array.isArray(v) ? JSON.stringify(v) : v === null ? "null" : String(v)]);
  }
  return out;
}

// ------------------------------------------------------------------ mapa
const mapa = L.map("mapa", { zoomControl: true, worldCopyJump: true });
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(mapa);
// Gateways por debajo de los nodos (overlayPane = 400): un nodo en el ITPA no queda tapado.
mapa.createPane("gws").style.zIndex = 350;
capas.gws.addTo(mapa);
capas.lineas.addTo(mapa);

// Los nodos sin geolocalizacion comparten el punto del ITPA (donde tambien hay
// gateways): se reparten en un anillo alrededor para que se puedan pulsar.
function posicionMapa(n, idxItpa, totalItpa) {
  if (n.pos.origen !== "itpa") return [n.pos.lat, n.pos.lon];
  const ang = Math.PI / 4 + (2 * Math.PI * idxItpa) / Math.max(1, totalItpa);
  const r = 0.0009;
  return [n.pos.lat + r * Math.sin(ang), n.pos.lon + (r * Math.cos(ang)) / Math.cos((n.pos.lat * Math.PI) / 180)];
}

function pintarNodos(encuadrar) {
  const col = COLOR();
  const visibles = [...estado.nodos.values()].filter(enMapa);
  const itpa = visibles.filter((n) => n.pos.origen === "itpa");
  const vistos = new Set();
  for (const n of visibles) {
    vistos.add(n.id);
    const c = situacion(n) === "activo" ? claseMargen(n.ultimo.margen) : "nada";
    const estilo = {
      radius: estado.sel === n.id ? 11 : 8,
      color: n.pos.origen === "itpa" ? col("tenue") : "#ffffff",
      weight: estado.sel === n.id ? 3 : 2,
      dashArray: n.pos.origen === "itpa" ? "3 3" : null,
      fillColor: col(c),
      fillOpacity: viejo(n) ? 0.55 : atenuado(n) ? 0.6 : 0.95,
    };
    const ll = posicionMapa(n, itpa.indexOf(n), itpa.length);
    let m = capas.nodos.get(n.id);
    if (!m) {
      m = L.circleMarker(ll, estilo).addTo(mapa).on("click", () => seleccionar(n.id));
      capas.nodos.set(n.id, m);
    } else {
      m.setLatLng(ll).setStyle(estilo);
    }
    m.unbindTooltip().bindTooltip(`${n.proyecto} · ${n.nombre}`.replace(/[<>&]/g, ""), { direction: "top", offset: [0, -8] });
  }
  for (const [id, m] of capas.nodos) if (!vistos.has(id)) { m.remove(); capas.nodos.delete(id); }

  if (encuadrar) {
    const pts = [...capas.nodos.values()].map((m) => m.getLatLng()).concat(estado.gateways.map((g) => [g.lat, g.lon]));
    if (pts.length) mapa.fitBounds(L.latLngBounds(pts).pad(0.3), { maxZoom: 15 });
    else if (estado.itpa) mapa.setView([estado.itpa.lat, estado.itpa.lon], 14);
  }
}

function pintarGateways() {
  capas.gws.clearLayers();
  for (const g of estado.gateways) {
    L.marker([g.lat, g.lon], {
      pane: "gws",
      icon: L.divIcon({ className: "", html: '<span class="gw-icono"></span>', iconSize: [18, 18], iconAnchor: [9, 9] }),
      zIndexOffset: -100,
    }).bindTooltip(`Gateway · ${g.nombre}`.replace(/[<>&]/g, ""), { direction: "top" }).addTo(capas.gws);
  }
}

function pintarLineas() {
  capas.lineas.clearLayers();
  const n = estado.sel && estado.nodos.get(estado.sel);
  if (!n || !n.ultimo || !capas.nodos.has(n.id)) return;
  const desde = capas.nodos.get(n.id).getLatLng();
  const col = COLOR();
  for (const r of n.ultimo.rx) {
    const g = estado.gateways.find((x) => x.id === r.gw);
    if (!g) continue;
    L.polyline([desde, [g.lat, g.lon]], { color: col(claseMargen(r.margen)), weight: 3, opacity: 0.8, dashArray: "6 6" })
      .bindTooltip(`${g.nombre}: ${r.rssi} dBm · SNR ${fmt(r.snr)} dB`.replace(/[<>&]/g, ""), { sticky: true })
      .addTo(capas.lineas);
  }
}

// ------------------------------------------------------------------ lista
function pintarLista() {
  const filtro = $("#filtro").value.trim().toLowerCase();
  const grupos = new Map();
  const ocultos = [];
  for (const n of estado.nodos.values()) {
    if (filtro && !`${n.proyecto} ${n.nombre}`.toLowerCase().includes(filtro)) continue;
    if (!enMapa(n)) { ocultos.push(n); continue; }
    if (!grupos.has(n.proyecto)) grupos.set(n.proyecto, []);
    grupos.get(n.proyecto).push(n);
  }
  const cont = $("#grupos");
  cont.replaceChildren();
  if (!estado.nodos.size) {
    cont.append(el("p", { class: "vacio" }, "Todavía no hay dispositivos publicados."));
    return;
  }
  const fila = (n) => {
    const sit = situacion(n);
    const c = sit === "activo" ? claseMargen(n.ultimo.margen) : "nada";
    const pill = sit === "activo" ? (n.ultimo.margen != null ? `${fmt(n.ultimo.margen)} dB` : "—")
      : sit === "sindatos" ? "sin datos" : "inactivo";
    return el("button", {
      class: "nodo-fila", "aria-current": estado.sel === n.id ? "true" : "false",
      onclick: () => { seleccionar(n.id); $("#lista").classList.remove("abierta"); },
    },
      el("i", { class: `pto ${n.pos.origen === "itpa" && (sit === "activo" || sit === "sindatos") ? "itpa" : c}${viejo(n) ? " viejo" : atenuado(n) ? " atenuado" : ""}` }),
      el("div", { style: "min-width:0" }, el("div", { class: "nom" }, n.nombre),
        el("div", { class: "sub" }, (sit === "oculto" ? `${n.proyecto} · ` : "") + hace(n.ultimo && n.ultimo.ts))),
      el("span", { class: `pill ${c}` }, pill),
    );
  };
  const reciente = (a, b) => (b.ultimo ? b.ultimo.ts : 0) - (a.ultimo ? a.ultimo.ts : 0);
  for (const [proy, ns] of [...grupos].sort((a, b) => a[0].localeCompare(b[0], "es"))) {
    ns.sort(reciente);
    cont.append(el("section", { class: "grupo" },
      el("h2", {}, el("span", {}, proy), el("span", {}, String(ns.length))),
      ns.map(fila)));
  }
  if (ocultos.length) {
    ocultos.sort(reciente);
    cont.append(el("section", { class: "grupo inactivos" },
      el("h2", {}, el("span", {}, "Inactivos más de 24 h · fuera del mapa"), el("span", {}, String(ocultos.length))),
      ocultos.map(fila)));
  }
}

function pintarResumen() {
  const ns = [...estado.nodos.values()];
  const activos = ns.filter((n) => situacion(n) === "activo").length;
  const proys = new Set(ns.map((n) => n.proyecto)).size;
  $("#resumen").replaceChildren(
    el("span", {}, el("b", {}, String(proys)), "proyectos"),
    el("span", {}, el("b", {}, String(ns.length)), "nodos"),
    el("span", {}, el("b", {}, String(activos)), "activos"),
    el("span", {}, el("b", {}, String(estado.gateways.length)), "gateways"),
  );
}

// ------------------------------------------------------------------ detalle
let graficas = [];
function seleccionar(id) {
  estado.sel = id;
  history.replaceState(null, "", `#nodo=${encodeURIComponent(id)}`);
  estado.hist = null;
  const n = estado.nodos.get(id);
  pintarNodos(false);
  pintarLista();
  pintarLineas();
  pintarDetalle();
  if (n) {
    // En movil el detalle ocupa la parte baja: el nodo se centra en la franja visible de arriba.
    const m = capas.nodos.get(id);
    const ll = m && m.getLatLng();
    if (!ll) { /* oculto del mapa: solo detalle */ }
    else if (window.innerWidth <= 760) {
      const p = mapa.latLngToContainerPoint(ll).add([0, mapa.getSize().y * 0.33]);
      mapa.panTo(mapa.containerPointToLatLng(p));
    } else mapa.panTo(ll);
  }
  cargarHistorial(id);
}
function cerrar() {
  estado.sel = null;
  history.replaceState(null, "", location.pathname);
  $("#detalle").hidden = true;
  pintarNodos(false);
  pintarLista();
  pintarLineas();
}

function pintarDetalle() {
  const caja = $("#detalle");
  const n = estado.sel && estado.nodos.get(estado.sel);
  if (!n) { caja.hidden = true; return; }
  caja.hidden = false;
  graficas.forEach((g) => g.destroy());
  graficas = [];
  const u = n.ultimo;

  const ubic = n.pos.origen === "itpa"
    ? el("p", { class: "aviso itpa" }, "Sus datos no traen geolocalización: se muestra en el ITPA.")
    : el("p", { class: "aviso" }, `Posición reportada en el payload (${hace(n.pos.ts)}): ${fmt(n.pos.lat, 5)}, ${fmt(n.pos.lon, 5)}`
        + (n.pos.alt != null ? ` · ${fmt(n.pos.alt, 0)} m` : ""));

  const sit = situacion(n);
  const secs = [
    el("header", {},
      el("div", {}, el("h2", {}, n.nombre), el("div", { class: "proy" }, `${n.proyecto} · ${n.perfil}`)),
      el("button", { class: "cerrar", "aria-label": "Cerrar", onclick: cerrar }, "×")),
    sit === "inactivo" ? el("p", { class: "aviso inactivo" }, `Inactivo: sin uplinks desde hace más de 1 h (último ${hace(u.ts)}).`) : null,
    sit === "oculto" ? el("p", { class: "aviso inactivo" }, `Sin uplinks desde hace más de 24 h (último ${hace(u.ts)}): no se muestra en el mapa.`) : null,
    el("h3", {}, "Ubicación"), ubic,
  ].filter(Boolean);

  if (!u) {
    secs.push(el("h3", {}, "Último uplink"), el("p", { class: "aviso" }, "Aún no se ha recibido ningún uplink desde que se publicó."));
  } else {
    secs.push(
      el("h3", {}, `Último uplink · ${hace(u.ts)}`),
      el("dl", { class: "kv" },
        [["Hora", hora(u.ts)], ["fCnt", u.fcnt ?? "—"], ["fPort", u.fport ?? "—"],
         ["SF / BW", u.sf ? `SF${u.sf} / ${u.bw_khz} kHz` : "—"], ["Frecuencia", u.freq_mhz ? `${u.freq_mhz} MHz` : "—"], ["DR", u.dr ?? "—"]]
          .map(([k, v]) => el("div", {}, el("dt", {}, k), el("dd", {}, String(v))))),
      el("h3", {}, "Señal en los gateways"),
      tablaSenal(u.rx),
      el("h3", {}, "Datos reportados"),
      tablaDatos(n, u),
    );
  }

  secs.push(el("h3", {}, `Historial · ${estado.dias} días`), el("div", { id: "historial" }, el("p", { class: "aviso" }, "Cargando…")));
  caja.replaceChildren(...secs);
  if (estado.hist) pintarHistorial();
}

function tablaSenal(rx) {
  if (!rx.length) return el("p", { class: "aviso" }, "Sin información de recepción.");
  const col = COLOR();
  return el("table", {},
    el("thead", {}, el("tr", {}, el("th", {}, "Gateway"), el("th", { class: "num" }, "RSSI"), el("th", { class: "num" }, "SNR"), el("th", { class: "num" }, "Margen"))),
    el("tbody", {}, rx.map((r) => {
      const c = claseMargen(r.margen);
      const ancho = r.margen == null ? 0 : Math.max(4, Math.min(100, (r.margen / 25) * 100));
      return el("tr", {},
        el("td", {}, r.gw_nombre, el("div", { class: "barra-margen" }, el("i", { style: `width:${ancho}%;background:${col(c)}` }))),
        el("td", { class: "num" }, `${r.rssi ?? "—"} dBm`),
        el("td", { class: "num" }, `${fmt(r.snr)} dB`),
        el("td", { class: "num" }, el("span", { class: `pill ${c}` }, r.margen == null ? "—" : `${fmt(r.margen)} dB`)));
    })));
}

function tablaDatos(n, u) {
  if (!n.tiene_codec) return el("p", { class: "aviso" }, "Este proyecto no tiene codec en ChirpStack: solo se muestra la calidad de la señal.");
  if (!u.datos) return el("p", { class: "aviso" }, "Este uplink no trajo datos decodificados (payload vacío o comando MAC).");
  return el("table", { class: "datos" }, el("tbody", {}, aplanar(u.datos).map(([k, v]) => el("tr", {}, el("td", {}, k), el("td", {}, v)))));
}

async function cargarHistorial(id) {
  try {
    const r = await fetch(`api/nodo/${encodeURIComponent(id)}/historial`);
    if (!r.ok) throw new Error(r.status);
    const h = await r.json();
    if (estado.sel !== id) return;
    estado.hist = h;
    pintarHistorial();
  } catch {
    const c = $("#historial");
    if (c) c.replaceChildren(el("p", { class: "aviso" }, "No se pudo cargar el historial."));
  }
}

function pintarHistorial() {
  const cont = $("#historial");
  const h = estado.hist;
  if (!cont || !h) return;
  graficas.forEach((g) => g.destroy());
  graficas = [];
  const total = h.uplinks + h.perdidos;
  const pct = total ? (100 * h.perdidos) / total : 0;
  cont.replaceChildren(
    el("div", { class: "stats" },
      el("div", {}, el("b", {}, String(h.uplinks)), el("span", {}, "uplinks recibidos")),
      el("div", {}, el("b", {}, String(h.perdidos)), el("span", {}, "perdidos (huecos de fCnt)")),
      el("div", {}, el("b", {}, `${fmt(pct)} %`), el("span", {}, "pérdida"))),
  );
  if (!h.uplinks) return;

  const col = COLOR();
  const ancho = Math.max(260, cont.clientWidth);
  const s = h.serie;
  const gSenal = el("div", { class: "grafica" });
  cont.append(el("h3", {}, "RSSI y SNR del mejor gateway"), gSenal);
  graficas.push(new uPlot({
    width: ancho, height: 170,
    series: [{}, { label: "RSSI (dBm)", stroke: col("acento"), width: 1.5, scale: "rssi" },
      { label: "SNR (dB)", stroke: col("regular"), width: 1.5, scale: "snr" }],
    axes: [{ stroke: col("tenue") }, { scale: "rssi", stroke: col("tenue"), size: 44 },
      { scale: "snr", side: 1, stroke: col("tenue"), size: 36, grid: { show: false } }],
    scales: { x: { time: true } },
    cursor: { drag: { x: true, y: false } },
  }, [s.ts, s.rssi, s.snr], gSenal));

  const campos = Object.keys(s.campos).sort();
  if (campos.length) {
    const sel = el("select", { "aria-label": "Campo a graficar" }, campos.map((c) => el("option", { value: c }, c)));
    const gCampo = el("div", { class: "grafica" });
    cont.append(el("h3", {}, "Datos numéricos reportados"), sel, gCampo);
    let g = null;
    const dibujar = () => {
      if (g) { g.destroy(); graficas = graficas.filter((x) => x !== g); }
      g = new uPlot({
        width: ancho, height: 160,
        series: [{}, { label: sel.value, stroke: col("acento"), width: 1.5, spanGaps: true, points: { show: true, size: 3 } }],
        axes: [{ stroke: col("tenue") }, { stroke: col("tenue"), size: 50 }],
        scales: { x: { time: true } },
      }, [s.ts, s.campos[sel.value]], gCampo);
      graficas.push(g);
    };
    sel.addEventListener("change", dibujar);
    dibujar();
  }

  cont.append(el("h3", {}, "Últimos mensajes"), el("div", { class: "ultimos" }, el("table", {},
    el("thead", {}, el("tr", {}, el("th", {}, "Hora"), el("th", { class: "num" }, "fCnt"), el("th", { class: "num" }, "SF"),
      el("th", { class: "num" }, "RSSI"), el("th", { class: "num" }, "SNR"), el("th", {}, "Datos"))),
    el("tbody", {}, h.ultimos.map((u, i) => el("tr", { class: i === 0 && h._nuevo ? "nuevo" : null },
      el("td", {}, new Date(u.ts).toLocaleTimeString("es-MX")),
      el("td", { class: "num" }, String(u.fcnt ?? "—")),
      el("td", { class: "num" }, u.sf ? String(u.sf) : "—"),
      el("td", { class: "num" }, String(u.rssi ?? "—")),
      el("td", { class: "num" }, fmt(u.snr)),
      el("td", { class: "res", title: u.datos ? JSON.stringify(u.datos) : "" }, u.datos ? aplanar(u.datos).slice(0, 3).map(([k, v]) => `${k}=${v}`).join(" ") : "—"))))),
  ));
  h._nuevo = false;
}

// ------------------------------------------------------------------ datos
async function cargarEstado(encuadrar) {
  const r = await fetch("api/estado", { cache: "no-store" });
  const d = await r.json();
  estado.itpa = d.itpa;
  estado.dias = d.historial_dias;
  estado.gateways = d.gateways;
  estado.nodos = new Map(d.nodos.map((n) => [n.id, n]));
  if (estado.sel && !estado.nodos.has(estado.sel)) estado.sel = null;
  pintarGateways();
  pintarNodos(encuadrar);
  pintarLista();
  pintarResumen();
  pintarLineas();
  pintarDetalle();
}

let recargaHist = 0;
function alUplink(n) {
  estado.nodos.set(n.id, n);
  pintarNodos(false);
  pintarLista();
  pintarResumen();
  if (estado.sel === n.id) {
    pintarLineas();
    pintarDetalle();
    // El historial se pide de nuevo como mucho cada 10 s.
    if (Date.now() - recargaHist > 10000) {
      recargaHist = Date.now();
      cargarHistorial(n.id).then(() => { if (estado.hist) { estado.hist._nuevo = true; pintarHistorial(); } });
    }
  }
}

function conectar() {
  const vivo = $("#vivo");
  const es = new EventSource("api/eventos");
  let caido = false;
  es.onopen = () => {
    vivo.dataset.estado = "vivo";
    vivo.querySelector("b").textContent = "En vivo";
    // Tras un corte se pudo perder algun uplink: se resincroniza todo.
    if (caido) cargarEstado(false).catch(() => {});
    caido = false;
  };
  es.addEventListener("error", () => { caido = true; });
  es.onerror = () => { vivo.dataset.estado = "caido"; vivo.querySelector("b").textContent = "Reconectando…"; };
  es.addEventListener("uplink", (e) => alUplink(JSON.parse(e.data)));
  es.addEventListener("catalogo", () => cargarEstado(false));
}

$("#filtro").addEventListener("input", pintarLista);
$("#boton-lista").addEventListener("click", (e) => {
  const abierta = $("#lista").classList.toggle("abierta");
  e.currentTarget.setAttribute("aria-expanded", String(abierta));
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrar(); });
// Los "hace X min" envejecen solos.
// Y los nodos se atenuan solos (5 min), pasan a inactivo (1 h) y salen del mapa (24 h).
setInterval(() => { pintarNodos(false); pintarLista(); pintarResumen(); pintarLineas(); }, 15000);

cargarEstado(true).then(() => {
  // Enlace directo a un nodo: pi-caro.org/#nodo=<id>
  const m = location.hash.match(/^#nodo=([0-9a-f]{12})$/);
  if (m && estado.nodos.has(m[1])) seleccionar(m[1]);
}).catch(() => { $("#grupos").replaceChildren(el("p", { class: "vacio" }, "No se pudo cargar el estado.")); });
conectar();
