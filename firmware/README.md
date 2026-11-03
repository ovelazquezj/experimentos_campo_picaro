# Firmware — radiosonda de pruebas de terreno

ESP-IDF v5.x + RadioLib 7.7.x para **LilyGo T-Beam Supreme** (ESP32-S3 + SX1262).

**Un solo binario cubre las 6 corridas.** No hay que recompilar entre ellas: se
eligen **desde la app por BLE o con el botón**, y la selección persiste en NVS.

> ✅ **Compila limpio** con ESP-IDF **v5.5.2** (GCC 14.2, target `esp32s3`).
> **v2 (con BLE):** binario ~723 KB sobre la partición `factory` de 3 MB, es
> decir **77 % libre**. (La v1, sin BLE, ocupaba ~435 KB.)

---

## Antes de compilar

```bash
# 1. Credenciales (credentials.json y credenciales_lorawan.h estan en .gitignore)
cp credentials.example.json credentials.json
#    y rellena dev_eui, app_key y los IDs del servidor
cp main/credenciales_lorawan.example.h main/credenciales_lorawan.h
#    y rellena DEV_EUI, JOIN_EUI y APP_KEY (sin el, la compilacion se detiene con #error)

# 2. Entorno ESP-IDF v5.x
. $HOME/esp/esp-idf/export.sh        # o donde lo tengas
idf.py --version                     # debe decir v5.x
```

Las credenciales que usa el firmware están en `main/credenciales_lorawan.h`
(fuera de git), que incluye `main/config_lorawan.h`; la plantilla versionada es
`main/credenciales_lorawan.example.h`. **Verifica que coinciden** con
`credentials.json` antes del primer flasheo.

---

## Compilar y flashear

```bash
# desde pruebas_terreno/firmware/
idf.py set-target esp32s3
idf.py build
idf.py -p <PUERTO> flash monitor      # Linux: /dev/ttyACM0 · Windows: COMx
```

RadioLib se descarga sola en el primer `build` (IDF Component Manager, ver
`main/idf_component.yml`). Hace falta conexión a internet esa primera vez.

---

## Qué debe verse al arrancar

Por el puerto serie, tras inicializar los periféricos:

```
seleccion guardada: CERRO16 Clase C  SF10/DR0  8.0s  fPort 16
=======================================
  DevEUI 0011223344550001 · US915 sub-banda 2
  6 corridas: 3 escenarios x 2 clases
=======================================
JOIN intento #1 ...
=== MENU: corto = cambiar · doble = ARRANCAR ===
```

Y **ahí se queda**: el menú bloquea hasta la doble pulsación. No se transmite
nada mientras tanto. Al confirmar:

```
=== ARRANCA 20260814-CERRO16-C ===
  CERRO16 · Cerro del Muerto, LoS a 16,35 km
  DR0/SF10 · 8.0 s · 300 uplinks · fPort 16 · Clase C
  el device profile del servidor debe ser: terreno-c
---- 20260814-CERRO16-C  TX 1/300 ----
  GNSS: FIX sats=9 | 24.31C | bat 4012mV(87%)
  payload 11B fPort 16 DR0/SF10 airtime ~371 ms | HEX 8a5c0d0d...
```

El join ocurre **antes** del menú a propósito: puede tardar y reintenta cada
15 s, así que sucede mientras se monta el equipo. Cuando el operador confirma, el
primer uplink sale en el acto en vez de tras una espera de duración imprevisible.

Tres cosas que deben cuadrar:
1. **El device profile del servidor es el de la línea `debe ser:`.** El firmware
   no puede comprobarlo ni corregirlo. Es el único error de la campaña que
   produce datos con aspecto perfectamente normal (ver el manual de campo).
2. **El `fPort` corresponde al escenario y clase** que muestra el OLED: 11/12
   urbano, 13/14 terraza, 15/16 cerro.
3. **El airtime** ronda 185 ms en SF9, 62 ms en SF7 y 371 ms en SF10.

---

## Riesgos conocidos, por orden de probabilidad

