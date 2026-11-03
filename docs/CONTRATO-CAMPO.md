# Contrato — App de campo PiCARO y su microservicio

Este documento es la **única fuente de verdad** para construir el microservicio y
la app Flutter en paralelo. Ambos lados se implementan contra lo que dice aquí. Si
algo no encaja, se discute y se cambia AQUÍ antes de tocar código.

Versión del contrato: **1.4** (ver §12, §13, §15 y §16 — enmiendas tras la
construcción, tras la campaña de agosto-2026 y la corrida VUELO)

> **Nota de la v2 de la app (BLE) — este contrato NO cambia.** Desde la v2, la app
> controla además la sonda por **Bluetooth**, y con ello la selección de corrida ocurre
> en un solo sitio. Ese segundo camino **no pasa por el microservicio**: es un enlace
> directo teléfono↔sonda que no toca ningún endpoint, ningún mensaje del WebSocket ni
> ningún campo del modelo de datos. Todo lo que dice este documento sigue siendo cierto
> palabra por palabra. Ver §14.

---

## 1. Qué es esto

Una app móvil (Flutter, APK de instalación local) para **operar y monitorizar** la
campaña de pruebas de terreno desde el teléfono, hablando con un **microservicio**
que corre en un contenedor junto a ChirpStack en el servidor en la nube.

Principio rector: **la app no controla la radio de la sonda**. La sonda se arranca
físicamente con su botón (menú + doble pulsación). Lo que la app «arranca» es una
**sesión de captura** en el microservicio. Ver §3.

Regla dura heredada: **la configuración global de ChirpStack no se toca**. El
microservicio solo *lee* del MQTT y *llama* a la API REST de ChirpStack para
operaciones que ya hacíamos a mano (cambiar el device profile de NUESTRO device,
encolar downlinks de ping). Nada más.

---

## 2. Reparto y estructura de ficheros

```
pruebas_terreno/
  branding/                 iconos (YA GENERADOS, no regenerar)
  docs/CONTRATO-CAMPO.md    este documento
  microservicio/            [dev A]  servicio FastAPI + Docker
    picaro_campo/
      __init__.py
      main.py               FastAPI app: rutas REST + WebSocket
      auth.py               dependencia de token Bearer
      ingest.py             suscripcion MQTT (reusa parse_chirpstack_up)
      sessions.py           maquina de estados de sesion + metricas
      store.py              SQLite (extiende dashboard/storage.py con session_id)
      chirpstack.py         llamadas a la API REST (perfil, ping downlink)
      config.py             lee variables de entorno
      models.py             modelos Pydantic de request/response
    tests/
      test_api.py           pytest con TestClient (sin red real)
      test_sessions.py
    Dockerfile
    requirements.txt
    .env.example
    README.md
  app/                      [dev B]  proyecto Flutter
    pubspec.yaml
    lib/
      main.dart
      config.dart           URL base + token (pantalla de configuracion)
      api/campo_api.dart     cliente REST
      api/campo_ws.dart      cliente WebSocket
      models/*.dart
      screens/panel.dart     ① Panel
      screens/mapa.dart      ② Mapa
      screens/graficos.dart  ③ Graficos
      screens/sesiones.dart  ④ Sesiones (menu ≡)
      screens/acerca.dart    ⑤ Acerca de (menu ≡)
      screens/ayuda.dart     ⑥ Ayuda (botón ?)
      widgets/*.dart
    assets/icon/…            (se copian de branding/)
    README.md
  despliegue-campo/          [dev A]  compose + bloque Caddy
    docker-compose.campo.yml
    Caddyfile.campo.snippet
    README.md
```

Los tres directorios nuevos (`microservicio/`, `app/`, `despliegue-campo/`) no
existen aún: cada agente crea el suyo. No se pisan entre sí.

**Reutilizar, no reinventar:** el mapeo de campos de un uplink de ChirpStack ya
está resuelto en `dashboard/mqtt_ingest.py::parse_chirpstack_up`, y el esquema
SQLite en `dashboard/storage.py`. Cópialos/adáptalos; no inventes otro formato.
La lógica de cambio de perfil está en `servidor/perfil.py` (mismos IDs de device
profile). La de ping vivió en `servidor/pinger.py` (fPort 98, byte = secuencia)
y desde D-61 vive **dentro del microservicio**, ligada a la sesión: ver §15.2.

---

## 3. Máquina de estados de la sesión

```
        POST /session/start
   (sin sesion) ─────────────────► CAPTURANDO
                                    │   │   │
        POST /session/{id}/abort ◄──┘   │   └──► (auto) fcnt alcanza target
                 │                       │             │
                 ▼                       ▼             ▼
              ABORTADA              POST .../finish  FINALIZADA
```

