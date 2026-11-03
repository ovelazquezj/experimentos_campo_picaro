# Corrida VUELO — especificación (D-64)

> **Documento interno.** Contrato común de firmware, decoder, microservicio, app y
> análisis para la corrida que simula la telemetría de la cápsula. Cualquier cambio
> aquí obliga a tocar las cinco piezas.

## Qué es

Simula lo que mandará la cápsula durante **55 minutos de vuelo**, medido desde
**puntos fijos** en altura y a distancia (cerros). Se sacrifica frecuencia a
cambio de mandar **todos los sensores** de la T-Beam dentro del límite de 11 bytes
de DR0.

| | |
|---|---|
| Escenario / clase | `VUELO` / **solo A** (perfil `terreno-a`) |
| `run_id` | `AAAAMMDD-VUELO-A[-n]` |
| Modo del menú / BLE | **6** (0–5 no cambian: URBANO-A, URBANO-C, TERRAZA-A, TERRAZA-C, CERRO16-A, CERRO16-C) |
| Radio | DR0 / SF10 / 125 kHz, ADR off, 11 bytes (ToA 371 ms < 400 ms de *dwell*) |
| fPort | **17** (todos los paquetes) |
| Cadencia | una **lectura completa cada 60 s** → **ráfaga** de 3 paquetes, **uno cada 20 s** |
| Fin de corrida | **55 ráfagas = 165 uplinks** (`target_uplinks` = 165) |
| Pings | se mantienen (1/min, fPort 98): miden si la cápsula **recibe órdenes** a esa distancia |

Los tres paquetes de una ráfaga llevan la **misma lectura**, tomada al empezar la
ráfaga. Orden fijo: P1 → P2 → P3.

## Formato (little-endian, 11 bytes exactos)

**Byte 0, cabecera:** `tipo << 6 | (rafaga & 0x3F)`

- `tipo`: 1 = P1 posición · 2 = P2 ambiente · 3 = P3 navegación (0 reservado → error)
- `rafaga`: 0..54 (6 bits; el contador empieza en 0 en cada corrida)

**Sentinelas «no disponible»:** `0x7FFF` en int16, `0xFFFF` en uint16, `0xFF` en uint8.
El decoder los traduce a `null`.

### P1 — posición

| Bytes | Tipo | Campo | Escala |
|---|---|---|---|
| 1–4 | int32 | `latitude` | grados × 1e7 |
| 5–8 | int32 | `longitude` | grados × 1e7 |
| 9–10 | uint16 | `altitude_m` | metros (0..65534; negativos → 0) |

Sin fix: lat = lon = 0 y alt = `0xFFFF` → el decoder da `gps_fix=false` y lat/lon/alt `null`.

### P2 — ambiente y energía

| Bytes | Tipo | Campo | Escala |
|---|---|---|---|
| 1–2 | int16 | `temperature_c` | °C × 100 |
| 3–4 | uint16 | `pressure_hpa` | hPa × 10 |
| 5 | uint8 | `humidity_pct` | % entero |
| 6–7 | uint16 | `battery_v` | mV (el decoder da **voltios**) |
| 8 | uint8 | `battery_pct` | % |
| 9 | uint8 | `satellites` | número |
| 10 | uint8 | banderas | bit0 `gps_fix` · bit1 `usb_powered` · bit2 `charging` · bit3 `gps_active` · bit4 `mag_ok` · bit5 `bme_ok` |

### P3 — navegación

| Bytes | Tipo | Campo | Escala |
|---|---|---|---|
| 1–2 | uint16 | `speed_kmh` | km/h × 10 |
| 3–4 | uint16 | `heading_deg` | grados × 10 (0..3599); sin magnetómetro → `0xFFFF` |
| 5 | uint8 | `hdop` | × 10 (satura en 254) |
| 6–7 | int16 | `vspeed_ms` | m/s × 10, velocidad vertical = Δaltitud GPS / Δt entre ráfagas; primera ráfaga o sin fix → `0x7FFF` |
| 8–10 | uint24 | `uptime_s` | segundos desde el arranque |

## Salida del decoder (fPort 17)

Siempre: `tipo_paquete` (`"posicion"` · `"ambiente"` · `"navegacion"`), `rafaga`,
`escenario: 4`, `clase: "A"`, `escenario_nombre: "vuelo (puntos fijos)"`.
Más los campos del tipo con los nombres de las tablas. Los nombres coinciden con
las columnas del microservicio: `latitude`, `longitude`, `altitude_m`, `gps_fix`,
`satellites`, `battery_v`, `battery_pct`, `charging`, `usb_powered`, `gps_active`,
`temperature_c`, `pressure_hpa`. Los demás (`humidity_pct`, `speed_kmh`,
`heading_deg`, `hdop`, `vspeed_ms`, `uptime_s`, `mag_ok`, `bme_ok`, `tipo_paquete`,
`rafaga`) viajan en `raw_json`.

**Consecuencia para quien consume:** un uplink de VUELO trae **solo una parte**
de la lectura. P2 y P3 no tienen posición y P1 no tiene temperatura. El mapa, el
panel y las gráficas toman cada magnitud del **último paquete que la trajo**, y
nunca pintan un 0 o un null como si fuera un dato.

## Métricas (microservicio y análisis)

- PDR estimado = recibidos / rango de fCnt, igual que en el resto de corridas.
- Además, por **tipo de paquete** (P1/P2/P3) y **ráfagas completas** (3 de 3),
  **parciales** (1–2) y **perdidas** (0), agrupando por `rafaga`.

## microSD

- `<run_id>.csv`: un renglón por **paquete** (fallidos incluidos), como en las
  demás corridas, con dos columnas nuevas al final: `tipo` y `rafaga`. En las
  corridas antiguas quedan vacías.
- `<run_id>_lecturas.csv`: un renglón por **ráfaga** con la lectura completa.