**1. `lorawan.cpp` es C++, no C.** RadioLib es C++ y no se puede llamar desde C.
Expone su API con `extern "C"`, y las cabeceras propias (`escenarios.h`,
`runlog.h`, `payload_terreno.h`) llevan el mismo envoltorio para que los módulos
en C y los `.cpp` compartan API. Si aparecen errores de enlazado con nombres
«decorados», mirar ahí primero.

**2. Firmas de la API de ESP-IDF v5.x.** Los drivers vienen del ejercicio 09
(que compila con IDF v5.5). Si tu IDF es más antiguo, el driver I2C o el de SPI
pueden haber cambiado de API.

**3. El mecanismo de corte NO conmuta ningún GPIO.** La placa va soldada y no se
le añade hardware, así que `CORTE_HABILITAR_GPIO` está en **0**: el corte y el
ping quedan como evento registrado con su marca de tiempo, que es lo único que
necesita la medida de latencia. Los pines 15/16 siguen declarados pero inactivos
y **sin verificar contra el esquemático**. Ponlo a 1 solo si algún día hay un
actuador real y se han comprobado esos pines.

**4. `sensores_corriente_ma()` devuelve siempre `false`.** El AXP2101 no mide
corriente de batería (solo tensión y porcentaje); el ADC de corriente existía en
el AXP192 de placas anteriores. La columna `batt_mA` del CSV queda vacía por
diseño. Ver la Adenda 1 del protocolo: por eso la autonomía se mide en banco.

---

## Probar sin GPS ni cielo

En `sensores.h`:

```c
#define SENSORES_MODO_BANCO   1    // genera datos sinteticos, sin GPS
```

Útil para verificar el join, el OLED, el botón y la escritura en microSD sin
salir del laboratorio.

---

## Mapa de ficheros

| Fichero | Qué hace |
|---|---|
| `main/escenarios.h/.c` | **La configuración de las 6 corridas.** Única fuente de verdad de DR, intervalo y fPort. También el botón (`boton_tomar()`), el cursor del menú (`seleccion_siguiente()`, `corrida_confirmar()`) y su persistencia en NVS |
| `main/app_main.cpp` | Arranque, join y la máquina MENÚ → CORRIDA → FIN → MENÚ |
| `main/lorawan.h/.cpp` | RadioLib: join, clase A/C, DR fijo, ADR off, downlinks |
| `main/payload_terreno.h/.c` | Empaquetado little-endian de 11/14 bytes y cálculo de airtime |
| `main/telemetry.*` + `gps_l76k.*` + `bme280.*` + `pmu_axp2101.*` | GPS L76K + BME280 + batería del PMU |
| `main/runlog.h/.c` | CSV por corrida en la microSD, una fila por uplink. Asigna el `run_id` con número de intento (`runlog_asignar_run_id()`) |
| `main/sdcard.*` | Montaje de la tarjeta. Viene del ej.09 y **no se modifica** |
| `main/oled_sh1106.*` | Pantalla de estado: menú, corrida y **la de emparejado (v2)** |
| `main/ble_control.h/.c` | **v2:** servidor GATT NimBLE. Ver abajo |
| `../decoder.js` | Codec de ChirpStack. **Ya subido al device profile del servidor** |

---

## v2 — Control por BLE (`ble_control`)

La sonda expone un servicio GATT por el que la app fija la corrida y lee su
estado. **El botón se conserva íntegro como respaldo**, y las pantallas de
configuración y de corrida quedan exactamente como en la v1.

### Qué hace el módulo, y qué NO hace

`ble_control.c` es deliberadamente tonto: **no decide política**. Recibe comandos
por un enlace que la pila ya cifró y autenticó, los encola, y publica el estado
que le den. Qué hacer con cada comando lo decide el bucle de `app_main.cpp`,
igual que con el botón.

Tres reglas estructurales que sostienen eso:

1. **Nada bloquea.** `ble_tomar_comando()` tiene la misma forma que
   `boton_tomar()`: consulta no bloqueante que devuelve y consume. Añadir BLE a
   la máquina de estados fue añadir una línea junto a la del botón, no
   reestructurarla.
