# Microservicio de campo — PiCARO

Servicio FastAPI que **opera y monitoriza** una campaña de pruebas de terreno
LoRaWAN. La app Flutter habla con él por REST + WebSocket; él lee los uplinks de
ChirpStack por MQTT y llama a la API REST de ChirpStack para cambiar el perfil
del device y encolar downlinks (ping fPort 98; Marco fPort 30 de la radiosonda).

Fuente de verdad: [`../docs/CONTRATO-CAMPO.md`](../docs/CONTRATO-CAMPO.md). Este
README describe cómo correrlo; el contrato manda sobre el comportamiento.

> Regla dura heredada: **la configuración global de ChirpStack no se toca**. El
> servicio solo *lee* del MQTT y *llama* a operaciones sobre NUESTRO device
> (cambiar su device profile, encolar su ping). Nada más.

## Estructura

```
picaro_campo/
  main.py        FastAPI: rutas REST + WebSocket (create_app factory)
  auth.py        dependencia de token Bearer (+ token WS por query param)
  ingest.py      suscripción MQTT (reusa parse_chirpstack_up del dashboard)
  sessions.py    máquina de estados de sesión, métricas en vivo, hub WebSocket
  store.py       SQLite (esquema del dashboard + session_id + tabla sessions)
  chirpstack.py  cliente REST (cambio de perfil, encolar ping y Marco)
  config.py      lee variables de entorno + constantes del experimento
  models.py      modelos Pydantic de request
tests/           pytest con TestClient, sin red real (MQTT y ChirpStack mockeados)
Dockerfile · requirements.txt · .env.example
```

## Endpoints REST (§6 del contrato)

Todas las rutas salvo `/health` exigen `Authorization: Bearer <CAMPO_TOKEN>` (si
falta o es inválido → **401**). Errores como JSON `{"detail": "..."}` con código
400/401/404/409/503.

| Método | Ruta | Qué hace |
|---|---|---|
| GET  | `/health` | `{status, mqtt_connected, version}` (sin auth) |
| POST | `/session/start` | `{scenario, class, sonda?}` (ver «Corridas» y «Sondas») → `201 {session}`; **400** si la combinación no existe (p. ej. `VUELO`/`C`) o la sonda no la admite; **409** si ya hay una activa; cambia el device profile, **verifica la clase efectiva** (gate de clase, §15.1: **409** «clase desajustada» si el device sigue congelado en otra clase) y calcula `expected_fport` |
| POST | `/session/{id}/abort` | `200 {session}` (conserva los datos) |
| POST | `/session/{id}/finish` | `200 {session}` |
| GET  | `/session/current` | `{session, metrics}` o `{session: null}` |
| GET  | `/sessions` | `[{session, summary}, …]` (más reciente primero); `summary.vuelo` y `summary.radiosonda` como en `metrics` |
| GET  | `/sessions/{id}` | `{session, summary, metrics}` |
| GET  | `/sessions/{id}/uplinks` | `[{uplink}, …]` |
| GET  | `/sessions/{id}/downlinks` | `[{seq, fport, ts, iso, origin}, …]` — pings **enviados** de la sesión (manuales y automáticos, §15.2) |
| GET  | `/sessions/{id}/csv` | `text/csv` (`Content-Disposition` con `run_label`) |
| GET  | `/sessions/{id}/downlinks/csv` | `text/csv` `<run_label>_dl.csv` — el lado «enviado» del cruce de latencia |
| POST | `/ping` | encola downlink fPort 98 → `200 {seq}` (persistido si hay sesión capturando) |
| POST | `/marco` | Marco Polo de la radiosonda: encola fPort 30 `[seq]` → `200 {seq, enqueued_at}`; **409** sin sesión activa de la sonda `radiosonda` (ver «RADIOSONDA») |
| GET  | `/sessions/{id}/marcopolo` | `[{seq, enqueued_at, received_at, rtt_ms, rssi_dbm, snr_db, gw_rssi, gw_snr}, …]` |
| POST | `/profile` | `{profile, sonda?}` → `200 {profile}` |
| POST | `/session/{id}/posicion` | `{lat, lon, alt_m?, precision_m?, ts?}` → `201 {posicion}`; **400** fuera de rango, **404**, **409** si no captura (GPS del teléfono, ver «Sondas») |
| GET  | `/sessions/{id}/posiciones` | `[{ts, iso, lat, lon, alt_m, precision_m}, …]`; en CSV: `/sessions/{id}/posiciones/csv` (`<run_label>_pos.csv`) |