- Solo puede haber **una** sesión en `CAPTURANDO` a la vez. `start` con otra activa
  devuelve 409.
- `start` recibe `{scenario, class}`, **cambia el device profile** del device al
  correspondiente (`terreno-a`/`terreno-c`) vía la API de ChirpStack, calcula el
  `expected_fport`, y abre la fila de sesión.
- Mientras `CAPTURANDO`, cada uplink cuyo `fPort` coincide con `expected_fport` se
  guarda ligado a la sesión. Un uplink con **otro** fPort de corrida (11–16) genera
  un aviso de **desajuste** (§6, WS `warning`), pero NO se guarda en esta sesión.
- Auto-finaliza cuando el `fCnt` del último uplink guardado alcanza `target_uplinks`
  (300). También se puede cerrar a mano con `finish`.
- `abort` cierra la sesión marcándola ABORTADA; los datos capturados se conservan.

### run_label

Etiqueta legible de la sesión, con el mismo criterio que el firmware:
`AAAAMMDD-ESCENARIO-CLASE[-INTENTO]`, p. ej. `20260814-CERRO16-C`. La fecha es UTC
del servidor. Si ya existe una sesión con el mismo día/escenario/clase, se añade
`-2`, `-3`… (mismo criterio de «intentos distintos» que `runlog_asignar_run_id`).

---

## 4. Modelo de datos (SQLite)

Tabla `telemetry`: **exactamente** las columnas de `dashboard/storage.py` (`ts, iso,
dev_eui, f_cnt, f_port, rssi, snr, gateway_id, freq, dr, gps_active, gps_fix,
latitude, longitude, altitude_m, satellites, battery_v, battery_pct, charging,
usb_powered, temperature_c, pressure_hpa, raw_json`) **más** una columna
`session_id INTEGER` (FK a `sessions.id`).

Tabla `sessions`:

| columna | tipo | nota |
|---|---|---|
| id | INTEGER PK | |
| run_label | TEXT | `20260814-CERRO16-C` |
| scenario | TEXT | `URBANO` \| `TERRAZA` \| `CERRO16` \| `VUELO` (§16) |
| class | TEXT | `A` \| `C` |
| expected_fport | INTEGER | 11..17 |
| profile | TEXT | `terreno-a` \| `terreno-c` |
| state | TEXT | `capturing` \| `finished` \| `aborted` |
| target_uplinks | INTEGER | 300; **por corrida** desde v1.4 (VUELO: 165, §16) |
| started_at | REAL | epoch UTC |
| ended_at | REAL | epoch UTC, null si activa |
| notes | TEXT | opcional |

`battery_pct` puede ser **null** (el decoder ya traduce 0xFF→null; ver A-08). No lo
trates como 0.

---

## 5. fPorts y las 6 corridas

| escenario | clase | fPort | perfil | DR/SF | payload |
|---|---|---|---|---|---|
| URBANO  | A | 11 | terreno-a | DR1/SF9  | 14 B |
| URBANO  | C | 12 | terreno-c | DR1/SF9  | 14 B |
| TERRAZA | A | 13 | terreno-a | DR3/SF7  | 14 B |
| TERRAZA | C | 14 | terreno-c | DR3/SF7  | 14 B |
| CERRO16 | A | 15 | terreno-a | DR0/SF10 | 11 B |
| CERRO16 | C | 16 | terreno-c | DR0/SF10 | 11 B |
| VUELO   | A | 17 | terreno-a | DR0/SF10 | 11 B (P1/P2/P3, §16) |

VUELO **no tiene Clase C**: `VUELO`/`C` se rechaza como cualquier combinación
desconocida (`400`).

Downlinks: **fPort 98** = ping de latencia (byte = nº de secuencia). fPort 99 =
corte (no se usa desde la app).

---

## 6. API REST

Base: `https://campo.pi-caro.org`. Todo JSON. Todas las rutas salvo `/health`
exigen cabecera `Authorization: Bearer <token>`; sin ella → **401**.

| Método | Ruta | Cuerpo / respuesta |
|---|---|---|
| GET | `/health` | → `{status:"ok", mqtt_connected:bool, version:str}` (sin auth) |
| POST | `/session/start` | `{scenario, class}` → `201 {session}`; 409 si ya hay una activa **o si la clase efectiva del device no coincide (gate de clase, §15.1)** |
| POST | `/session/{id}/abort` | → `200 {session}` |
| POST | `/session/{id}/finish` | → `200 {session}` |
| GET | `/session/current` | → `{session, metrics}` o `{session:null}` |
| GET | `/sessions` | → `[{session, summary}, …]` (más reciente primero) |
| GET | `/sessions/{id}` | → `{session, summary, metrics}` |
| GET | `/sessions/{id}/uplinks` | → `[{uplink}, …]` |
| GET | `/sessions/{id}/downlinks` | → `[{seq, fport, ts, iso, origin}, …]` (pings enviados, §15.2) |
| GET | `/sessions/{id}/csv` | → `text/csv` (Content-Disposition con run_label) |
| GET | `/sessions/{id}/downlinks/csv` | → `text/csv` (`<run_label>_dl.csv`, §15.2) |
| DELETE | `/sessions/{id}` | borra la sesión y sus datos → `200 {id, deleted:true}`; `404` si no existe; **`409` si está capturando** |
| POST | `/ping` | `{}` → encola un downlink fPort 98 al device; `200 {seq}` |
| POST | `/profile` | `{profile:"ej09"\|"terreno-a"\|"terreno-c"}` → `200 {profile}` |