2. **El módulo BLE no conoce la máquina de estados, y ésta no conoce NimBLE.**
   El acoplamiento es un puñado de enums.
3. **`ble_control.c` no incluye `oled_sh1106.h` ni `pmu_axp2101.h`.** La pantalla
   de emparejado la pinta `app_main.cpp`, que es quien pinta todas las demás. Es
   la garantía **estructural** de que el comportamiento visual de la v1 no puede
   cambiar por accidente desde aquí.

La entrada del botón y la del BLE se funden en `escenarios.c`, en
`comando_tomar(ctx, &c)`: una sola tabla de gestos por contexto, en vez de la
lógica repartida por los bucles. **El botón se atiende primero** — en un empate
gana quien está físicamente delante de la sonda; un comando BLE no atendido en
esa vuelta no se pierde, sigue pendiente 50 ms más.

### La seguridad la da la pila, no código nuestro

**LE Secure Connections con Passkey Entry.** No hay criptografía propia: ni HMAC,
ni nonces, ni secretos en NVS. Las características `Comando` y `Estado` se
declaran con `_ENC|_AUTHEN`, y eso es lo que **fuerza el emparejamiento**: un
central sin enlace seguro recibe *Insufficient Authentication* y Android inicia
el emparejamiento por su cuenta.

**El passkey no lo genera la pila.** Con `sm_io_cap = DISPLAY_ONLY`, NimBLE lo
*pide* (`BLE_GAP_EVENT_PASSKEY_ACTION`) y espera que la aplicación lo elija, lo
muestre y lo inyecte con `ble_sm_inject_io()`. Consecuencia de diseño que hay que
tener presente: **el passkey no existe hasta que hay un emparejamiento en
curso**, así que la pantalla de emparejado no puede ser estática — tiene tres
fases (esperando / passkey / fallo).

Se muestra siempre con **`%06lu`, no `%lu`**. Si el passkey sale `12345`, el
diálogo de Android espera `012345`, seis caracteres; imprimir cinco haría que el
emparejamiento fallara con `st=1028` en uno de cada diez intentos, al azar, y con
un síntoma indistinguible de haberlo tecleado mal.

**El emparejamiento sólo se acepta en el estado EMPAREJADO.** Fuera de él se
rechaza terminando la conexión. Lo fuerza una restricción del proyecto —no hay
dónde pintar el número sin tocar las pantallas de la v1— y resulta ser además la
decisión de seguridad correcta: **nadie empareja un teléfono nuevo sin que
alguien pulse el botón de la sonda**.

### Opciones de `sdkconfig.defaults` que importan

| Opción | Valor | Por qué |
|---|---|---|
| `CONFIG_BT_ENABLED` | `y` | NimBLE |
| `CONFIG_BT_NIMBLE_ENABLED` | `y` | |
| `CONFIG_BT_NIMBLE_MAX_CONNECTIONS` | `1` | Un central a la vez. Elimina de raíz «¿y si dos móviles mandan órdenes contradictorias?» y ahorra RAM |
| `CONFIG_BT_NIMBLE_ROLE_CENTRAL` / `_OBSERVER` | `n` | La sonda es sólo periférico: no escanea. Quita código y RAM |
| `CONFIG_BT_NIMBLE_SM_SC` | `y` | Secure Connections |
| **`CONFIG_BT_NIMBLE_SM_LEGACY`** | **`n`** | **Crítico.** Ver abajo |
| `CONFIG_BT_NIMBLE_NVS_PERSIST` | `y` | Sin esto el bonding no sobrevive a un reinicio y hay que emparejar en cada arranque |
| `CONFIG_BT_NIMBLE_MAX_BONDS` | `3` | Móvil principal + repuesto + margen. El cuarto desaloja al más antiguo |
| `CONFIG_SPIRAM` | **sin activar** | Se midió y **no hace falta**. Activarla cambia el arranque del dispositivo |