## Corridas

| Escenario | Clase | fPort | Perfil | `target_uplinks` |
|---|---|---|---|---|
| URBANO  | A / C | 11 / 12 | terreno-a / terreno-c | `TARGET_UPLINKS` (300) |
| TERRAZA | A / C | 13 / 14 | terreno-a / terreno-c | `TARGET_UPLINKS` (300) |
| CERRO16 | A / C | 15 / 16 | terreno-a / terreno-c | `TARGET_UPLINKS` (300) |
| VUELO   | **solo A** | 17 | terreno-a | **165** fijo (55 ráfagas × 3) |
| RADIOSONDA | **solo C** | 20–23 + 30 | radiosonda-c | **16** de telemetría, **sin autofinalizar** |

VUELO ([`../docs/VUELO-ESPEC.md`](../docs/VUELO-ESPEC.md)) manda cada lectura
repartida en 3 paquetes (P1 posición, P2 ambiente, P3 navegación). Sus campos
extra (`tipo_paquete`, `rafaga`, `hdop`, …) viajan en `raw_json`; no hay columnas
nuevas. P2/P3 se guardan con `latitude`/`longitude` **null** (nunca 0) y la
distancia al gateway solo usa P1 con coordenadas. En VUELO, `battery_*`,
`gps_fix` y `satellites` de `metrics` son los del **último paquete que los trajo**.

En sesiones VUELO, `metrics` (y `summary`) llevan además la clave `vuelo`
(`null` en las demás corridas):

```json
"vuelo": {
  "por_tipo": {"posicion": 3, "ambiente": 1, "navegacion": 3},
  "rafagas_completas": 1,   // llegaron P1+P2+P3
  "rafagas_parciales": 2,   // llegaron 1 o 2 (la ráfaga en curso cuenta aquí)
  "rafagas_perdidas": 1,    // ninguno, contando 0..rafaga_max
  "rafaga_max": 3,          // null si aún no llegó ninguna
  "rafagas_objetivo": 55
}
```

Cada uplink (`/sessions/{id}/uplinks` y WS `uplink`) lleva la clave `vuelo`: en
fPort 17, `{tipo_paquete, rafaga, humidity_pct, speed_kmh, heading_deg, hdop,
vspeed_ms, uptime_s, mag_ok, bme_ok}` (los que falten → `null`); en los demás
fPorts, `null`. `raw_json` no se expone nunca.

### RADIOSONDA (1.5.0)

Contrato en `Radiosonda_pi-caro/docs/RADIOSONDA-ESPEC.md`. Solo la abre la sonda
`radiosonda` (y esa sonda solo abre esta corrida): `{"scenario": "RADIOSONDA",
"class": "C", "sonda": "radiosonda"}`. Pone el perfil `radiosonda-c` y aplica el
gate de clase igual que en terreno (409 si la clase efectiva no es C).

- **Varios fPorts.** 20 posición, 21 atmósfera, 22 ambiente, 23 interno y 30 Polo
  son todos de la corrida y se guardan; ninguno es desajuste. `expected_fport` es
  el 20 (el principal).
- **Objetivo 16 sin autofinalizar.** Solo cuentan 20–23; `progress_pct` se mide
  con la telemetría recibida y se topa en 100. La sonda sigue transmitiendo
  después de aterrizar: la sesión la cierra el operador.