`metrics` (calculadas en vivo sobre la sesión):

```json
{
  "received": 54, "expected_fport": 16, "last_fcnt": 60,
  "gaps": 6, "pdr_est": 0.90, "progress_pct": 20.0,
  "rssi_mean": -119.0, "rssi_last": -118, "snr_mean": -8.0,
  "dist_gw_km_max": 16.3, "last_uplink_iso": "…",
  "battery_v": 3.71, "battery_pct": null,
  "gps_fix": true, "satellites": 9
}
```

- `pdr_est` = received / (last_fcnt − first_fcnt + 1). Es **estimado**: el
  denominador real vive en la microSD. Etiquétalo siempre como «est.».
- `progress_pct` = 100 · last_fcnt / target_uplinks.
- `dist_gw_km` se calcula por haversine contra la posición del gateway (constante de
  config `GW_LAT`, `GW_LON`).

`summary` (de una sesión cerrada): received, pdr_est, rssi_mean, snr_mean,
dist_gw_km_max, duración_s, run_label, state.

Errores: JSON `{"detail": "..."}` con el código HTTP adecuado (400/401/404/409/503).
Si el MQTT o la API de ChirpStack no responden, `503`.

---

## 7. WebSocket

`wss://campo.pi-caro.org/ws?token=<token>` (token por query param porque los
navegadores/clientes WS no siempre permiten cabeceras). Sin token válido → cierre
inmediato con code 1008.

Mensajes **servidor→cliente** (JSON, campo `type`):

| type | payload | cuándo |
|---|---|---|
| `hello` | `{version, mqtt_connected, session}` | al conectar |
| `session` | `{…session…}` | al cambiar de estado la sesión |
| `uplink` | `{…uplink aplanado…}` | por cada uplink de la sesión activa |
| `metrics` | `{…§6 metrics…}` | tras cada uplink, y cada 5 s |
| `warning` | `{kind, expected, got}` — kinds: `fport_mismatch`, `class_mismatch`, `class_unverified` (§15.1) | uplink de corrida con fPort ≠ esperado; clase efectiva ≠ clase de la corrida; clase no verificable |
| `ping_ack` | `{seq, origin:"manual"\|"auto"}` | al encolar un ping (manual o del ciclo automático, §15.2) |

Cliente→servidor: no es necesario (el control va por REST). El servidor ignora lo
que reciba salvo un `{"type":"pong"}` opcional para keepalive.

---

## 8. Configuración (variables de entorno del microservicio)

| var | ejemplo | nota |
|---|---|---|
| `CAMPO_TOKEN` | (secreto) | token Bearer que exige la API |
| `MQTT_HOST` | `mqtt.pi-caro.org` | |
| `MQTT_PORT` | `8883` | TLS |
| `MQTT_USER` / `MQTT_PASSWORD` | `picaro` / … | |
| `CHIRPSTACK_API` | `https://api.pi-caro.org` | REST |
| `CHIRPSTACK_TOKEN` | (secreto) | token de API de ChirpStack (fuera del repo) |
| `APP_ID` | `<APP_ID>` | |
| `DEV_EUI` | `0011223344550001` | el device del ej.09, reutilizado |
| `DB_PATH` | `/data/campo.db` | volumen persistente |
| `GW_LAT` / `GW_LON` | (coords del gateway) | para la distancia |
| `TARGET_UPLINKS` | `300` | objetivo de las corridas que no fijan el suyo; VUELO usa 165 fijo (§16) |
| `PING_INTERVAL_S` | `60` | cadencia del ping automático ligado a la sesión (§15.2); `0` lo desactiva |

IDs de device profile (constantes, de `servidor/perfil.py`): ej09
`<PROFILE_ID_EJ09>`, terreno-a
`<PROFILE_ID_TERRENO_A>`, terreno-c
`<PROFILE_ID_TERRENO_C>`.

---

## 9. Despliegue (Opción A — subdominio por Caddy, sin puerto nuevo)

