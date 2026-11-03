# Firmware — sonda T3 (LoRa32) de pruebas de terreno

ESP-IDF v5.5 + RadioLib 7.7.1 para **LILYGO T3 v1.6.1** (ESP32-PICO-D4 + SX1276).

Es la **segunda sonda** de la campaña y sirve para probar la conexión con un
gateway en campo. Corre **una sola corrida, VUELO-A** (DR0/SF10, el máximo
alcance de US915; ráfagas de 3 paquetes cada 20 s; fPort 17; Clase A), con la
máquina de estados de la T-Beam Supreme (`../firmware`). Se opera **solo desde la
app**, por BLE: no tiene botón.

No tiene sensores: **los simula** (ver «Sensores simulados») y manda los mismos
paquetes de 11 bytes que la T-Beam. En la app se ve lo mismo que con la T-Beam:
la lectura de VUELO, el RSSI, el SNR, el PDR y las ráfagas.

---

## La placa frente a la T-Beam

| | T-Beam Supreme | T3 v1.6.1 |
|---|---|---|
| MCU | ESP32-S3, USB nativo | ESP32 clásico, puente USB-serie CH9102 |
| Radio | SX1262 + TCXO | SX1276, sin TCXO |
| Energía | PMU AXP2101 | sin PMU; batería por ADC (IO35, divisor 1:2), sin porcentaje |
| Sensores | GPS, BME280, magnetómetro | **simulados** (`simulacion.h`) |
| Corridas | las 7 | **solo VUELO-A** |
| Pantalla | SH1106 | SSD1306 @0x3C |
| LED de modo | CHGLED del PMU | LED verde (IO25) |
| Botón | BOOT (IO0), respaldo sin app | **ninguno**: solo app |
| Nombre BLE | `PICARO-CAMPO` | `PICARO-LORA32` |

### Una sola corrida

El firmware se compila con `PICARO_CORRIDA_FIJA=6` (`main/CMakeLists.txt`). Con
eso:

- arranca siempre con VUELO-A seleccionada, ignorando lo guardado en NVS;
- por BLE, cualquier otro modo se rechaza con ATT `0x83` (parámetro inválido).

### Sin botón: todo desde la app

La T3 v1.6.1 no tiene botón de usuario: el único pulsador es RESET. El firmware lo
tiene desactivado (`BOTON_HABILITADO 0` en `board_pins.h`). En esta placa IO0 va
al circuito de auto-reset del puente USB, y si se leyera, abrir o cerrar el monitor
serie produciría pulsaciones fantasma.

| Situación | T3 |
|---|---|
| Primer arranque, sin teléfono emparejado | Arranca en EMPAREJADO y espera a la app; sale al emparejar |
| Volver a emparejar u olvidar teléfonos | `idf.py erase-flash` y reflashear: se pierden los bonds |
| Arrancar, abortar o hacer re-join | Desde la app, como con la T-Beam |
| Sin app ni teléfono | Apagar y encender: la sonda vuelve al menú y no transmite hasta recibir una orden |

---

## Servidor y app

Las dos sondas usan **el mismo microservicio** (`https://campo.pi-caro.org`), el
mismo token y la misma app (≥ 2.2.0), **una sesión a la vez**:

1. En la app, «Buscar sonda» → **PICARO-LORA32**.
2. La app reconoce la T3 por su nombre BLE. El selector solo deja VUELO A, y al
   arrancar la app pide la sesión al servidor con `sonda: lora32`.
3. El microservicio aplica el perfil `terreno-a`, el gate de clase, los pings y
   la captura al DevEUI de la T3 (`DEV_EUI_LORA32` en su entorno). Los uplinks de
   la T-Beam, si está encendida, no entran en la sesión.
4. **Distancia:** mientras la sesión captura, la app (≥ 2.3.0) lee el GPS del
   teléfono, que va junto a la sonda, y manda su posición cada 30 s. Pide permiso
   de ubicación la primera vez. El servidor mide la distancia entre esa posición y
   **el gateway que recibió cada paquete**, con las coordenadas que el gateway tenga
   en ChirpStack. El panel «Distancia · GPS del teléfono» muestra la distancia
   actual y la máxima, el gateway, la posición del teléfono y su precisión. Todo
   queda guardado con la sesión: en el CSV de uplinks y en `<run_label>_pos.csv`.

Detalle en `../microservicio/README.md` («Sondas») y en `../docs/CONTRATO-CAMPO.md` §17.


---

## Antes de compilar

```bash
# Credenciales OTAA (credenciales_lora32.h esta en .gitignore)
cp main/credenciales_lora32.example.h main/credenciales_lora32.h
#   y rellena DEV_EUI, JOIN_EUI y APP_KEY tal cual estan en ChirpStack
```

---

## Compilar y flashear

```bash
# desde pruebas_terreno/firmware_lora32/
idf.py set-target esp32
idf.py build
idf.py -p <PUERTO> flash monitor
```