- **Sin ping automático.** Lo sustituye el Marco Polo.
- **Marco Polo.** `POST /marco` encola el fPort 30 `[seq]` (1..255 cíclico, se
  reinicia en cada sesión), lo deja pendiente en la tabla `marcopolo` y difunde
  `marco_ack`. Cuando llega el Polo (uplink fPort 30) con ese `seq`, el servicio
  calcula `rtt_ms` = llegada del Polo − encolado del Marco (reloj del servicio) y
  difunde `polo`. Un Polo sin Marco pendiente sale con `rtt_ms: null` y se guarda
  con `enqueued_at: null`. El Marco también queda en `/sessions/{id}/downlinks`
  (`fport: 30`, `origin: "marco"`).

Cada uplink lleva la clave `radiosonda` (`null` fuera de 20–23/30): el
`tipo_paquete` y los campos de su tabla, con los nombres del codec:

| `tipo_paquete` | Campos |
|---|---|
| `posicion` | `gps_fix, latitude, longitude, altitude_m, satellites` |
| `atmosfera` | `ext_temperature_c, ext_pressure_hpa, ext_humidity_pct, tvoc_ppb, eco2_ppm, aqi, battery_pct` |
| `ambiente` | `aht_temperature_c, aht_humidity_pct, light_lux, dht_temperature_c, dht_humidity_pct, battery_v, uptime_s` |
| `interno` | `temperature_c, pressure_hpa, humidity_pct, ina_bus_v, ina_current_ma, lectura, gps_fix, usb_powered, charging, gps_active` |
| `polo` | `seq, rssi_dbm, snr_db` |

`metrics` (y `summary`) llevan el bloque `radiosonda` (`null` en las demás
corridas):

```json
"radiosonda": {
  "ultima": {"latitude": 19.52, "ext_temperature_c": -41.25, "...": "..."},
  "por_tipo": {"posicion": 4, "atmosfera": 4, "ambiente": 3, "interno": 4, "polo": 2},
  "telemetria_recibidos": 15, "telemetria_objetivo": 16,
  "lecturas_completas": 3, "lecturas_parciales": 1, "lectura_ultima": 3,
  "marcos_enviados": 3, "polos_recibidos": 2, "polos_sin_marco": 0,
  "rtt_ms_mean": 2210.5, "rtt_ms_min": 1480, "rtt_ms_max": 2941
}
```

`ultima` trae todas las magnitudes de 20–23, cada una con el último valor **no
nulo** que llegó. Las lecturas se agrupan por fCnt consecutivo (20 = n … 23 =
n+3); un Polo colado a mitad de ráfaga no parte la lectura. Las columnas clásicas
(`latitude`, `battery_*`, `temperature_c`…) se llenan desde el `object` del codec
como siempre, y `battery_*`, `gps_fix` y `satellites` de `metrics` son los del
último paquete que los trajo, como en VUELO. El CSV de uplinks no cambia: los
campos sin columna propia van en `raw_json`, igual que en VUELO.

La clave del campo de clase en el JSON es **`class`** (valores `"A"`/`"C"`), tal
cual la lee la app. `metrics` respeta los nombres del §6 (`pdr_est`,
`progress_pct`, `rssi_mean`, `battery_pct` que **puede ser null**, etc.).

## Sondas (D-65)

El servicio atiende tres sondas, **una sesión a la vez**. Cada sesión es de una, y
el perfil, el gate de clase, los pings y la captura van a su DevEUI:

| `sonda` | Placa | DevEUI (entorno) | Corridas |
|---|---|---|---|
| `tbeam` (por defecto) | T-Beam Supreme | `DEV_EUI` | todas |
| `lora32` | T3 v1.6.1 | `DEV_EUI_LORA32` | solo VUELO-A |
| `radiosonda` | T-Beam Supreme con el firmware RADIOSONDA | `DEV_EUI_RADIOSONDA` (hoy = `DEV_EUI`) | solo RADIOSONDA-C (que ninguna otra sonda abre) |

La app 2.2 manda `sonda` según el nombre BLE de la sonda conectada
(`PICARO-LORA32` → `lora32`, `PICARO-RADIOSONDA` → `radiosonda`). Si hay más de
un DevEUI distinto configurado, el MQTT se suscribe a todos los devices de la
aplicación y descarta los que no son de la sesión (la radiosonda, con el mismo
DevEUI que la `tbeam`, no cuenta como otro). Las
sesiones llevan `sonda` y `dev_eui`; la SQLite existente se migra sola al
arrancar.