- El contenedor se une a la red Docker externa `picaro` (la de ChirpStack) y
  escucha en un puerto **interno** `8000`, **sin publicar** al host.
- Caddy (el del stack de ChirpStack) gana un bloque:
  ```
  campo.pi-caro.org {
      reverse_proxy picaro-campo:8000
  }
  ```
  y una variable `DOMAIN_CAMPO`. Caddy emite el certificado solo (HTTP-01, puerto 80
  ya abierto) y hace de pasarela también para el WebSocket.
- `docker-compose.campo.yml` es un compose **separado** que declara la red `picaro`
  como `external: true`, monta un volumen para la SQLite y lee las variables de un
  `.env`. No modifica el compose de ChirpStack.
- No se abre ningún puerto en el firewall del servidor en la nube.

El despliegue real lo hace el coordinador por SSH con autorización del usuario. El
agente entrega los ficheros y un README con los pasos exactos.

---

## 10. La app Flutter

- **Pantalla de configuración** (primera vez / ajustes): URL base y token, guardados
  con `shared_preferences`. Sin config válida, la app lleva ahí.
- **Navegación:** `BottomNavigationBar` con las tres primeras pantallas; un menú
  `[≡]` arriba a la izquierda (`Drawer` o `PopupMenu`) con **Sesiones** y **Acerca
  de**; un botón `[?]` arriba a la derecha que abre **Ayuda**.

**① Panel** — selector de las 6 corridas (mismas opciones que el menú del device);
botón circular grande **verde (Arrancar) / rojo (Abortar) / azul (Finalizado)** según
el estado de la sesión; los datos que muestra la OLED (TX n/300 vía progress, RSSI,
SNR, GPS/sats, batería con «--» si es null, último downlink); banda de **aviso** si
llega `warning` de desajuste de fPort. Al pulsar Arrancar: `POST /session/start`
(que además cambia el perfil). Estado en vivo por WebSocket.

**② Mapa** — puntos de la sesión activa (o de la seleccionada). Marcador del gateway.
Usar `flutter_map` (OpenStreetMap) — **sin API key**. Si no hay tiles offline, que no
rompa: degradar a un lienzo con los puntos y una escala.

**③ Gráficos** — PDR estimado, RSSI/SNR/batería vs tiempo, resumen numérico. Basta
con dibujar en `CustomPainter` o `fl_chart`.

**④ Sesiones** — lista de sesiones (`GET /sessions`) con resumen; tocar una abre su
detalle; botón de **descargar CSV** (`GET /sessions/{id}/csv`, guardar con
`path_provider`/share).

**⑤ Acerca de** — «PiCARO — App de campo», autoría **© 2026 Omar Velázquez —
Licencia MIT**, correo **ovelazquezj@gmail.com**, versión de la app, y el icono.

**⑥ Ayuda** — pasos de sincronización sonda↔app, derivados de
`docs/MANUAL-DE-CAMPO.md`: 1) ajustar perfil (lo hace Arrancar), 2) en la sonda
elegir la misma corrida y doble-pulsar, 3) Arrancar en la app, 4) comprobar que no
hay aviso de desajuste.

- **Icono y splash:** `flutter_launcher_icons` y `flutter_native_splash` apuntando a
  los PNG de `branding/` (`icon_1024.png`, `adaptive_foreground_1024.png`,
  `adaptive_background_1024.png`, `splash_logo_1152.png`). Asume que existen; no
  generes placeholders.
- **Sin SDK de Flutter en el entorno del agente:** entrega **código fuente** que
  compile en cuanto haya `flutter pub get` + `flutter build apk`, con un README que
  liste dependencias y pasos. No inventes APIs de paquetes: usa versiones estables y
  conocidas.

---

## 11. Paleta (coherente con el icono)

Cielo nocturno `#0A1730`/`#183468`; oro `#FFA842`; nodo cian `#7AE4FF`; verde
Arrancar `#2FbF71`; rojo Abortar `#E4573D`; azul Finalizado `#3E82F7`. Modo oscuro
por defecto (se usa en campo, con sol; alto contraste).

---

## 12. Enmiendas v1.1 (tras la construcción y la revisión)

Resolución de los flecos detectados al revisar el contrato v1.0. El código
entregado ya los incorpora, salvo donde se indique.

1. **Ping**: su control vive en el **Panel** (botón Ping → `POST /ping`, respuesta
   por WS `ping_ack`). Implementado.
2. **`/profile` vs `/session/start`**: `start` es el dueño del perfil mientras dura
   la sesión. `/profile` queda para uso **fuera de sesión** (p. ej. devolver el
   device a `ej09` al terminar la campaña). La app no ofrece cambiar el perfil suelto
   con una captura en marcha.