> ⚠️ **`SM_LEGACY=n` no es una optimización, es la defensa real.** `sm_sc = 1`
> dice que *queremos* Secure Connections, pero si el código de emparejamiento
> *legacy* está compilado y el par declara que no soporta SC, la pila **puede
> negociar a la baja** — y el legacy tiene un intercambio de llaves **recuperable
> en pasivo**, que es exactamente el agujero que este diseño existe para cerrar.
> Compilarlo fuera es lo que hace que la degradación silenciosa sea imposible.
> Configuración y compilación juntas; ninguna de las dos basta sola.

Igual de importante en el mismo sentido: **`sm_io_cap` no es cosmético**. Con
`NO_INPUT_OUTPUT` el emparejamiento cae a *Just Works*, que se completa sin
enseñar ningún número, con `encrypted = 1` y **`authenticated = 0`**, y **sin**
protección contra man-in-the-middle. Es decir: **funciona y parece que funciona**.
Por eso el firmware sólo da por bueno un emparejamiento con `encrypted = 1` **y**
`authenticated = 1` **y** `key_size = 16`, y no sale del estado EMPAREJADO sin
las tres. Si en algún sitio del código se lee `encrypted` sin leer `authenticated`
al lado, es un bug.

### Coste medido en hardware

| Qué | Medido |
|---|---|
| Cadencia de uplinks con BLE conectado | **8,07 s clavados**, sin un solo salto (24 uplinks); **8,08 s** en otros 37 ya con el enlace cifrado |
| SRAM interna libre tras el JOIN | **~211 000 B**, bloque contiguo **~168 000 B** |
| Coste de NimBLE | ~59 KB de SRAM interna |
| Flash | binario ~723 KB sobre 3 MB → **77 % libre** |
| Emparejamiento | `cifrado=1 autenticado=1 bonded=1 llave=16` — Passkey Entry real, no *Just Works* |
| Reconexión con bonding | **270 ms**, sin diálogo y sin código |

Que la cadencia salga clavada es lo que cierra de verdad la coexistencia, no el
hecho de que transmitiera: si NimBLE estuviera robando CPU o estorbando al
planificador del SX1262, saldría aquí como *jitter*. **La PSRAM sigue
desactivada y no hace falta.**

> **Canario a vigilar:** `NimBLE: Failed to restore IRKs from store; status=8` en
> el arranque significa que no hay ningún bonding guardado. Es normal en una
> sonda de fábrica. Si aparece **después** de haber emparejado un móvil y
> reiniciado, el bonding **no está persistiendo**: revisar `NVS_PERSIST` y
> `ble_store_config_init()`.

---

## Cómo se elige y se arranca una corrida

**Seleccionar no es arrancar.** Son dos acciones distintas y la separación es
deliberada: antes bastaba cambiar de escenario para que empezara a transmitir en
el acto, y el principio de cada corrida se llenaba de uplinks tomados mientras
aún se estaba colocando la antena.

```
arranque → JOIN → [EMPAREJADO] → MENÚ → CORRIDA → FIN → MENÚ
                        ↑ sólo si NO hay ningún móvil emparejado
                        ↑ o con pulsación LARGA desde el MENÚ
```

| Estado | Corta | Doble | Larga (≥ 2 s) |
|---|---|---|---|
| **MENÚ** | siguiente de las 6 opciones | **confirma y ARRANCA** | **abre la ventana de emparejamiento** |
| **CORRIDA** | se ignora | se ignora | abortar → menú |
| **FIN** | se ignora | se ignora | → menú |
| **EMPAREJADO** | saltar → menú | **borra TODOS los bonds** | → menú |

Una sola regla que enseñar en campo: **larga = ir al menú, siempre**. En el menú
ya se está en el menú, y ése es precisamente el hueco donde se colgó el gesto de
emparejar. La **doble** conserva su significado de siempre —el acto deliberado e
irreversible de esta pantalla—: en el menú arranca; en EMPAREJADO olvida los
teléfonos. El gesto destructivo **no se anuncia en pantalla** a propósito, así
que sólo existe en el manual de campo.

Por BLE, **seleccionar es arrancar**: equivale exactamente a la doble pulsación,
sólo que diciendo además *cuál*. No existe un comando de «mover el cursor»,
porque navegar es un gesto local del botón. Y por eso el BLE puede arrancar desde
`FINALIZADO` sin pasar por el menú, mientras que el botón sigue necesitando la
larga: el botón no sabe decir «arranca la 3», sólo navegar.