El puente USB-serie (CH9102) tiene auto-reset: `idf.py flash` pone la placa en
modo descarga sola y el número de COM no cambia. Hace falta un cable USB **de
datos**: con uno solo de carga, la placa se enciende pero Windows no muestra
ningún puerto.

---

## Qué debe verse al arrancar

```
#   LILYGO T3 v1.6.1 (ESP32 + SX1276)       #
#   sensores SIMULADOS (simulacion.h)       #
...
I (...) escenarios: seleccion guardada: VUELO Clase A  SF10/DR0  20.0s  fPort 17
I (...) escenarios: sin boton: la sonda se opera solo desde la app (BLE)
I (...) pmu_t3: bateria por ADC en IO35: 4232 mV
I (...) oled: SSD1306 iniciado
I (...) ble_control: anunciando como 'PICARO-LORA32'
I (...) picaro:   DevEUI 0011223344550003 · US915 sub-banda 2
I (...) picaro:   corrida fija: VUELO-A (modo 6)
W (...) picaro: === MENU: se opera desde la app ===
I (...) lorawan: JOIN NUEVO por aire (JoinAccept recibido). Enlace REAL.
```

Al arrancar la corrida desde la app, cada uplink se ve así:

```
---- 00000000-VUELO-A  TX 1/165 ----
  rafaga 1/55  paquete P1
  SIMULADO: 22.14780,-102.27660 2010m | 25.19C 800.8hPa 55% | bat 4340mV
  payload 11B fPort 17 DR0/SF10 airtime ~371 ms | HEX 41707c330d50d409c3da07
```

El GPS simulado no da hora, así que el `run_id` de la microSD empieza siempre por
`00000000`; el número de intento distingue una corrida de otra. La hora de
referencia la pone el servidor al recibir el uplink. Sin tarjeta microSD, la
corrida funciona igual, pero sin el log local.

---

## Sensores simulados

La T3 no tiene GPS, BME280 ni magnetómetro. `telemetry_collect()` (`main/telemetry.c`)
rellena esas magnitudes con los valores de **`main/simulacion.h`**, de modo que la
corrida VUELO manda exactamente los P1/P2/P3 de la T-Beam (`../docs/VUELO-ESPEC.md`),
11 bytes cada uno. El decoder y la app no distinguen una sonda de otra.

| Magnitud | Valor |
|---|---|
| Posición | **fija**: `SIM_LAT`, `SIM_LON`, `SIM_ALT_M` (el punto de prueba) |
| Satélites, HDOP | 9 y 0,9 (fix siempre) |
| Temperatura, presión, humedad | 25 °C, 800 hPa y 50 %, oscilando suavemente (periodo de 5 min) para que se vea cambiar |
| Rumbo, velocidad, velocidad vertical | 0 (sonda quieta) |
| **Batería y uptime** | **reales** (ADC y reloj) |

La posición simulada **no se usa para medir distancias**: solo rellena el panel de
VUELO. La distancia de la T3 sale del **GPS del teléfono** (ver «Servidor y app»).
Aun así, conviene poner en `SIM_LAT`/`SIM_LON`/`SIM_ALT_M` el punto de la prueba,
para que el mapa no pinte la sonda en otro sitio.

El OLED lo dice en su línea 4 («Sensores SIMULADOS») y el log serie marca cada
lectura como `SIMULADO`.

---

## Módulos compartidos con `../firmware`

Estos ficheros son **copias** de los de la T-Beam. Un arreglo en uno se aplica
también en el otro:

| Copia sin cambios | Copia con cambios |
|---|---|
| `lorawan.cpp/.h`, `escenarios.h`, `runlog.c/.h`, `payload_terreno.c/.h`, `i2c0.c/.h`, `ble_control.h`, `esp_hal.h` ¹ | `app_main.cpp` (placa, textos sin botón, log de lo simulado), `escenarios.c` (`#if BOTON_HABILITADO`, `#ifdef PICARO_CORRIDA_FIJA`), `ble_control.c` (nombre BLE y modo fijo), `sdcard.c` (bus propio), `telemetry.c/.h`, `config_lorawan.h` (credenciales fuera) |

¹ `esp_hal.h` solo cambia en comentarios.

Para ver en qué se separan:

```bash
cd pruebas_terreno
for f in lorawan.cpp lorawan.h escenarios.c escenarios.h runlog.c runlog.h \
         payload_terreno.c payload_terreno.h i2c0.c i2c0.h ble_control.c \
         ble_control.h app_main.cpp; do
  diff -q firmware/main/$f firmware_lora32/main/$f
done
```

Propios de esta placa: `board_pins.h`, `sensores_config.h`, `radio.cpp/.h`
(SX1276 en VSPI), `pmu_t3.c/.h` (ADC de batería y LED, con la misma API que
`pmu_axp2101.h`), `oled_ssd1306.c/.h`, `gps_ninguno.c` (la T3 no tiene GPS) y
`simulacion.h` (los valores simulados, que aplica `telemetry.c`).