3. **`progress_pct` y auto-finalización**: se derivan del **rango de fCnt**
   `(last−first+1)`, no del fCnt absoluto. `progress_pct = min(100, 100·(last−first+1)/target)`;
   auto-finaliza cuando `recibidos + gaps ≥ target`. Así espeja el «TX n/300» del
   dispositivo y no se descuadra si la captura empieza con el contador ya alto.
   **Corregido en el código** (`sessions.py`) y en los tests.
4. **`run_label` (servidor) vs `run_id` (firmware)**: son **independientes** y no se
   asume que coincidan. `cruzar.py` **no** cruza por la etiqueta sino por **fPort +
   ventana temporal**, así que una divergencia del sufijo `-2/-3` no rompe el
   análisis. El `run_label` es la vista del servidor; el `run_id` de la microSD es el
   registro de referencia.
5. **fPort fuera de 11–16 durante una sesión**: se **ignora en silencio** (no es una
   corrida del experimento). fPort en 11–16 distinto del esperado: **warning**, no se
   guarda. Implementado.
6. **`sessions.notes`**: queda **reservado**, sin endpoint de escritura en v1. La
   anotación de «por qué se abortó» vive en la hoja de campo. Candidato a A-09 si se
   quiere editable desde la app.
7. **`class` como clave del wire**: se mantiene `class` en el JSON y se **aliasa en el
   código** (Pydantic con `Field(alias="class")`; en Dart, campo `sessionClass` que
   (de)serializa `json['class']`). Fijado y verificado en ambos lados.
8. **`metrics.gaps`** = `(last_fcnt − first_fcnt + 1) − recibidos`. Definido e
   implementado.
9. **CSV de `/sessions/{id}/csv`**: es el **lado recibido** (las columnas de
   `telemetry` de la sesión). **NO** es el CSV de la microSD (el lado enviado, el
   denominador real). El PDR definitivo se sigue calculando cruzando ambos con
   `cruzar.py`. Refuerza el «PDR est.» de la app.
10. **Orden de operación para Clase C**: **Arrancar en la app primero** (fija el
    perfil), y después arrancar la sonda físicamente. Así el perfil de Clase C ya está
    puesto antes de medir latencia (regla de oro del manual). Reflejado en la Ayuda y
    en `APP-CAMPO.md`.

**Hallazgo de la construcción — marcador del gateway en el mapa.** La API no expone
`GW_LAT/LON`, así que la app las toma de su pantalla de **configuración** (opcionales;
sin ellas, no dibuja el marcador). El microservicio sí usa `GW_LAT/LON` del `.env`
para calcular `dist_gw_km_max`. Si más adelante conviene, se puede exponer la posición
del gateway en `/health` para autocompletarla.

---

## 13. Enmiendas v1.2 (replay, borrado y encuadre)

Cambios pedidos tras la primera prueba de campo real.

1. **Borrado de sesiones** — nuevo `DELETE /sessions/{id}` (§6): elimina la sesión y
   sus uplinks del servidor. Irreversible. `404` si no existe; **`409` si está
   capturando** (hay que abortarla antes). En la app, un botón *Descartar sesión* en
   el detalle, con **diálogo de confirmación** que advierte de que es irreversible.
   Sirve para no acumular sesiones de prueba en el servidor.
2. **Replay de sesiones guardadas** — la app puede **redibujar el mapa y las gráficas**
   de cualquier sesión histórica. No hace falta endpoint nuevo: lee
   `GET /sessions/{id}` (métricas) y `GET /sessions/{id}/uplinks` (puntos y series) y
   reutiliza los mismos widgets que la vista en vivo (`MapPanel`, `ChartsPanel`).
   Es una **foto fija**: no escucha el WebSocket, así que arrancar una sesión nueva no
   altera el replay abierto (se actualizan las pestañas en vivo, no el replay).
3. **Acerca de** — el texto deja de hablar de «campaña»: es una **herramienta open
   source para las pruebas de campo del proyecto radiosonda PiCARO (LoRaWAN Clase A vs
   C)**. Autoría, MIT y correo se mantienen.

---

## 14. La segunda mitad de la app (BLE) — fuera de este contrato

**Este contrato no cambia con la v2. Ni un endpoint, ni un campo, ni un mensaje.** Esta
sección existe para que quien lo lea sepa **por qué** la app hace ahora cosas que aquí no
están descritas, y no las busque en vano.

Hasta la v1, la app tenía **un solo interlocutor**: el microservicio, por internet. La v2
le añade **un segundo**, independiente del primero: la propia sonda, por **Bluetooth de
baja energía (BLE)**, en un enlace directo teléfono↔sonda.

```
                        ┌───────────────┐
   internet (TLS) ─────▶│ microservicio │──▶ ChirpStack   ← ESTE contrato
                        └───────────────┘
   APP ───────────────────────────────────────────────────
                        ┌───────────────┐
   BLE (LE Secure) ────▶│     SONDA     │                 ← fuera de este contrato
                        └───────────────┘
```