Los comandos se validan contra el estado actual de la sonda: `seleccionar` se
**rechaza** durante una corrida (cambiar de modo a mitad mezclaría dos escenarios
bajo el mismo `run_id`) y durante el JOIN (si no, se quedaría en la cola y
arrancaría una corrida en un instante impredecible, minutos después). `abortar`
estando ya en configuración es un **no-op que devuelve OK**, no un error: la app
lo manda a ciegas al cerrar una sesión, y convertir una operación de higiene en
un aviso rojo enseña al operador a ignorar los avisos.

En el menú parpadea la línea de selección y cada pulsación corta avanza por las
siete opciones (URBANO-A, URBANO-C, TERRAZA-A, TERRAZA-C, CERRO16-A, CERRO16-C,
VUELO-A, cíclico; VUELO desde D-64, ver `../docs/VUELO-ESPEC.md`). Navegar **no transmite, no reconfigura la radio y no toca los
contadores**: `seleccion_siguiente()` solo mueve un cursor. Nada se aplica hasta
que `corrida_confirmar()` persiste la elección y pone los contadores a cero.

Durante la corrida las pulsaciones corta y doble **se descartan a propósito**:
`boton_tomar()` las entrega igual, y es quien llama el que decide tirarlas. Un
roce del botón dentro de la mochila no puede alterar una medida de 40 minutos.

Al completar los 300 uplinks la sonda muestra `FINALIZADO` y **deja de
transmitir**; no encadena la siguiente sola, porque hacerlo mezclaría dos
corridas y nadie que llegue a la sonda podría saber si hay algo en marcha.

> **El menú responde con ~0,4 s de retardo.** Para saber que una pulsación no es
> la primera de una doble hay que esperar a que venza la ventana de la doble
> (`BTN_DOBLE_MS`). Es el precio de tener dos gestos en un solo botón, no un
> fallo. La larga, en cambio, se emite al cumplirse los 2 s sin esperar a que se
> suelte, para que el operador vea la reacción y sepa que ya puede soltar.

La selección se guarda en NVS (clave `sel`, índice 0..5) **al confirmar**, no al
navegar. Tras reflashear la clave no existe y se arranca en URBANO Clase A: es
inocuo, porque con el menú la corrida siempre se elige y se confirma a mano, así
que un valor inicial distinto no puede colarse en una medida.

Abortar con la pulsación larga es una operación limpia. Lo ya registrado no se
pierde ni se mezcla: al reanudar el mismo escenario y clase el mismo día,
`runlog_asignar_run_id()` sonda la microSD y crea `20260814-CERRO16-C-2.csv` en
vez de reutilizar el fichero anterior. Se sonda la tarjeta en lugar de llevar un
contador en NVS porque el estado real es el de los ficheros, y así no hay forma
de que un contador se desincronice de lo que hay escrito.

El procedimiento completo de campo, con los dibujos de cada pantalla, está en
[`../docs/MANUAL-DE-CAMPO.md`](../docs/MANUAL-DE-CAMPO.md).

> **El OLED queda permanentemente encendido.** No hay apagado automático ni
> temporizador de inactividad: el único `0xAE` del driver está dentro de la
> secuencia de inicialización, seguido del `0xAF` que la enciende. Y así debe
> ser: el menú tiene que poder verse parpadear, y la pantalla de `FINALIZADO`
> tiene que ser legible cuando alguien llega a la sonda un rato después.
>
> Consume del orden de 20–30 mA, pero es una carga **constante e idéntica en las
> seis corridas**, así que no sesga la comparación entre clases —lo que se mide
> es la diferencia, y una carga igual en ambos brazos se cancela en la resta—.
> Lo que sí infla es el consumo **absoluto**, hasta sepultar los 5–10 mA que
> separan la Clase A de la C. Por eso la autonomía (H3) no se mide en campo sino
> en banco (Adenda 1 del protocolo), y por eso no se extrapola de aquí la
> autonomía de un despliegue real, que no llevaría pantalla.