**Distancia de la T3 (1.4.0).** La T3 no tiene GPS y su posición en el payload es
simulada, así que su distancia sale del **teléfono**:
- La app envía la posición del teléfono cada 30 s (`POST /session/{id}/posicion`).
- Cada uplink se empareja con la posición más cercana en el tiempo, si está a ≤ 300 s.
- Se mide contra **el gateway que recibió el uplink**: con sus coordenadas de
  ChirpStack si las tiene, o con `GW_LAT/GW_LON` si no.

Métricas añadidas: `dist_gw_km_ultima`, `posicion_telefono`, `gateway_ultimo`. El
CSV de uplinks lleva al final `tel_lat, tel_lon, tel_precision_m, gw_lat, gw_lon,
dist_gw_km`. En la T-Beam, todo esto va vacío y la distancia se calcula como antes.

## WebSocket (§7)

`wss://<host>/ws?token=<CAMPO_TOKEN>` (token por query param; si es inválido se
cierra con **code 1008**). Mensajes servidor→cliente (`type`): `hello`,
`session`, `uplink`, `metrics`, `warning` (`kind: fport_mismatch |
class_mismatch | class_unverified`), `ping_ack` (`{seq, origin}`) y, en
RADIOSONDA, `marco_ack` (`{seq, enqueued_at}`) y `polo` (`{seq, rtt_ms, rssi_dbm,
snr_db, gw_rssi, gw_snr, received_at}`; `rtt_ms` null si no había Marco
pendiente).

## Ping automático ligado a la sesión (D-61)

Mientras una sesión está capturando, una tarea asyncio encola un ping fPort 98
cada `PING_INTERVAL_S` segundos (60 por defecto; `0` lo desactiva), por el mismo
camino y con la misma secuencia que el `/ping` manual. Cada envío —manual o
automático— se persiste en la tabla `downlinks` de la SQLite y se descarga con
la sesión (`/sessions/{id}/downlinks[/csv]`). La tarea muere con la sesión
(finish/abort/auto-finish) y con el apagado del servicio. Sustituye al antiguo
`servidor/pinger.py` (obsoleto: nunca llegó a enviar nada en la campaña).

## Correr en local (desarrollo)

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env    # y rellena los secretos

# Modo factoría: uvicorn llama a create_app() en el arranque.
uvicorn picaro_campo.main:create_app --factory --host 0.0.0.0 --port 8000
```

Las variables de entorno se toman del entorno del proceso (o de un `.env` si lo
cargas tú; el contenedor lo hace por `env_file`). Ver `.env.example` (§8).

## Tests

```bash
pip install -r requirements.txt
python -m pytest
```

No tocan la red: el MQTT no se conecta (`start_mqtt=False`) y ChirpStack está
mockeado. Cubren auth, el ciclo start→uplinks→metrics→finish, el 409 de doble
sesión, el **gate de clase** (409 «clase desajustada» y el caso no verificable),
el desajuste de fPort, la generación de CSV (uplinks y `_dl` de downlinks
enviados), el **ping automático** (dispara, persiste y muere con la sesión, con
intervalo inyectado en ms), la auto-finalización al objetivo, la corrida
**VUELO** (`tests/test_vuelo.py`: start, rechazo de VUELO-C, objetivo 165,
métricas por tipo/ráfaga, P2/P3 sin posición), las sondas (`tests/test_sondas.py`),
la corrida **RADIOSONDA** (`tests/test_radiosonda.py`: sondas admitidas, gate de
clase, varios fPorts, sin autofinalizar ni ping automático, lecturas, Marco Polo
y RTT) y los 503 de dependencias caídas.

## Docker

```bash
docker build -t picaro-campo:latest .
```

El despliegue real (compose + Caddy) está en
[`../despliegue-campo/`](../despliegue-campo/).

---
© 2026 Omar Velázquez — Licencia MIT · ovelazquezj@gmail.com