**Qué cambia para el operador:** una sola acción en la app fija **las dos mitades** a la
vez. Al Arrancar, la app hace el `POST /session/start` de siempre —que conmuta el device
profile y abre la sesión— **y además** ordena a la sonda, por BLE, que arranque ese mismo
escenario y clase. Antes eran dos actos humanos separados (§3 del manual de campo) y podían
divergir; ahora salen de la misma selección.

**Qué NO cambia, y es lo que importa aquí:**

- La sonda **sigue sin poder hablar con ChirpStack**: solo habla LoRa. El perfil A/C lo
  sigue poniendo el microservicio, exactamente con la llamada que ya existía.
- **Ningún dato de la sonda llega por BLE a este servicio.** El BLE lleva solo la orden de
  modo y el estado de la sonda; la telemetría sigue viajando por radio → ChirpStack → MQTT
  → microservicio, como siempre.
- **El aviso de desajuste de fPort se conserva tal cual.** Con la v2 no debería poder
  originarse ya en un error humano de selección, pero sigue siendo la red de seguridad que
  cazaría cualquier otra causa, y por eso no se retira.
- **El aborto del lado servidor no depende del BLE.** El botón *Abortar* de la app llama a
  `POST /session/{id}/abort` **siempre**, haya enlace Bluetooth o no. Una sesión de captura
  abierta se tiene que poder cerrar aunque el Bluetooth se haya caído; lo contrario dejaría
  sesiones colgadas en el servidor sin forma de cerrarlas desde el cerro.

**Dónde se documenta la mitad BLE:** el uso está en [`APP-CAMPO.md`](APP-CAMPO.md) §9 y el
procedimiento de campo —emparejamiento incluido— en
[`MANUAL-DE-CAMPO.md`](MANUAL-DE-CAMPO.md). Este contrato se limita a lo que va por
internet.

---

## 15. Enmiendas v1.3 (tras la campaña de agosto-2026: gate de clase y ping ligado a sesión)

Correcciones a los dos fallos diagnosticados en el análisis de la campaña (ver
BITACORA.md, entrada 2026-08-29, D-60 y D-61): la clase efectiva congelada por
ChirpStack (0/764 downlinks entregados en Clase A) y el pinger suelto que nunca
envió nada.

1. **Gate de clase en `start` (D-60).** ChirpStack v4 congela la clase operativa
   del device (`enabled_class`) en el momento del **JOIN OTAA** según el perfil
   activo entonces; el `PUT` de cambio de perfil que hace `start` **no** la
   actualiza (issue [#360](https://github.com/chirpstack/chirpstack/issues/360)
   de ChirpStack). Como la sonda hace su único join al encender (D-41),
   normalmente antes de `start`, el servidor puede quedarse operando con la
   clase de la corrida **anterior**. Por eso `start`, tras cambiar el perfil,
   **lee la clase efectiva** (`classEnabled` del `GET /api/devices/{devEui}`) y
   la compara con la clase de la corrida:
   - Si **no coincide**, la sesión **no se abre**: `409` con `detail` que empieza
     por `clase desajustada:` e incluye la instrucción de recuperación («el
     perfil ya quedó puesto: apaga y enciende la sonda para que haga un JOIN
     nuevo y vuelve a arrancar»). Por WS sale además `warning`
     `{kind:"class_mismatch", expected, got}`. Se eligió **rechazar** y no
     «abrir con aviso»: una corrida con la clase equivocada no mide lo que dice
     medir (H4 quedaría inválida otra vez), y el flujo de la app ya muestra el
     `detail` de los errores de `start`. El rechazo es además **auto-corregible**:
     el perfil bueno ya quedó puesto, así que el apagar/encender congela la
     clase correcta y el siguiente `start` entra.
   - Si el servidor **no expone** el campo (ChirpStack < 4.6), la sesión se abre
     pero se emite `warning` `{kind:"class_unverified", expected, got:null}`:
     bloquear dejaría la campaña entera sin poder arrancar.
   - La app debe mostrar el `detail` del 409 (o la banda de `warning`) tal cual:
     contiene la acción del operador.
2. **Ping automático ligado a la sesión (D-61).** El pinger del servidor
   (`servidor/pinger.py`, proceso suelto) queda **obsoleto**: no envió un solo
   ping en toda la campaña. Su función vive ahora en el microservicio: mientras
   una sesión está `capturing`, un ciclo asyncio ligado a ella encola un ping
   fPort 98 (1 byte = secuencia, no confirmado, el **mismo camino** que
   `POST /ping`) cada `PING_INTERVAL_S` (60 s por defecto, §8). Manual y
   automático **comparten la secuencia** 1..255 que se reinicia en `start`. El
   ciclo **muere con la sesión** (finish/abort/auto-finish y apagado del
   servicio). Cada envío —manual o automático— se **persiste** en la tabla
   `downlinks` (`session_id, seq, fport, ts, iso, origin`) y se expone:
   - `GET /sessions/{id}/downlinks` → JSON `[{seq, fport, ts, iso, origin}, …]`;
   - `GET /sessions/{id}/downlinks/csv` → CSV `<run_label>_dl.csv` (cabecera
     `seq,fport,ts,iso,origin`), hermano del CSV de uplinks de §6. Así el lado
     «enviado» del cruce de latencia con la microSD existe de verdad.
   - `ping_ack` gana el campo `origin` (`"manual"`/`"auto"`). Un `/ping` manual
     **sin sesión** sigue permitido (diagnóstico) pero no se persiste.
   - Un fallo de ChirpStack en un tick automático **no** tumba el ciclo (se
     reintenta al siguiente); en el `/ping` manual sigue subiendo como `503`.
3. **Compatibilidad.** La app v1/v2 no necesita cambios para seguir funcionando:
   los mensajes y rutas existentes no cambian de forma, solo se añaden campos
   (`origin`) y rutas nuevas. Sí **debería** añadir la descarga del `_dl.csv`
   junto al CSV de la sesión y mostrar el `detail` del 409 del gate.

---

## 16. Enmiendas v1.4 (corrida VUELO, D-64)

Nueva corrida que simula la telemetría de la cápsula durante 55 min de vuelo desde
puntos fijos. Formato de radio y decoder en [`VUELO-ESPEC.md`](VUELO-ESPEC.md);
aquí solo lo que afecta a este contrato.

1. **Corrida VUELO-A.** `{scenario:"VUELO", class:"A"}` → fPort **17**, perfil
   **`terreno-a`**, `target_uplinks` **165** (55 ráfagas × 3 paquetes). Solo existe
   en Clase A: `VUELO`/`C` → `400 corrida desconocida`. El `run_label` sigue el
   criterio de §3 (`AAAAMMDD-VUELO-A[-n]`). El gate de clase (§15.1), el ping
   automático (§15.2) y el aviso de desajuste de fPort (17 cuenta como fPort de
   corrida) se aplican igual.
2. **`target_uplinks` por corrida.** Deja de ser un único valor global: cada
   corrida puede fijar el suyo y las que no lo hacen usan `TARGET_UPLINKS` (300).
   `progress_pct` y la auto-finalización (§12.3) usan el de la sesión, que viene
   en `session.target_uplinks`. La app debe mostrar «TX n/target» con ese valor,
   no con 300 fijo.
3. **Uplinks parciales.** Cada uplink de VUELO trae solo una parte de la lectura:
   P1 posición, P2 ambiente/energía, P3 navegación. P2/P3 llegan con `latitude`,
   `longitude`, `altitude_m` **null**; P1 sin `battery_*` ni `temperature_c`. No
   hay columnas nuevas en SQLite (los campos extra viajan en `raw_json`). Ningún
   null se trata como 0: la distancia al gateway usa solo puntos con coordenadas.
   En VUELO, `battery_v`, `battery_pct`, `gps_fix` y `satellites` de `metrics` se
   toman del **último paquete que los trajo**, no del último uplink.
4. **Clave `vuelo` en `metrics` y `summary`.** En sesiones VUELO; `null` en las
   demás corridas:
   ```json
   "vuelo": {
     "por_tipo": {"posicion": 3, "ambiente": 1, "navegacion": 3},
     "rafagas_completas": 1,
     "rafagas_parciales": 2,
     "rafagas_perdidas": 1,
     "rafaga_max": 3,
     "rafagas_objetivo": 55
   }
   ```
   Se agrupa por `rafaga` del decoder: completa = llegaron P1+P2+P3; parcial = 1
   o 2 (la ráfaga en curso cuenta aquí hasta que llega su P3); perdida = ninguno,
   contando solo `0..rafaga_max`. `rafaga_max` es `null` si no ha llegado ninguna.
   Un paquete duplicado suma en `por_tipo` pero no hace una ráfaga «4/3».
5. **Clave `vuelo` en cada uplink** (`GET /sessions/{id}/uplinks` y WS `uplink`).
   Para uplinks de fPort 17, un objeto con los campos del `object` decodificado que
   no tienen columna: `tipo_paquete`, `rafaga`, `humidity_pct`, `speed_kmh`,
   `heading_deg`, `hdop`, `vspeed_ms`, `uptime_s`, `mag_ok`, `bme_ok` (los que
   falten → `null`). Para cualquier otro fPort, `vuelo: null`. `raw_json` sigue sin
   exponerse.
6. **Modo BLE 6 = VUELO-A.** La orden de modo por BLE (op `0x01`, §14 y
   `APP-CAMPO.md` §9) acepta modo **0..6**; 0–5 no cambian (URBANO-A, URBANO-C,
   TERRAZA-A, TERRAZA-C, CERRO16-A, CERRO16-C) y **6 = VUELO-A**. El firmware ya lo
   acepta.
7. **Compatibilidad.** Solo se añaden claves (`vuelo`) y una corrida; las seis
   corridas anteriores no cambian de forma ni de valores. Versión del servicio
   **1.2.0**.

## 17. Enmiendas v1.5 (segunda sonda, D-65)

Una segunda sonda, la T3 (`../firmware_lora32`, BLE `PICARO-LORA32`), comparte el
servicio con la T-Beam. Sigue habiendo **una sola sesión activa a la vez**; cada
sesión es de una sonda.

1. **`sonda` en `POST /session/start`.** Cuerpo `{scenario, class, sonda?}`, con
   `sonda` = `"tbeam"` (por defecto) o `"lora32"`. El cambio de perfil, el gate de
   clase (§15.1), los pings (§15.2) y la captura se hacen sobre el DevEUI de esa
   sonda. Sin `sonda`, la sesión es de la T-Beam, como en la app ≤ 2.1.0.
2. **La sonda `lora32` solo admite VUELO-A.** Cualquier otra corrida →
   `400 la sonda lora32 no admite la corrida …`. Sonda desconocida, o sin DevEUI en
   el entorno → `400`.
3. **Captura por DevEUI.** El servicio se suscribe a todos los devices de la
   aplicación y guarda solo los uplinks de la sonda de la sesión. Los de la otra
   sonda se ignoran en silencio, aunque coincida el fPort: no generan
   `fport_mismatch`.
4. **`session.sonda` y `session.dev_eui`** en toda respuesta con sesión. Las
   sesiones anteriores a D-65 salen como `sonda: "tbeam"`, `dev_eui: null`.
5. **`POST /profile`** acepta también `sonda` (por defecto `tbeam`). Un `POST /ping`
   sin sesión va a la T-Beam.
6. **Entorno.** `DEV_EUI` sigue siendo la T-Beam; `DEV_EUI_LORA32` es la T3.
7. **Payload de la T3.** El mismo de VUELO (§16, `VUELO-ESPEC.md`): P1/P2/P3 de 11 B en
   fPort 17. GPS, BME280 y magnetómetro van **simulados** en el firmware; la batería es
   real y llega sin porcentaje. El decoder no distingue sondas. La posición simulada
   **no se usa para la distancia** (ver 9).
8. **Compatibilidad.** Solo se añaden un campo opcional y dos claves. Versión del
   servicio **1.3.0**; app **2.2.0**.
9. **Distancia con el GPS del teléfono (v1.4.0).** En las sondas sin GPS propio
   (`lora32`), la app envía la posición del teléfono durante la sesión:
   - `POST /session/{id}/posicion` `{lat, lon, alt_m?, precision_m?, ts?}` → `201
     {posicion}`. Errores: `400` si las coordenadas están fuera de rango; `404` si la
     sesión no existe; `409` si no está capturando. `ts` es el instante del fix, en
     epoch UTC; si falta, se toma el de llegada. La app 2.3 lo manda cada 30 s.
   - `GET /sessions/{id}/posiciones` y `/sessions/{id}/posiciones/csv`
     (`<run_label>_pos.csv`).
   - WS: mensaje `posicion`, seguido de `metrics`.

   **Cálculo.** Cada uplink se empareja con la posición del teléfono más cercana en el
   tiempo, si está a ≤ 300 s, y se mide contra **el gateway que lo recibió**. Se usan
   las coordenadas que el gateway tenga en ChirpStack; si no tiene (0,0), las de
   `GW_LAT/GW_LON`. Las coordenadas de cada gateway se leen una vez y se guardan.
   En la T-Beam no cambia nada: mide con su GPS contra `GW_LAT/GW_LON`.
10. **Métricas nuevas** (`null` en la T-Beam):
    - `dist_gw_km_ultima`: la del último uplink.
    - `posicion_telefono` (`{ts, iso, lat, lon, alt_m, precision_m}`): la última
      posición recibida.
    - `gateway_ultimo` (`{id, lat, lon}`).

    `dist_gw_km_max` es, en la T3, el máximo de las distancias desde el teléfono.
11. **CSV de uplinks.** Columnas añadidas al final: `tel_lat, tel_lon,
    tel_precision_m, gw_lat, gw_lon, dist_gw_km`. Van rellenas en las sesiones de la
    T3 y vacías en las de la T-Beam. Servicio **1.4.0**; app **2.3.0**.
