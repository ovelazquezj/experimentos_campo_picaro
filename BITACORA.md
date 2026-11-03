# Bitácora de decisiones — Pruebas de terreno

> **Documento interno.** Contiene datos reales de infraestructura (dominio, UUIDs, IP).
> No publicar en el repositorio público `radiosonda_PIcaro` ni en la wiki.

> ⛔ **Regla dura, establecida tras el incidente [I-01](#incidente-i-01--el-cambio-de-rx1_delay-rompió-el-ejercicio-09).**
> La **configuración global** del servidor ChirpStack —ficheros `region_*.toml`,
> `chirpstack.toml`, temporizadores— **no se modifica por ningún proyecto**. Si el
> experimento no cabe con la configuración existente, **se ajusta el experimento**.
> Lo **aditivo** sí es aceptable: crear device profiles, dar de alta devices, añadir
> usuarios MQTT. Ante la duda, preguntar antes de escribir en el servidor.

Proyecto: radiosonda LoRaWAN para caracterización de cobertura en tres escenarios,
con comparación Clase A / Clase C.

Infraestructura: ChirpStack propio en `<IP_DEL_SERVIDOR>` (`lns.pi-caro.org`,
`api.pi-caro.org`, `mqtt.pi-caro.org`). Tenant `Proyecto PiCARO`
(`<TENANT_ID>`), aplicación `PiCARO`
(`<APP_ID>`).

---

## 1. Decisiones vigentes

| # | Decisión | Valor | Estado |
|---|---|---|---|
| D-01 | Stack LoRaWAN | RadioLib 7.7.1 sobre ESP-IDF v5.x | Vigente |
| D-02 | Banda y sub-banda | US915, sub-banda 2 (canales 8–15) | Vigente |
| D-03 | Escenario 1 — URBANO, móvil en vehículo | DR1 / SF9, **7 s** | Vigente (intervalo antes 5 s, ver R-04) |
| D-04 | Escenario 2 — TERRAZA, piso 5 exterior | DR3 / SF7, **7 s** | Vigente (antes «azotea 6 pisos» y 2,5 s, ver D-19 y R-04) |
| D-05 | Escenario 3 — CERRO16, LoS a **15,27 km** | DR0 / SF10, **8 s** | Vigente (distancia corregida 2026-08-29, ver D-20; intervalo antes 3 s, ver R-04) |
| D-06 | ADR | Desactivado en los tres escenarios | Vigente |
| D-07 | Clase LoRaWAN | Variable del experimento: A y C por escenario | Vigente |
| D-08 | `rx1_delay` del servidor | **5 s — intocable** | Restaurado tras I-01 (ver R-03) |
| D-09 | Payload base | 11 bytes, `packed`, little-endian | Vigente |
| D-10 | Extensión de payload | +3 bytes (batería) cuando el DR lo permite | Vigente |
| D-11 | Temperatura | `int8_t`, °C × 2 (paso 0,5 °C) | Vigente |
| D-12 | Etiquetado de corrida | `fPort` 11–16 (escenario × clase) | Vigente |
| D-13 | Comando de corte | `fPort` 99, byte mágico `0xA5` | Vigente |
| D-14 | Ping de latencia | `fPort` 98, cualquier byte | Vigente |
| D-15 | Sensores | Reales: BME280 (I²C) + L76K (UART) | Vigente |
| D-16 | DevEUI | `0011223344550001`, el del ej.09, con perfil conmutable | **Revertida** (antes «DevEUI nuevo», ver R-04) |
| D-17 | Datos en documentación | Reales (documento interno) | Vigente |
| D-18 | Ubicación del proyecto | `C:\dev\PiCARO\pruebas_terreno\`, fuera del repo | Vigente |
| D-19 | Emplazamiento del escenario 2 | Terraza del piso 5, exterior (no piso 7 tras ventana) | Vigente |
| D-20 | Distancia real al cerro | **15,27 km** (haversine, coordenadas reales) | **Corregida 2026-08-29** — decía 16,35 km, de un punto de cima aproximado. El nombre `CERRO16` y los `fPort` se conservan |
| D-21 | Selección de corrida | Botón físico + persistencia en NVS, un solo firmware | Vigente (mecanismo redefinido en D-37) |
| D-22 | OLED | **Permanentemente encendido** | **Corregida 2026-07-19** — decía «apagado automático a los 30 s», que nunca se implementó (ver D-37) |
| D-23 | Duración de corrida | **300 uplinks**, no tiempo fijo | Vigente (antes 600, ver R-04) |
| D-24 | Réplicas | 1 por celda → 6 corridas | Vigente |
| D-25 | Criterio de PDR | ≥ 80 % (esc. 1 y 2) · ≥ 50 % (cerro) | Vigente |
| D-26 | Control de validez A vs C | χ² α = 0,05 **y además** Δ > 5 pp | Vigente |
| D-27 | Fallo de join | Reintento con backoff indefinido | Vigente |
| D-28 | Escenario 1 — desplazamiento | Vehículo a 30–40 km/h (~1 punto cada 50 m) | Vigente |
| D-29 | Corrida incompleta | Marcar parcial y repetir | Vigente |
| D-30 | Autonomía en Clase C | Sin umbral: medir y reportar | Vigente |
| D-31 | Mecanismo de corte en campo | **Desarmado** las 6 corridas (GPIO + LED) | Vigente |
| D-32 | Uplinks fallidos | Se registran (denominador del PDR) | Vigente |
| D-33 | Modo banco sin GPS | Disponible para pruebas en interiores | Vigente |
| D-34 | Base del firmware | El del **ejercicio 09**, con tres añadidos | Vigente (ver I-01) |
| D-35 | Device profiles | **Dos nuevos** (Clase A / Clase C) sobre el device existente | Vigente |
| D-36 | Configuración global del servidor | **Intocable** por cualquier proyecto | Vigente (tras I-01) |
| D-37 | Selección de corrida | **Menú con arranque explícito**: seleccionar ≠ arrancar | Vigente |
| D-38 | Fin de corrida | `FINALIZADO` fijo, sin transmitir; no encadena la siguiente | Vigente |
| D-39 | Corrida abortada y reanudada | Fichero nuevo con nº de intento; **corridas distintas** en el análisis | Vigente |
| D-40 | LED de la placa | **Indicador de modo**: parpadea ⇔ estás en el menú; apagado en todo lo demás | Vigente |
| D-41 | Join en cada arranque | **`FORCE_FRESH_JOIN=1`**: join OTAA real siempre. Un join fallido en el cerro aborta la corrida, y eso es correcto | Vigente |
| D-42 | Despliegue de la app de campo | **Opción A**: subdominio `campo.pi-caro.org` por Caddy, contenedor en la red `picaro`, **sin puerto nuevo** | Vigente |
| D-43 | Qué es «Arrancar» en la app | **Abrir una sesión de captura** en el servidor (perfil + fila + expected_fport), **no** controlar la radio | Vigente |
| D-44 | Navegación de la app | 3 pestañas (Panel/Mapa/Gráficos) + menú `≡` (Sesiones/Acerca de) + botón `?` (Ayuda) | Vigente |
| D-45 | Autenticación de la app | **Token Bearer** único, local en el dispositivo; **TLS obligado** | Vigente |
| D-46 | Icono y branding | Generados en `branding/` (Pi embebido + señal LoRa + pluma de Ícaro); se reutilizan | Vigente |
| D-47 | Sesiones: replay y borrado | Replay (mapa+gráficas) de sesiones guardadas, foto fija; borrado con confirmación irreversible; ambos sobre el servidor | Vigente |
| D-48 | Dónde se elige la corrida (v2) | **En la app, una sola vez**: se propaga al servidor (perfil + sesión) y a la sonda por **BLE**. Orden: servidor primero, BLE después. Botón físico = **respaldo completo** | Vigente |
| D-49 | Seguridad del enlace BLE | **LE Secure Connections con Passkey Entry** (emparejamiento del propio BLE), no autenticación propia. Sustituye a la decisión cerrada D2/P1: se midió y la premisa era falsa | Vigente |
| D-50 | Contra la degradación silenciosa a *Just Works* | **`SM_LEGACY=n`** (compilar fuera el emparejamiento legacy) **y** exigir `authenticated=1` + `key_size=16`, no sólo `encrypted=1` | Vigente |
| D-51 | Cuándo se puede emparejar | **Sólo en el estado EMPAREJADO**, al que se entra con **pulsación larga**. Corta = salir; **doble = borrar todos los bonds** (no señalizado: sólo en el manual) | Vigente |
| D-52 | Gate de la app (RF-7) | Selector y **Arrancar** deshabilitados sin sonda por BLE, **diciendo por qué**. **Abortar SIEMPRE disponible**, con enlace o sin él | Vigente |
| D-53 | Aviso de sonda parada | Banda no descartable si la sonda deja de correr con la sesión abierta, con botón *Cerrar sesión*. **No cierra sola**: no destruir por inferencia | Vigente |
| D-54 | Arranque operable sin enlace (C-Fondo) | El JOIN deja de bloquear el control: pasa a **tarea en segundo plano** y la sonda es operable (emparejar, navegar, seleccionar) **desde el arranque**; el enlace LoRa se adquiere por detrás | Vigente |
| D-55 | Arbitrio de propiedad de la radio | Un **mutex** da a la radio un único dueño; la tarea de join la **suelta ANTES** de marcar «unido» y el bucle la toma **DESPUÉS** ⇒ contención cero. Descartada la herencia de prioridad, innecesaria | Vigente |
| D-56 | Estados BLE del arranque | **`SIN_ENLACE = 0x06`** (menú operable sin enlace) y **`ESPERANDO_ENLACE = 0x07`** (arranque agendado esperando enlace); **`UNIENDO = 0x04` RETIRADO** (no reutilizar) | Vigente |
| D-57 | Seleccionar sin enlace (D2) | No se rechaza: entra en `ESPERANDO_ENLACE`, **espera acotada y abortable**, arranca sola al unir. **Abortar siempre disponible**. El gate de la app (D-52) deja de exigir enlace LoRa: se muestra como indicador aparte | Vigente |
| D-58 | La v2 cambia el contrato BLE | Se acepta y documenta la **reversión** de «la v2 no cambia el contrato» (Addendum A del contrato). No hay firmware desplegado contra la versión previa: nada que versionar | Vigente |
| D-59 | Aborto de una corrida esperando enlace | Al abortar desde `ESPERANDO_ENLACE` (botón), la sonda **publica `ABORTADA`** (uniforme con el aborto de una corrida en marcha) y la app cuenta `ESPERANDO_ENLACE` como **corrida viva**, de modo que el aviso de sonda parada (D-53) también cubre ese caso. **Hallado y verificado en Fase E** | Vigente |
| D-60 | Gate de clase en `start` | Tras cambiar el perfil, `start` **lee la clase efectiva** (`classEnabled`) y si no coincide con la corrida **rechaza con 409** («clase desajustada: apaga y enciende la sonda y vuelve a arrancar») + `warning` WS. ChirpStack congela la clase en el JOIN (issue #360); el PUT de perfil no la actualiza | Vigente |
| D-61 | Ping de latencia ligado a la sesión | El pinger suelto (`servidor/pinger.py`, **obsoleto**: no envió nada en la campaña) se sustituye por un **ciclo asyncio del microservicio**: 1 ping fPort 98 cada `PING_INTERVAL_S` (60 s) mientras la sesión captura, misma secuencia que `/ping` manual, **persistido** en SQLite y exportado como `<run_label>_dl.csv`; muere con la sesión | Vigente |
| D-62 | Re-join por BLE para el gate de clase (D-60) | Comando nuevo `op = 0x03` en `Comando` (Addendum B del contrato BLE): tras un 409 «clase desajustada», la app ordena a la sonda **rehacer el join OTAA** sin apagarla. Solo aplicable en `CONFIG`/`SIN_ENLACE`. Respaldo del botón: apagar y encender | Vigente |
| D-63 | «Marcar finalizada» también para la sonda | El botón, si la sonda sigue `CORRIENDO`/`ESPERANDO_ENLACE`, pregunta y manda el mismo comando BLE de parada que Abortar (`op = 0x02`) **antes** de cerrar la sesión como FINALIZADA — sonda primero, servidor siempre (RF-5, decisión G). Si la sonda ya había terminado sola, no se le manda nada | Vigente |
| D-64 | Corrida VUELO | **VUELO-A**, modo 6, fPort 17, DR0/SF10, solo Clase A: una lectura completa por minuto en **3 paquetes de 11 B** (P1 posición · P2 ambiente/energía · P3 navegación), uno cada 20 s, **55 ráfagas = 165 uplinks**; pings activos; PDR ≥ 50 %. Especificación en `docs/VUELO-ESPEC.md` | Vigente |

---

## 2. Entradas cronológicas

### 2026-07-18 — D-18 · Ubicación del proyecto fuera del repositorio

**Decisión.** El proyecto vive en `C:\dev\PiCARO\pruebas_terreno\`, como carpeta
hermana de la carpeta privada de infraestructura y fuera del árbol de `SWL2001`.

**Alternativas consideradas.**

- *Un ejercicio 12 dentro de `specs/exercises/`.* Descartada: el repositorio es
  público y este trabajo maneja credenciales, UUIDs reales y la IP del servidor.
  Además su ciclo de vida es distinto — un ejercicio se cierra, esta campaña de
  medición evoluciona.
- *Una rama del repositorio.* Descartada por el mismo motivo: una rama pública
  sigue siendo pública.

**Por qué.** La separación física evita el error de publicar por descuido. La
regla ya establecida para la carpeta privada de infraestructura se extiende aquí.

---

### 2026-07-18 — D-01 · Stack LoRaWAN: RadioLib, no LoRaMac-node

**Decisión.** El firmware usa **RadioLib 7.7.1**, componente oficial del registro
de Espressif, con el HAL para ESP-IDF ya escrito en el ejercicio 09.

**Alternativas consideradas.**

- *LoRaMac-node (pedido en la especificación original).* Descartada: **no existe
  un port oficial a ESP-IDF**. Portarlo significa escribir de cero la capa de
  temporizadores, la de radio y la de persistencia, y validar el resultado contra
  la certificación. Semanas de trabajo para llegar a donde ya estamos.
- *LoRa Basics Modem (SWL2001).* Descartada: está orientada al LR1110/SX126x con
  su propio HAL y capa de aplicación; el T-Beam Supreme monta SX1262 y ya funciona
  con RadioLib.

**Por qué.** El ejercicio 09 tiene RadioLib funcionando con HAL propio y drivers
probados de L76K, BME280, AXP2101, OLED y microSD. Reescribir el stack tira todo
eso sin ganar nada medible para el experimento.

**Consecuencia en la API.** Lo que la especificación pedía como
`MibRequestConfirm_t → MIB_ADR = false` se implementa como `node.setADR(false)`;
el data rate fijo, como `node.setDatarate(dr)`; la clase, como
`node.setClass(RADIOLIB_LORAWAN_CLASS_C)`.

---

### 2026-07-18 — D-02, D-03, D-04 · Corrección de la tabla de Data Rates de US915

**Decisión.** Los escenarios usan **DR1 para SF9** y **DR3 para SF7**.

**Qué estaba mal.** La especificación original asignaba SF9 → DR2 y SF7 → DR4.
Ambas son incorrectas en US915:

| Data Rate | US915 | EU868 |
|---|---|---|
| DR0 | SF10 / 125 kHz | SF12 |
| DR1 | **SF9** / 125 kHz | SF11 |
| DR2 | SF8 / 125 kHz | SF10 |
| DR3 | **SF7** / 125 kHz | SF9 |
| DR4 | SF8 / **500 kHz** | SF8 |
| DR5 | — | SF7 |

En US915, DR2 es SF8 y DR4 es SF8 a 500 kHz de ancho de banda, no SF7. Las
equivalencias que la especificación daba para EU868 (SF9 → DR3, SF7 → DR5) sí
eran correctas, lo que sugiere que la tabla de EU868 se trasladó a US915 sin
comprobar.

**Por qué importa.** La banda de trabajo es US915. Con la asignación equivocada,
el escenario "SF9" habría transmitido en SF8 y el escenario "SF7" en SF8 a
500 kHz — un ancho de banda distinto, con sensibilidad y ocupación espectral
distintas. Los resultados no habrían medido lo que se pretendía medir.

**Fuente.** Regional Parameters de la LoRa Alliance; tabla equivalente en la
documentación de The Things Network para US902-928.

---

### 2026-07-18 — D-05 · Escenario del cerro: SF10, no SF7

**Decisión.** El escenario del cerro usa **DR0 / SF10**.

> *Nota posterior (2026-07-19):* esta entrada conserva la cifra de 15 km con la
> que se tomó la decisión. La distancia real medida resultó ser **16,35 km**
> (ver D-20), lo que no altera la decisión pero sí el nombre del escenario, ahora
> **CERRO16**.

**Qué cambió.** La especificación original pedía SF7 para el cerro, justificado
como "máxima optimización de tiempo en el aire a larga distancia". Al preguntar
por el objetivo real, quedó claro que **no se busca comprobar SF7 sino alcanzar
la máxima distancia posible**. Son objetivos opuestos: SF7 es el factor de
propagación con *menor* alcance de los disponibles.

**Alternativas consideradas.**

- *SF12.* Descartada: **no existe para uplink en US915.** La banda solo define
  DR0–DR3 (SF10–SF7) sobre canales de 125 kHz. SF11 y SF12 aparecen únicamente en
  el enlace descendente (DR8–DR13, 500 kHz).
- *SF7 (propuesta original).* Descartada: minimiza el tiempo en el aire a costa
  de la sensibilidad, que es exactamente el recurso que hace falta a 15 km.
- *Barrido SF7→SF10 en la misma corrida.* Descartada para esta campaña: mezcla
  dos preguntas (alcance máximo y umbral por SF) y complica el análisis. Queda
  anotada como posible campaña futura.

**Por qué.** SF10 es el máximo alcance que permite la banda: aproximadamente
**+9 dB de presupuesto de enlace** frente a SF7. A 15 km esa diferencia decide si
el enlace existe.

**Consecuencia.** DR0 impone un límite de **11 bytes de payload de aplicación**
(ver D-09). Es la restricción que reorganizó el formato de datos.

---

### 2026-07-18 — D-09, D-11 · Payload de 11 bytes

**Decisión.** Estructura `packed` de 11 bytes:

```c
typedef struct __attribute__((packed)) {
    int32_t latitude;    // grados × 1e7      (4 bytes)
    int32_t longitude;   // grados × 1e7      (4 bytes)
    int16_t altitude;    // metros            (2 bytes)
    int8_t  temperature; // °C × 2            (1 byte)
} RadiosondaPayload_t;   //                   = 11 bytes
```

**Evolución.** 19 bytes (formato del ejercicio 09) → 12 bytes (propuesta de la
especificación) → **11 bytes** (final).

**Alternativas consideradas.**

- *Mantener los 19 bytes del ejercicio 09.* Atractiva porque no exige tocar el
  servidor: el device profile y el codec ya existen y funcionan. Descartada
  porque **no caben en DR0**, lo que dejaría el techo del experimento en SF9 y
  renunciaría a los +3 dB de SF10 justo en el escenario de máxima distancia.
- *Los 12 bytes de la especificación.* Descartada por un solo byte: DR0 admite un
  máximo de **11 bytes** de payload de aplicación en US915, por el límite de
  *dwell time* de 400 ms. A SF10, 11 bytes ya ocupan unos 371 ms de aire.
- *Dos formatos, uno por escenario.* Descartada: obliga a dos codecs y dos device
  profiles para ahorrar unos milisegundos. Complejidad sin retorno.

**Por qué el recorte cayó en la temperatura.** Pasar de `int16_t` (°C × 100) a
`int8_t` (°C × 2) libera el byte que sobraba. El rango resultante, −64 a
+63,5 °C con paso de 0,5 °C, cubre con holgura el perfil térmico de una
radiosonda; la precisión de centésimas era mayor que la incertidumbre real del
BME280 en campo.

**Endianness.** El ESP32-S3 es little-endian y la estructura se envía en crudo,
así que el codec del servidor debe leer **little-endian**. El codec del ejercicio
09 lee big-endian: son incompatibles y por eso hace falta uno nuevo.

---

### 2026-07-18 — D-10 · Extensión de payload con batería

**Decisión.** Payload de **longitud variable**: 11 bytes siempre, más 3 bytes
opcionales (`batt_mV` `uint16` + `batt_pct` `uint8`) cuando el data rate lo
permite. El codec decodifica según la longitud recibida.

**Contexto.** Al convertir la autonomía en objeto de medida (ver D-07), la
tensión de batería pasó de dato accesorio a variable dependiente.

**Alternativas consideradas.**

- *Batería solo en el registro de microSD.* Sigue siendo la fuente principal para
  el análisis, por frecuencia y por no consumir aire. Pero deja al operador de
  campo sin lectura en vivo durante la corrida.
- *Batería siempre en el payload.* Imposible: en DR0 no caben los 14 bytes.
- *Un segundo mensaje periódico de "housekeeping".* Descartada: duplica tráfico y
  tampoco resuelve el límite de DR0.

**Por qué.** En SF9 y SF7 los límites son 53 y 242 bytes: los 3 bytes extra no
cuestan nada. En SF10 el payload degrada limpiamente a 11 bytes. El operador ve
la batería en el dashboard en dos de los tres escenarios y el registro de microSD
cubre el tercero.

---

### 2026-07-18 — D-07 · Clase A frente a Clase C como variable del experimento

**Decisión.** La clase deja de ser una elección de diseño y pasa a ser
**variable independiente**: cada escenario se ejecuta en Clase A y en Clase C.

**Cómo surgió.** La pregunta inicial fue si Clase C resolvía la imposibilidad de
mantener intervalos de 2 s. La respuesta es **no**: en Clase C el dispositivo
sigue obligado a abrir RX1 después de cada uplink, de modo que la cadencia mínima
no cambia. Lo que sí aporta Clase C es **downlink inmediato**, porque escucha de
forma continua entre ventanas.

**Alternativas consideradas.**

- *Solo Clase A.* Descartada: deja sin medir la latencia de corte, que es
  relevante para un mecanismo de liberación física.
- *Solo Clase C.* Descartada: su coste de consumo quedaría sin cuantificar, y es
  precisamente el dato que interesa.

**Por qué.** El coste de Clase C —receptor permanentemente encendido, del orden
de 5–10 mA continuos frente a microamperios en reposo— se convierte en
**objeto de medida** en lugar de en un problema a evitar. La autonomía no es
crítica en esta campaña, así que puede sacrificarse para cuantificarla.

**Control de validez incorporado.** La clase no afecta al enlace ascendente, así
que el PDR *no debería* cambiar entre A y C dentro del mismo escenario. Si
cambia, el problema está en el método, no en el fenómeno. Es una verificación
gratuita integrada en el diseño.

---

### 2026-07-18 — D-12 · `fPort` como etiqueta de corrida

**Decisión.** El `fPort` de uplink codifica escenario y clase:

| `fPort` | Escenario | Clase |
|---|---|---|
| 11 | 1 — URBANO (móvil en vehículo) | A |
| 12 | 1 — URBANO (móvil en vehículo) | C |
| 13 | 2 — TERRAZA (piso 5, exterior) | A |
| 14 | 2 — TERRAZA (piso 5, exterior) | C |
| 15 | 3 — CERRO16 (LoS 16,35 km) | A |
| 16 | 3 — CERRO16 (LoS 16,35 km) | C |

**Alternativas consideradas.**

- *Un campo `run_id` dentro del payload.* Descartada: en DR0 no sobra ni un byte.
- *Anotar los tiempos de inicio y fin de cada corrida a mano y cruzar por marca
  temporal.* Descartada por frágil: depende de la disciplina del operador y falla
  en los solapes.

**Por qué.** El `fPort` viaja fuera del payload, ChirpStack lo registra en cada
uplink y el dashboard ya lo almacena en la columna `f_port`. Cada paquete queda
autoetiquetado a **coste cero de tiempo en el aire**, y el análisis separa las
corridas sin intervención manual.

---

### 2026-07-18 — D-13, D-14 · Separación del comando de corte y el ping de latencia

**Decisión.** Dos comandos de downlink distintos:

| `fPort` | Payload | Efecto |
|---|---|---|
| 99 | byte `0xA5` | **Corte real.** Activa el GPIO de liberación |
| 98 | cualquier byte | **Ping de latencia.** Enciende el LED y registra la marca de tiempo |

Cualquier otro valor en el `fPort` 99 se ignora y se registra como intento
rechazado.

**Alternativas consideradas.**

- *Un único comando de un byte en cualquier puerto (especificación original).*
  Descartada por dos motivos. Primero, seguridad: un mecanismo de liberación
  física no puede depender de que llegue "un byte cualquiera"; un mensaje
  espurio o un error de encaminamiento dispararía el corte. Segundo, método:
  medir la latencia de downlink exige repetir el comando decenas de veces, y con
  un único comando eso significa cortar la sonda en cada medición.

**Por qué.** El byte mágico convierte un disparo accidental en un evento
improbable sin gastar bytes adicionales. El puerto separado permite caracterizar
la latencia de Clase A frente a Clase C con la estadística necesaria y sin
consumir el mecanismo.

---

### 2026-07-18 — D-15 · Sensores reales

**Decisión.** BME280 por I²C para temperatura y presión; L76K por UART para
posición. Sin lecturas simuladas.

**Alternativa considerada.** La especificación original admitía "sensor de
temperatura simulado o real vía I2C/ADC con GPIOs genéricos". Descartada: la
placa T-Beam Supreme ya monta el BME280 y el ejercicio 09 tiene su driver
probado, así que el sensor simulado añadía una ruta de código que nadie usaría en
campo y que habría que mantener.

---

### 2026-07-18 — D-16 · DevEUI nuevo

**Decisión.** Se registra un DevEUI nuevo para la sonda de pruebas de terreno.

**Alternativa considerada.** Reutilizar `0011223344550001`, ya migrado al
servidor en la nube. Descartada por dos razones: mezclaría las medidas de esta
campaña con el histórico del ejercicio 09 en la misma serie de datos, y —más
concluyente— obligaría a cambiarle el device profile, porque el payload nuevo es
incompatible con el codec de 19 bytes big-endian. Eso rompería la configuración
del ejercicio 09 para ese dispositivo.

---

### 2026-07-19 — D-17 · Documentación con datos reales

**Decisión.** La bitácora, el protocolo experimental y la guía de laboratorio
llevan datos reales: dominio, UUIDs, credenciales e IP.

**Alternativa considerada.** Escribirlos con marcadores desde el principio, como
se hizo con el ejercicio 11 del repositorio público. Descartada porque el
destinatario es el equipo interno y los marcadores obligarían a consultar otro
documento en cada paso, justo durante el trabajo de campo.

**Condición.** Si en el futuro alguno de estos documentos se publica, se deriva
una versión saneada. Reescribir para sanear a posteriori es más arriesgado que
partir de marcadores, así que la decisión se revisa antes de cualquier
publicación, no después.

---

### 2026-07-19 — D-20, D-32 · Emplazamientos reales y distancia medida

**Decisión.** Se fijan las coordenadas definitivas de los tres emplazamientos y se
corrige la distancia al cerro.

| Punto | Coordenadas | Terreno | Antena |
|---|---|---|---|
| **Gateway** | `21.92, -102.27` | 2000 m snm *(por verificar)* | 15,5 m sobre el suelo |
| **Cerro** | `21.8741637679742, -102.42482836119612` | 2400 m snm | ~1,5 m (sonda en mano/trípode) |
| **Terraza** | `21.93, -102.30` | < 1900 m snm | ~15 m sobre el suelo |

Los 15,5 m del gateway se descomponen en azotea de casa de dos plantas (8 m),
base del tinaco (1,5 m) y mástil (6 m). La antena es una **Raigen de fibra de
vidrio, 5,8 dBi**, con 90 cm de coaxial (~0,3 dB, despreciable).

**Distancia gateway↔cerro: 16,35 km** por haversine, no los 15 estimados. El
escenario se renombra a **CERRO16** para que la documentación no arrastre una
cifra falsa. Distancia gateway↔terraza: **2,74 km**, rumbo **118° (ESE)** desde el
edificio.

**Advertencia sobre la altitud del gateway.** Los 2000 m proceden de leer la curva
de nivel más cercana en Google Maps, no de una medición. Resulta sospechoso que el
gateway esté 100 m por encima de un edificio de la ciudad situado a 2,74 km
(< 1900 m), estando montado sobre una casa y no sobre un promontorio. **Queda
pendiente de verificar**; si el valor real fuese ~1890 m, toda la tabla de despeje
de Fresnel se desplaza y el margen cambia de forma apreciable.

---

### 2026-07-19 — D-19 · Escenario 2: terraza del piso 5, no ventana del piso 7

**Decisión.** El escenario 2 se ejecuta desde la **terraza del piso 5**, al aire
libre.

**Alternativas consideradas.**

- *Piso 7, detrás de una ventana.* Descartada. El vidrio introduce una atenuación
  de entre **3 dB (vidrio común) y 25 dB (bajo-emisivo o metalizado)** que no se
  conoce ni se controla. No rompería el enlace —el margen a 2,74 km es de 52,1 dB
  en SF7, y aguanta incluso el peor caso— pero **contaminaría la comparación de
  RSSI entre escenarios**: sería imposible separar cuánto de la diferencia es
  propagación y cuánto es cristal.
- *Azotea del edificio (planteamiento original).* No disponible.

**Por qué.** La terraza cuesta unos 6 m de altura y elimina una variable
desconocida. En el cómputo del enlace esos 6 m son irrelevantes: la línea de vista
en el punto medio baja de 1968 m a 1965 m, y el margen SF7 no cambia. Además
recupera la condición de línea de vista limpia que pedía la especificación
original.

**Verificación en sitio.** El gateway queda al **ESE (118°)**. Hay que confirmar
que la terraza da a ese lado y que ni el pretil ni los pisos 6 y 7 se interponen;
una terraza orientada al norte u oeste sería peor que la ventana.

---

### 2026-07-19 — Presupuesto de enlace y despeje de Fresnel

**Hallazgo principal.** El enlace de 16,35 km **no está limitado por el
presupuesto de enlace, sino por el despeje del terreno**.

| Magnitud | Valor |
|---|---|
| FSPL a 16,35 km / 915 MHz | 115,9 dB |
| Potencia recibida estimada | −88,4 dBm |
| **Margen con SF10 (DR0)** | **43,6 dB** |
| Margen con SF7 (DR3) | 36,6 dB |

Con línea de vista limpia, ese enlace funcionaría **incluso en SF7**. SF10 se
mantiene no porque haga falta para alcanzar la distancia, sino como **margen
frente a obstrucción parcial y desvanecimiento**. Conviene tenerlo claro al
redactar la memoria: el escenario 3 pone a prueba la geometría del trayecto, no la
sensibilidad del factor de propagación.

**Primera zona de Fresnel.** Radio de 36,6 m en el punto medio (8,2 km), despeje
recomendado al 60 % de 22,0 m, más 3,9 m de abombamiento terrestre (k = 4/3).

Terreno máximo admisible a lo largo del trayecto:

| km desde el gateway | Terreno máx. | | km desde el gateway | Terreno máx. |
|---|---|---|---|---|
| 0,5 | 2019 m | | 8,2 *(punto medio)* | **2183 m** |
| 1 | 2027 m | | 10 | 2226 m |
| 2 | 2046 m | | 12 | 2276 m |
| 4 | 2088 m | | 14 | 2329 m |
| 6 | 2132 m | | | |

Para el escenario 2 (2,74 km): Fresnel de 15,0 m en el punto medio, despeje al
60 % de 9,0 m. Con el terreno urbano en torno a 1900 m y la línea de vista a
1965 m, haría falta un edificio de unas 18 plantas justo en medio para obstruir.

---

### 2026-07-19 — D-21, D-22 · Selección por botón y OLED con apagado automático

**Decisión.** Un **único firmware** cubre las seis corridas. La selección se hace
con el botón físico y persiste en NVS: pulsación larga (> 2 s) cicla el escenario,
doble pulsación alterna la clase. El OLED muestra la corrida activa y **se apaga
solo a los 30 s** sin pulsación.

**Alternativas consideradas.**

- *`#define` y recompilar entre corridas.* Descartada por logística: obligaría a
  subir al cerro con portátil y toolchain para cambiar de clase A a C. Es
  exactamente el escenario donde menos apetece depender de un ordenador.
- *Comando por consola serie.* Descartada: no necesita toolchain pero sigue
  exigiendo cable y portátil.
- *OLED siempre encendido.* **Descartada por interferir con la medición.** Un OLED
  activo consume del orden de **20–30 mA**, mientras que la diferencia de consumo
  entre Clase A y Clase C que se quiere medir es de **5–10 mA**. La pantalla
  enmascararía por completo el efecto bajo estudio.

**Por qué el apagado automático.** Con la pantalla encendida solo mientras se
consulta, se conserva la utilidad en campo sin comprometer H3. Es especialmente
importante porque la cobertura de datos en campo no está garantizada: el OLED es la
forma de verificar in situ que la sonda transmite y tiene fix.

---

### 2026-07-19 — D-23, D-24 · Duración por uplinks y número de réplicas

**Decisión.** Cada corrida termina al alcanzar **600 uplinks**, no al cumplir un
tiempo. Una réplica por celda: **6 corridas**.

**Duraciones resultantes:** escenario 1, 50 min; escenario 2, 25 min; escenario 3,
30 min.

**Alternativa considerada.** *Tiempo fijo de 30 min por corrida.* Descartada
porque los intervalos difieren entre escenarios: 30 minutos darían 360, 720 y 600
uplinks respectivamente. El escenario 1 quedaría con un tercio menos de muestras
que el 2, y el PDR de ambos no sería directamente comparable por tener distinta
precisión estadística.

**Por qué 600.** Con PDR ≈ 0,9 el error estándar es √(0,9·0,1/600) ≈ 1,2 puntos
porcentuales, suficiente para resolver las diferencias que interesan.

---

### 2026-07-19 — D-25, D-26 · Criterios de aceptación

**Decisión.**

| Criterio | Valor |
|---|---|
| PDR de «cobertura útil» (escenarios 1 y 2) | **≥ 80 %** |
| PDR de éxito del enlace a 16 km | **≥ 50 %** |
| Control de validez A vs C | χ² con α = 0,05 **y además** diferencia > 5 pp |

**Por qué el criterio de control exige las dos condiciones.** Se planteó usar solo
la prueba de χ². El problema es el tamaño de muestra: con *n* = 600 por corrida,
un χ² detecta como estadísticamente significativa una diferencia de **2–3 puntos
porcentuales**, que no tiene ninguna relevancia práctica. Aplicado en solitario,
llevaría a descartar corridas perfectamente válidas.

Exigiendo significancia estadística **y** un tamaño de efecto mínimo de 5 puntos,
se separa «hay señal en los datos» de «la diferencia importa». Ambos valores se
reportan.

**Por qué el cerro tiene un umbral distinto.** A 16 km, en el límite del
presupuesto útil, recibir la mitad de los paquetes demuestra que el enlace existe
y es explotable con redundancia. Exigir el mismo 80 % que en los otros escenarios
haría fallar el criterio aunque el enlace funcionase.

---

### 2026-07-19 — D-27 a D-33 · Decisiones de procedimiento y firmware

| # | Decisión | Motivo |
|---|---|---|
| D-27 | Reintento de join con **backoff indefinido**, registrando el hueco en el log | Una desconexión pasajera no debe costar una corrida entera, y menos en el cerro |
| D-28 | Escenario 1 **en vehículo a 30–40 km/h** | A 5 s de intervalo da un punto cada ~50 m: cubre área suficiente en los 50 min de corrida. A pie solo se recorrerían ~4 km |
| D-29 | Corrida cortada: **marcar parcial y repetir** | Se conserva el dato, pero solo las corridas completas entran en el análisis principal |
| D-30 | Autonomía en Clase C: **sin umbral**, solo medir y reportar | La decisión de si compensa depende de la misión concreta, no de esta campaña |
| D-31 | Corte **desarmado** en las 6 corridas: solo GPIO + LED | Permite las ≥ 30 medidas de latencia por corrida sin accionar un mecanismo irreversible |
| D-32 | **Registrar los uplinks fallidos** en el log de microSD | Sin ellos el denominador del PDR está mal |
| D-33 | **Modo banco sin fix de GPS** | Permite probar en interiores; envía coordenadas a cero y marca `gps_fix = false` |

---

### 2026-07-19 — Logística de la campaña

**Equipo.** Dos personas: operador y asistente. El **asistente lleva el registro
desde el móvil**, con `campo/hoja-de-campo.html` (funciona sin conexión).

**Fechas previstas:** 14 al 16 de agosto de 2026.

**Alimentación:** batería.

**Cobertura de datos en el cerro: no hay.** Consecuencia operativa de primer
orden: no se podrá verificar en vivo desde el dashboard si los uplinks están
llegando. El **OLED** pasa a ser la única verificación en campo, y el **log de
microSD** el único registro hasta el regreso. De ahí que la hoja de campo digital
tenga que funcionar en modo desconectado.

---

## 3. Decisiones revertidas

### R-01 · `rx1_delay` del servidor: 5 s → 1 s ~~(vigente)~~ **ANULADA**

> 🔴 **Esta reversión fue un error y quedó a su vez revertida el mismo día.**
> Provocó el incidente **I-01**: rompió el ejercicio 09. Ver **R-03**. Se conserva
> aquí el razonamiento original porque entender **por qué pareció razonable** es
> justamente la lección.

**Estado anterior.** 5 s, configurado durante el despliegue del ChirpStack en
el servidor en la nube.

**Estado en su momento.** 1 s. **Estado actual: 5 s** (ver R-03).

**Por qué se puso en 5 s.** Como margen conservador frente al *jitter* de la ruta
México↔servidor en la nube, en un momento en el que no había medidas de latencia. La
ventana RX1 debe abrirse después de que el downlink haya podido viajar de ida y
vuelta; un margen amplio protege contra picos de latencia.

**Por qué se revierte.** Dos motivos, uno de evidencia y otro de bloqueo.

1. **Evidencia.** El RTT medido entre el gateway y el servidor es de unos
   **180 ms**. Un `rx1_delay` de 1 s deja un margen de aproximadamente 5×, que es
   holgado. Los 5 s eran prudencia sin datos; ahora hay datos.
2. **Bloqueo.** En Clase A el dispositivo no puede transmitir hasta cerrar RX1 y
   RX2. Con `rx1_delay` = 5 s, el ciclo mínimo queda en
   `airtime + 5 s + 1 s + margen` ≈ **6,5 s**, lo que hace **imposibles los tres
   intervalos del experimento** (5 s, 2,5 s y 3 s), no solo el más corto.

**Lección.** El valor conservador era razonable cuando se eligió y dejó de serlo
al llegar los datos. Conviene revisar los márgenes puestos "por si acaso" en
cuanto exista medición.

**Aviso operativo (corregido).** El `rx1_delay` se comunica al dispositivo en el
*JoinAccept*. La redacción original de este aviso decía «no lo subas a 5 s de
nuevo sin recalcular los intervalos», es decir, daba por sentado que el valor
correcto era 1 s y que el experimento mandaba sobre el servidor. **Era al revés:**
el valor del servidor es un dato de entrada y los intervalos se derivan de él.

---

### R-02 · Escenario 2: intervalo de 2 s → 2,5 s

**Estado anterior.** 2 s, según la especificación original.

**Estado actual.** **2,5 s.**

**Por qué.** En Clase A, tras cada uplink el dispositivo debe atender RX1 (a
`rx1_delay`) y RX2 (un segundo después). Con `rx1_delay` = 1 s, RX2 cierra
transcurridos algo más de 2 s desde el fin de la transmisión. Un periodo de 2 s
solapa con sus propias ventanas de recepción: el stack retrasa la transmisión por
su cuenta y el intervalo real deja de ser el nominal.

Fijar 2,5 s hace que el intervalo **programado coincida con el real**, que es
condición para que la cadencia sea un parámetro controlado del experimento y no
una consecuencia del comportamiento interno del stack.

---

### R-03 · `rx1_delay`: 1 s → **5 s** (restauración)

**Estado actual.** **5 s** en `region_us915_1.toml` y `region_eu868.toml`.

**Por qué se restaura.** Porque bajarlo a 1 s rompió el ejercicio 09 (ver
**I-01**). Al devolverlo a 5 s, el mismo firmware y el mismo hardware volvieron a
unirse al primer intento:

```
I (6285) lorawan:  JOIN NUEVO por aire (JoinAccept recibido). Enlace REAL. DR=3
I (11463) lorawan: Uplink confirmado OK + downlink/ACK en Rx1 (ENLACE CONFIRMADO)
```

**Este valor pasa a ser un dato de entrada del experimento, no un parámetro
ajustable.** Todo lo que dependa de él —intervalos, duración de corrida— se
recalcula a partir de él, nunca al contrario.

---

### R-04 · Consecuencias de R-03: intervalos, duración y DevEUI

Restaurar `rx1_delay` = 5 s obliga a rehacer tres decisiones que se habían tomado
asumiendo 1 s.

**Intervalos: 5 / 2,5 / 3 s → 7 / 7 / 8 s.**

En Clase A no se transmite hasta cerrar RX1 y RX2, así que el ciclo mínimo es
`airtime + rx1_delay + 1 s + margen`. Con 5 s eso da **≈ 6,5 s**, lo que hacía
**físicamente imposibles** los tres intervalos anteriores —no solo el más corto—.
Los nuevos valores no son una elección de diseño: son el mínimo viable más un
margen.

**Duración: 600 → 300 uplinks por corrida.**

A 7–8 s de intervalo, 600 uplinks son 70–80 min por corrida y unas **7 horas de
campo** para las seis. Con 300 el error estándar del PDR sube de ~1,2 a ~1,7
puntos porcentuales —√(0,9·0,1/300)—, que sigue siendo suficiente para resolver
las diferencias que interesan. La alternativa era una jornada de campo inviable.

**DevEUI: nuevo → reutilizar `0011223344550001`.**

D-16 justificaba un DevEUI nuevo porque el payload de 11 bytes es incompatible con
el codec de 19 bytes del ejercicio 09, y cambiar el perfil del device habría roto
el ej.09. La solución correcta apareció al replantear el problema: **dos device
profiles y conmutar el del device según lo que se ejecute**. Es aditivo, no
duplica dispositivos y no rompe nada.

*Alternativa descartada:* mantener el payload de 19 bytes para reutilizar el
perfil del ej.09 tal cual. Se descartó porque el objetivo declarado del escenario
3 es **demostrar el alcance máximo**, y eso exige DR0/SF10, que solo admite 11
bytes. El coste de renunciar a SF10 habrían sido −3 dB justo en el escenario cuyo
propósito es el alcance —aunque el margen a SF9 ya fuera de 40 dB—.

---

## 4. Cuestiones abiertas

| # | Cuestión | Estado |
|---|---|---|
| A-01 | Altura y ganancia de antena del gateway | ✅ **Cerrada 2026-07-19** — 15,5 m sobre el suelo (8 + 1,5 + 6); Raigen de fibra de vidrio, 5,8 dBi, 90 cm de coaxial |
| A-02 | Número de réplicas por corrida y duración mínima | ✅ **Cerrada 2026-07-19** — 1 réplica por celda (6 corridas); **300** uplinks por corrida (D-23, D-24; antes 600, ver R-04) |
| A-03 | Despeje de la primera zona de Fresnel en el trayecto al cerro | ✅ **Cerrada 2026-08-29** — perfil SRTM 30 m contrastado punto a punto: 60 % de Fresnel + abombamiento despejado en todo el trayecto; margen mínimo +23,1 m a 340 m del gateway. Ver entrada 2026-08-29 y `analisis/perfil_elevacion.csv` |
| A-04 | Criterio de aceptación del PDR por escenario | ✅ **Cerrada 2026-07-19** — ≥ 80 % (esc. 1 y 2), ≥ 50 % (cerro); control A/C por χ² **y** Δ > 5 pp (D-25, D-26) |
| A-05 | Altitud real del terreno del gateway | ✅ **Cerrada 2026-08-29** — **1914 msnm** medidos en sitio (el SRTM devuelve el mismo valor); los 2000 m de la curva de nivel estaban inflados 86 m. Antena a 1929,5 msnm |
| A-06 | Conmutación de device profile entre ej.09 y experimento | ✅ **Cerrada 2026-08-29** — probada de extremo a extremo: en las cuatro pruebas de banco y en las corridas de la Serie 1 la app conmuta el perfil en cada arranque, y el gate de clase (D-60) lo verifica contra la clase efectiva de ChirpStack antes de dejar abrir la sesión. `servidor/perfil.py` sigue disponible como vía manual de respaldo (ver I-01, D-35, D-60) |
| A-07 | Dashboard/app de campo para operar la campaña desde el móvil | 🟢 **Operativa y probada en campo (2026-07-19)** — `https://campo.pi-caro.org`; primera corrida real capturada de extremo a extremo (URBANO-A-2, 42 rx). Añadidos replay y borrado de sesiones (contrato v1.2, 34 tests). Pendiente: las corridas de campo en sí (terraza, cerro; Clase C / H4) |
| A-08 | Centinela de batería `0xFF` saturado a 100 % en el payload | ✅ **Cerrada 2026-07-19** — payload manda `0xFF`=desconocido (no 100), `decoder.js` lo traduce a null, el OLED muestra `Bat --`. Firmware flasheado y decoder desplegado a los dos perfiles de terreno |
| A-09 | ~~Sector ciego del gateway hacia el oeste~~ → **Dispersión del RSSI en entorno urbano** | 🟡 **Reformulada y NO bloqueante (2026-08-29, tarde)** — con el cruce completo, las cuatro pruebas de banco dan **PDR 96,7–100 %** incluida la del punto de −101,4 dBm: no hay sector ciego, hay *shadowing* urbano del punto de medida. El tinaco está 1 m **por debajo** de la antena y no obstruye (verificado en sitio). Extrapolando a 15,27 km con n=2, el cerro sale **viable** (margen SF10 de +17 a +47 dB). Ver [`docs/PRUEBA-RF-BANCO.md`](docs/PRUEBA-RF-BANCO.md) §9 |
| A-10 | El `run_id` de la sonda y el `run_label` del servidor pueden divergir | 🟡 **Abierta (2026-08-29)** — en las pruebas de banco la sonda escribió `20260829-URBANO-A`, `-A-2`, `-A-3` mientras el servidor abría `-A-2`, `-A-3`, `-A-4`: cada uno numera sus intentos por su cuenta y el servidor ya había gastado el nombre base. `cruzar.py` empareja **por nombre de fichero**, así que el cruce sale mal en silencio si no se corrige a mano. Se emparejó por ventana temporal. Falta decidir el arreglo (que la app fije el `run_id` de la sonda, o cruzar por tiempo y no por nombre) |
| A-11 | JoinRequest con **MIC inválido** tras un re-join en el cerro: la Clase C no se pudo medir | 🟢 **Corregida en firmware (2026-09-28), pendiente de probar el re-join por BLE con la app** — causa en RadioLib 7.7.1: `processJoinAccept()` fija `rev` antes de verificar el MIC. Remedio en `lorawan.cpp`: tras cada join fallido y en cada re-join se **reconstruye el nodo** conservando solo los nonces (`rearmar_nodo`). Verificado en banco con `PICARO_TEST_REV_CORRUPTO=1`: ChirpStack registró `Invalid MIC` (el síntoma del cerro) y el intento siguiente unió. Ver entrada 2026-09-28 |
| A-12 | Pérdidas concentradas en **905,3 MHz** en CERRO16-A | 🟡 **Abierta (2026-09-27)** — 19–20 de las 24 pérdidas en ese canal (PDR 47 % frente a ~98,5 % en los otros siete). No aparece en las 11 corridas anteriores y cesa a las ~14:36: interferente transitorio. Pendiente: barrido de espectro en el gateway |
| A-13 | **ITPA-IOT-GW00 en línea pero sin recepción** | 🔴 **Abierta (2026-09-28)** — envía estadísticas cada 30 s, pero **0 paquetes recibidos al día** del 20 al 28 de septiembre, salvo 16 el 27 (8 del T-Beam en el cerro, a −117 dBm / −18 dB). El SenseCap recibe 7–9 mil al día. Revisar antena, conector, coaxial y plan de canales. Mientras tanto, la campaña depende de un solo gateway |

### A-03 — cómo cerrarla *(resuelta el 2026-08-29 con el perfil SRTM; se conserva el planteamiento)*

Trazar en Google Earth el perfil de elevación entre `21.92,
-102.27` (gateway) y `21.8741637679742, -102.42482836119612` (cerro),
y contrastarlo con la tabla de terreno máximo admisible de la entrada del
2026-07-19. Si en algún punto el terreno la supera, ahí está la obstrucción.

Es la única cuestión que puede invalidar la hipótesis H5 antes de salir a campo, y
se resuelve desde el escritorio en diez minutos.

### A-05 — por qué importa *(resuelta el 2026-08-29: 1914 msnm; la intuición de los ~110 m de más era correcta, eran 86 m)*

Si la altitud real del gateway no fuese 2000 m sino ~1890 m, toda la tabla de
terreno máximo se desplaza unos 110 m hacia abajo y el despeje disponible se
reduce en la misma proporción. A-03 no puede cerrarse de forma fiable sin resolver
antes A-05.

---

## Entrada 2026-07-19 (tarde) — H3 sale de la campaña de campo

**Decisión:** la hipótesis de autonomía (Clase A vs C) se mide en **banco**, no
en las corridas de campo.

**Motivo:** el AXP2101 de la placa no mide corriente de batería, solo tensión y
porcentaje. Deducir la autonomía de la pendiente de descarga exige que la caída
de tensión supere el ruido, y en 30 minutos la diferencia entre clases es de
~1,2 mV frente a 5–20 mV de ruido bajo los pulsos de TX. Habría producido una
cifra sin contenido.

**Alternativas descartadas:**
- *Alargar las corridas de campo a 20 h* — inviable logísticamente y
  contaminaría las medidas de cobertura con cambios de propagación.
- *Reportar la cifra igualmente con una advertencia* — un número con apariencia
  de medida acaba citado sin su advertencia.

**Cómo se mide ahora:** medidor de corriente USB en línea (directo, minutos) y,
si se quiere una curva real, ensayo de descarga de ≥ 20 h por clase.

**Sin efecto sobre** H1, H2, H4 ni H5: las 6 corridas siguen igual.

---

## Entrada 2026-07-19 (tarde) — Sí hay cobertura en el Cerro del Muerto

**Hecho verificado en sitio:** en la cima hay cobertura de datos móviles.

**Consecuencia:** se puede consultar el dashboard en vivo desde el cerro y
abortar una corrida si algo va mal, en vez de descubrirlo al volver. **No se
depende de ello**: la hoja de campo sigue siendo offline y `servidor/pinger.py`
lanza los pings desde el servidor, así que el procedimiento funciona igual si la
cobertura falla.

---

## Entrada 2026-07-19 (tarde) — No hay actuador de corte: solo se mide la latencia

**Hecho:** la T-Beam Supreme va montada en una placa soldada y no se le va a
anadir hardware. No existe ni existira durante esta campana un mecanismo fisico
de liberacion.

**Decision:** el firmware **no conmuta ningun GPIO** (`CORTE_HABILITAR_GPIO = 0`
en `board_pins.h`). El corte y el ping quedan como eventos registrados con su
marca de tiempo.

**Motivo:** conmutar un pin "libre" sin el esquematico de la placa es un riesgo
gratuito — podria estar cableado a algo. Los GPIO 15 y 16 elegidos inicialmente
solo estaban verificados contra los perifericos conocidos, no contra el
esquematico. Y sobre todo: **lo que mide el experimento nunca fue el pin, sino
el instante de llegada del comando**. El GPIO era la forma de hacerlo visible.

**Que sustituye a la senal fisica:** el OLED muestra en su ultima linea el tipo
de downlink, el **numero de secuencia** que puso el servidor y los segundos
transcurridos (`DL ping #12  3s`). Sin LED ni actuador, esa linea es la unica
confirmacion visual en campo, y el numero de secuencia permite cotejar al
momento contra el log del pinger para detectar un ping que no llego.

**Por que se conserva el concepto de corte:** es el caso de uso que justifica
medir latencia de downlink —una orden de liberacion que llega tarde no sirve— y
en el futuro podria montarse hardware real. Basta poner el flag a 1 y verificar
los pines contra la placa.


---

## INCIDENTE I-01 — El cambio de rx1_delay rompió el ejercicio 09

**Fecha:** 2026-07-19. **Impacto:** un día de trabajo perdido en el ejercicio 09,
más varias horas de diagnóstico dirigido a causas equivocadas.

### Qué pasó

Para que cupieran los intervalos de uplink del experimento (5 / 2,5 / 3 s), se
cambió `rx1_delay` de **5 s a 1 s** en `region_us915_1.toml` y `region_eu868.toml`
del ChirpStack compartido.

Ese ajuste vive en la configuración de **región**, no en el device profile: es
**global** y afecta a todos los devices del servidor. El ejercicio 09, que llevaba
un día funcionando, **dejó de completar el join**.

El fallo no se detectó hasta horas después. Durante ese tiempo el diagnóstico
persiguió síntomas equivocados en el firmware nuevo: el OLED en negro, las
direcciones I²C, la velocidad del bus, el orden de arranque de los periféricos.
Todo ello mientras la causa real estaba en un cambio hecho al servidor.

### Cómo se confirmó

Al restaurar `rx1_delay = 5 s` y volver a flashear el firmware del ejercicio 09
—sin tocar nada más— el enlace se restableció al primer intento:

```
I (6285) lorawan:  JOIN NUEVO por aire (JoinAccept recibido). Enlace REAL. DR=3
I (11463) lorawan: Uplink confirmado OK + downlink/ACK en Rx1 (ENLACE CONFIRMADO)
I (6306) picaro:   perifericos: SD=1 OLED=1 BME280=1 joined=1
```

Mismo firmware, mismo hardware, mismo servidor salvo ese parámetro. La causa
queda establecida sin ambigüedad.

### El agravante metodológico

Durante el diagnóstico se argumentó que `rx1_delay` **no podía** ser la causa,
porque el JoinAccept no usa ese temporizador sino `join_accept_delay` (5 s,
constante fijada por el estándar y que nadie había tocado).

El razonamiento era plausible y **falso en la práctica**. Y sirvió para descartar
prematuramente la única hipótesis que apuntaba al cambio propio, prolongando la
búsqueda por el lado equivocado.

> **Lección.** Cuando una hipótesis exculpa al cambio que uno mismo ha hecho, hay
> que someterla a prueba **antes** de creerla, no después de agotar las demás. El
> coste de comprobarla —restaurar el valor y reflashear— eran diez minutos.

### Por qué ocurrió

El fallo de fondo no fue técnico sino **de criterio sobre el alcance de la
decisión**: se asumió que un ajuste «pequeño y razonable» en infraestructura
compartida entraba dentro del margen propio. No entra. Un servidor en producción
que da servicio a otro proyecto en marcha —y a los 15 equipos del curso— no se
modifica para acomodar un experimento nuevo.

Había alternativa, y era la evidente: **adaptar el experimento**. Los intervalos
se recalculan a partir de `rx1_delay` en un minuto (ver R-04). Se optó por lo
contrario.

### Regla que queda establecida

**La configuración global del servidor no se modifica por ningún proyecto.**

| Acción | ¿Permitida? |
|---|---|
| Crear un device profile nuevo | ✅ Aditivo |
| Dar de alta un device | ✅ Aditivo |
| Añadir un usuario MQTT | ✅ Aditivo |
| Cambiar el perfil asignado a un device | ✅ Reversible y acotado |
| Editar `region_*.toml` o `chirpstack.toml` | ⛔ **No** |
| Cambiar temporizadores, `rx1_delay`, ajustes de región | ⛔ **No** |
| Modificar perfiles o devices de otro proyecto | ⛔ **No** |

Si el experimento no cabe con la configuración existente: **se para, se explica el
conflicto, se propone la alternativa desde el lado del proyecto y se espera
respuesta.** Ante la duda, preguntar antes de escribir en el servidor.

### Reparación

| Acción | Estado |
|---|---|
| `rx1_delay` restaurado a 5 s en ambas regiones | ✅ |
| Ejercicio 09 reflasheado y verificado (join + uplink + downlink) | ✅ |
| Device profile y device creados para el experimento | ✅ Eliminados |
| Servidor devuelto a su estado previo | ✅ |

---

## 2026-07-19 (noche) — D-34, D-35 · Rediseño sobre lo ya probado

Tras I-01, el experimento se rediseña con dos principios: **no tocar el servidor**
y **no reinventar lo que ya funciona**.

### D-34 · El firmware parte del ejercicio 09

**Decisión.** La base es el firmware del ejercicio 09, que está probado en esta
misma placa: join, uplink, downlink, OLED, microSD, sensores. Se le añaden **tres
cosas y ninguna más**:

1. Selector de escenario (DR, intervalo, clase) por botón, persistente en NVS
2. `fPort` por corrida (11–16) en lugar del fijo 10
3. Registro CSV por corrida en la microSD, con `run_id`

**Alternativa descartada.** *Continuar con el firmware escrito desde cero para
este experimento.* Descartada tras I-01: durante el diagnóstico consumió horas
persiguiendo fallos propios —OLED, I²C, orden de arranque— que el firmware del
ejercicio 09 no tiene porque ya están resueltos. Queda en el historial de git por
si alguna pieza resulta útil, pero no es la base.

**Por qué.** Cada línea que no se reescribe es una línea que no hay que volver a
depurar en campo. El firmware del ej.09 tiene un día de funcionamiento verificado
detrás; el nuevo, ninguno.

### D-35 · Dos device profiles sobre el device existente

**Decisión.** El device sigue siendo `0011223344550001`. Se crean **dos device
profiles nuevos** —uno Clase A y otro Clase C— y se conmuta el del device según lo
que se vaya a ejecutar.

**Alternativas consideradas.**

- *Un DevEUI nuevo para el experimento (D-16 original).* Descartada: duplica
  dispositivos para resolver algo que se resuelve conmutando un perfil.
- *Modificar el perfil del ejercicio 09 para añadirle Clase C.* Descartada: es
  exactamente el tipo de modificación sobre lo que ya funciona que causó I-01.

**Por qué.** Crear perfiles es **aditivo** y conmutar el de un device es
**reversible y acotado**: no altera nada de lo existente y se deshace en un
comando. Es la operación de menor riesgo que resuelve el problema.

**Riesgo operativo asociado (ver A-06).** Si se ejecuta el ejercicio 09 con el
perfil del experimento activo —o al revés— el codec no coincidirá con el payload
y el campo `object` saldrá mal sin que nada falle de forma visible. **El
procedimiento de conmutación debe escribirse y probarse antes de la campaña.**

---

## 2026-07-19 — Cierre de sesion: firmware validado en placa

### Estado al cerrar

Firmware de terreno **construido sobre el ejercicio 09 y validado en hardware**.
Reutiliza 29 de sus 35 ficheros byte-identicos. Binario de 422 KB, sin avisos.

Verificado **en la placa**, no supuesto:

| Comprobacion | Resultado |
|---|---|
| Join OTAA | JoinAccept recibido |
| Uplinks | Llegan y se decodifican con su etiqueta de corrida (fPort -> escenario/clase) |
| Intervalo | **8,1 s** medidos entre transmisiones |
| Downlink | Recibido y mostrado en el OLED (`DL ping #12`, con segundos vivos) |
| RSSI / SNR | -14 dBm / 9 dB (sonda junto al gateway) |
| OLED, microSD, sensores, boton | Inicializan correctamente |

Servidor: **solo aditivo**. Dos device profiles nuevos (`Radiosonda-Terreno-ClaseA`
y `-ClaseC`) sobre el device `0011223344550001` que ya existia. La configuracion
global sigue como la dejo el ejercicio 09. Conmutacion con `servidor/perfil.py`.

Perfil activo al cerrar: **`Radiosonda-Terreno-ClaseA`**. Si se quiere volver a
ejecutar el ejercicio 09 hay que devolverlo con `python perfil.py ej09`, o su
payload de 19 bytes se decodificara con el codec de 11/14 y saldra mal **sin dar
error visible**.

### Dos correcciones de esta sesion

**El periodo se contaba mal.** El bucle esperaba el intervalo completo DESPUES de
cerrar las ventanas RX, y el ciclo ya consume ~6,5 s: el periodo real era de
13,5 s en vez de 7. Con 300 uplinks eso son 67 min por corrida y casi 7 h de
campo — justo lo que se quiso evitar al bajar de 600 a 300. Ahora se mide desde
el inicio del ciclo. Intervalos a **8 s en los tres escenarios**: con 7 s
quedaban ~0,5 s de holgura sobre el ciclo minimo, demasiado ajustado.

**La linea de downlink del OLED se pintaba en la linea 2**, que el siguiente
refresco de estado sobrescribia: duraba menos de un segundo. Pasa a una linea 6
fija con tipo, secuencia y segundos transcurridos.

### Leccion de metodo (segunda del dia)

Dos veces se concluyo en firme desde evidencia incompleta:

1. Se descarto que `rx1_delay` fuera la causa del fallo de join razonando que el
   JoinAccept usa `join_accept_delay`. Plausible y falso.
2. Se declaro un bloqueante en la recepcion de downlinks porque cinco uplinks
   seguidos no mostraban ninguno — sin advertir que entre las dos capturas serie
   habia un hueco de ~80 s con el puerto cerrado, y que el downlink se entrego
   justo ahi. Lo desmintio el OLED, que llevaba rato mostrandolo.

En ambos casos el dato que lo refutaba estaba disponible. **Comprobar el estado
real antes de teorizar**, sobre todo cuando la hipotesis exculpa al cambio propio.

### Pendiente para manana

**En la placa:**
- [ ] Boton: que cicle los tres escenarios y que la seleccion sobreviva al reinicio (NVS)
- [ ] microSD: que el CSV de corrida se escriba con el nombre largo (`<run_id>.csv`)
- [ ] **Clase C**: `perfil.py terreno-c`, alternar clase con el boton y verificar
      que el downlink llega **al instante** en vez de esperar al siguiente uplink.
      Es la hipotesis H4 y lo unico que justifica el coste de la Clase C

**Fuera de la placa:**
- [ ] Verificar la altitud real del gateway (los 2000 m salen de una curva de
      nivel) y contrastar el perfil de elevacion al cerro con la tabla de terreno
      maximo admisible (cierra A-03 y A-05)
- [ ] Ensayo de autonomia en banco con medidor de corriente USB (Adenda 1)

### Nuevo requisito: dashboard web para el movil

Hace falta **un dashboard web que permita operar la campana entera desde el
telefono**, sin portatil en campo. Lo que deberia cubrir:

- Ver los uplinks en vivo: PDR de la corrida, RSSI/SNR, ultimo fCnt, mapa del track
- Saber que corrida esta en marcha y cuanto le queda (`TX n/300`)
- **Lanzar los pings de latencia** y ver la respuesta, sin `mosquitto_pub`
- **Conmutar el device profile** (ej.09 / terreno-A / terreno-C) sin la consola
- Sustituir o alimentar la hoja de campo, que hoy es un HTML offline aparte

Cuestiones a decidir cuando se aborde: si vive en el servidor en la nube o es una
pagina estatica que habla por MQTT sobre WSS; como se autentica sin exponer
credenciales en el navegador; y si debe seguir funcionando sin cobertura, que es
lo que hoy resuelve `campo/hoja-de-campo.html`.

Queda anotado como **A-07**.

---

## 2026-07-19 (continuación) — D-37, D-38, D-39 · Arranque explícito de corrida

### El problema que se corrige

Hasta ahora **seleccionar era arrancar**. Una pulsación larga cambiaba de escenario
y en ese mismo instante reiniciaba contadores, reconfiguraba la radio y empezaba a
transmitir. Dos consecuencias en campo: no había forma de llegar a «CERRO16 Clase C»
sin pasar transmitiendo por las opciones intermedias, y el principio de cada corrida
se llenaba de uplinks tomados mientras aún se montaba el equipo. Tampoco era posible
sincronizar el arranque con el momento real de la prueba.

Lo señaló el usuario, no una prueba. Es el tipo de defecto que no aparece en el
laboratorio, donde el arranque inmediato incluso resulta cómodo.

### D-37 · Menú con arranque explícito

Máquina de estados: **arranque → JOIN → MENÚ → CORRIDA → FIN → MENÚ**.

| Estado | Corta | Doble | Larga (≥ 2 s) |
|---|---|---|---|
| **MENÚ** (parpadea) | siguiente de las 6 opciones | **ARRANCAR** | — |
| **CORRIDA** | ignorada | ignorada | abortar → menú |
| **FIN** | ignorada | ignorada | → menú |

Una sola regla que enseñar: **larga = ir al menú, siempre**.

Navegar el menú no transmite, no reconfigura la radio y no toca los contadores. Solo
mueve un cursor de 0 a 5; el escenario y la clase se derivan de él, así que no hay dos
variables que puedan quedar descoordinadas. Nada se persiste ni se aplica hasta la
doble pulsación.

**El join va antes del menú** (decisión del usuario sobre la recomendación): puede
tardar y reintentar, así que ocurre mientras se monta el equipo y al confirmar el
primer uplink sale en el acto.

**En corrida, corta y doble se descartan a propósito.** Se conserva así la propiedad
de seguridad que ya tenía el diseño anterior: un roce del botón en la mochila no puede
alterar una medida de 40 minutos. La única entrada al menú es un gesto deliberado.

Dos consecuencias técnicas anotadas para no confundirlas con fallos:

- **El clic corto tarda ~0,4 s.** Para saber que una pulsación no es la primera de una
  doble hay que esperar a que venza la ventana. Es inherente a tener dos gestos sobre
  un solo botón.
- **Solo parpadea la línea de selección** (decisión del usuario). Las líneas de
  contexto —SF/DR, fPort, intervalo, perfil requerido— quedan fijas para poder
  verificar sin prisa qué se va a lanzar.

### D-38 · `FINALIZADO` fijo

Al completar los 300 uplinks la pantalla se queda en `FINALIZADO` y **deja de
transmitir**. No salta al menú parpadeante: eso borraría el aviso de que la corrida
terminó bien, y quien llegue a la sonda tiene que ver de un vistazo que no hay nada
corriendo. Se sigue sondeando la Clase C, porque un downlink tardío de la corrida
recién cerrada todavía es un dato de latencia válido.

### D-39 · Intentos de una corrida abortada

Abortar es una operación normal. El problema es que el `run_id` es
`fecha-ESCENARIO-clase`, así que reanudar el mismo escenario el mismo día reutilizaba
el fichero y **mezclaba dos intentos en un CSV imposible de separar después**.

El firmware resuelve el número de intento **sondeando la microSD**, no con un contador
en NVS: el estado real es el de los ficheros, y así no hay forma de que un contador se
desincronice de lo que hay escrito.

```
20260814-CERRO16-C.csv      primer intento (abortado)
20260814-CERRO16-C-2.csv    segundo intento
```

Los intentos son **corridas distintas** (decisión del usuario). Todos figuran en
`resumen.csv`; la comparación A vs C y las figuras usan el **más completo** de cada
celda y **declaran por escrito cuáles descartaron**. Fundirlos habría introducido
precisamente el sesgo que el control de H2 pretende detectar: si una corrida se abortó
fue por algo, casi siempre un cambio de condiciones.

Se comprobó con datos sintéticos que sin este arreglo el control de validez comparaba
el 90 % de Clase A contra el 53,3 % de un intento abortado y daba **REVISAR** — una
falsa alarma de método. Con el arreglo compara contra el intento completo y da OK.

### Tres residuos encontrados al actualizar la documentación

Ninguno lo buscaba; aparecieron al verificar que los documentos describían el firmware
real. Los tres estaban en documentos que se leen **antes** de salir a campo.

1. **`GUIA-LABORATORIO.md` y `EXPERIMENTO.md` §3.3 afirmaban que el OLED se apaga solo
   a los 30 s.** No existe: el único `0xAE` del driver está en la secuencia de init.
   En el protocolo figuraba además como **variable controlada** de H3, con un argumento
   de consumo construido encima. Corregido en ambos. La consecuencia no es que falte
   implementarlo — refuerza que **H3 no es medible en campo** y pertenece al banco
   (Adenda 1). Añadirlo ahora sería contraproducente: el menú tiene que verse parpadear.
2. **`EXPERIMENTO.md` §6.2 mandaba verificar `rx1Delay = 1 s`.** Residuo de I-01, el
   incidente en que se cambió ese valor. Tal cual estaba, instruía al operador a dar
   por buena una configuración rota. Corregido a 5 s.
3. **El centinela de batería se convierte en «batería llena».** Cuando falla la lectura
   del medidor, `pmu_battery_percent()` devuelve `0xFF`; el OLED lo imprime como
   `Bat 255%` y `payload_terreno.c` lo satura a 100 antes de enviarlo. Los dos sitios
   discrepan y el servidor recibe un dato falso sin aviso. Queda como **A-08**.

### La dependencia del device profile, elevada a sección propia

Elegir Clase C en el menú no sirve de nada si ChirpStack tiene el device en el perfil
de Clase A: los uplinks llegan, el PDR sale bien, el `fPort` dice «Clase C», y las
latencias salen del orden del intervalo de uplink. **H4 quedaría refutada por un error
de configuración, sin dejar rastro.**

El firmware no puede detectarlo ni corregirlo. Se mitiga por procedimiento (§6.4 del
protocolo, paso 1 del manual de campo) y mostrando en el menú el perfil requerido
(`Perfil: terreno-c`) en el único momento en que el operador puede actuar.

### Documentación

Nuevo **`docs/MANUAL-DE-CAMPO.md`**: operación paso a paso, las cuatro pantallas
dibujadas línea a línea, los tres gestos, tabla de diagnóstico y cierre de campaña.
Es autosuficiente a propósito — en el cerro no se consulta el código.

`EXPERIMENTO.md` sube a **v1.2**. Actualizados también `GUIA-LABORATORIO.md`,
`CUESTIONARIO-PREVIO.md`, `firmware/README.md`, `analisis/README.md` y el README raíz.

### Estado

- Firmware **compila limpio** (ESP-IDF v5.5.2, sin avisos nuevos). **No probado aún en
  placa**: el menú, el parpadeo, el aborto y el sufijo de intento están sin verificar
  sobre hardware.
- Scripts de análisis probados de extremo a extremo con datos sintéticos que incluyen
  un intento abortado.

### Pendiente

**En la placa (lo primero, antes que nada de campo):**
- [ ] Menú: que las 6 opciones ciclen, que solo parpadee la línea de selección y que
      la doble pulsación arranque
- [ ] Que navegar el menú **no** transmita
- [ ] Aborto con pulsación larga y reanudación: comprobar que nace el fichero `-2`
- [ ] `FINALIZADO` al llegar al objetivo (se puede forzar bajando `uplinks_objetivo`)
- [ ] microSD: CSV de corrida con el nombre largo, incluido el sufijo de intento
- [ ] **Clase C**: `perfil.py terreno-c` y verificar que el downlink llega **al
      instante** en vez de esperar al siguiente uplink. Es H4, y lo único que
      justifica el coste de la Clase C

**Fuera de la placa:**
- [ ] **A-08**: centinela de batería (ver arriba). Toca payload, `decoder.js` y OLED
- [ ] Verificar la altitud real del gateway y contrastar el perfil de elevación al
      cerro con la tabla de terreno máximo admisible (cierra A-03 y A-05)
- [ ] Ensayo de autonomía en banco con medidor de corriente USB (Adenda 1)
- [ ] **A-07**: dashboard web para operar la campaña desde el móvil

---

## 2026-07-19 (validación en placa) — D-40 · El menú, verificado sobre hardware

### Antes que nada: el menú no estaba en la placa

Se reportó el trabajo anterior como «compila limpio, no probado en placa» y ahí se
dejó. **Nunca se ejecutó `idf.py flash`.** El usuario fue a probar el menú contra el
binario de la sesión anterior, comprobó que no parpadeaba ni activaba nada, y
concluyó con razón que no funcionaba.

Lo demostró `esptool verify_flash`, que es la comprobación que debió hacerse antes de
afirmar nada:

```
Verifying 0x69ff0 (434160) bytes @ 0x00010000 ... -- verify FAILED (digest mismatch)
```

**Lección.** «Compila» y «funciona en el dispositivo» son afirmaciones distintas y la
segunda no se deduce de la primera. Cuando un cambio tiene que verificarse en
hardware, o se flashea, o se dice **de forma inequívoca** que el dispositivo sigue con
el binario anterior. Decirlo de pasada no basta: el usuario perdió una sesión de
pruebas contra software que no existía en la placa.

### Un defecto real del firmware viejo, encontrado en la captura

Antes de reflashear se capturó la corrida en marcha:

```
---- 00000000-TERRAZA-C  TX 38/300 ----
payload 14B fPort 15 DR3/SF7 airtime ~67 ms
```

Tres respuestas distintas a la misma pregunta: el `run_id` decía TERRAZA-C, los
parámetros (DR3/SF7, 14 B) eran de TERRAZA, y el `fPort 15` correspondía a CERRO16
Clase A.

**Causa.** `escenarios_atender_boton()` se llamaba en dos sitios. Dentro de la espera
entre uplinks estaba como `if (escenarios_atender_boton()) break;`: esa llamada
**aplicaba** el cambio de escenario y clase, pero solo rompía la espera. Al volver al
principio del bucle se llamaba otra vez y, con el evento ya consumido, devolvía
`false`, de modo que **`cfg` y `run_id` nunca se actualizaban**.

**Impacto si hubiera ocurrido en campo.** `cruzar.py` deduce el fPort esperado del
`run_id` (14), consulta el servidor y no encuentra nada, porque los paquetes llegaron
con fPort 15. El resultado sería un **PDR de cero sin ninguna pista de la causa**, y
lo provoca el uso normal del firmware anterior: pulsar el botón durante la espera.

El rediseño de D-37 lo elimina de raíz — la selección solo se toca en el menú, donde
no hay nada transmitiendo, y la espera solo reconoce la pulsación larga, que sale de
la corrida entera en vez de mutar medio estado.

### D-40 · El LED como indicador de modo

Petición del usuario: poder confirmar en qué modo está la sonda sin leer la pantalla.

| LED | Significa |
|---|---|
| Parpadeando 1 Hz | **Menú**: configurando, no midiendo |
| Apagado | Join, corrida en marcha o `FINALIZADO` |

Deliberadamente binario: distinguir corrida de `FINALIZADO` es trabajo de la pantalla,
que ya lo dice con todas las letras. El LED responde a la única pregunta que uno se
hace al acercarse a la sonda: *¿está midiendo o la estoy configurando?*

Antes, `pmu_charge_led_blink()` dejaba el LED parpadeando desde el arranque y para
siempre, como señal de «vivo», lo que no distinguía nada. Se sustituye por
`pmu_led_modo()`, que expone los cuatro modos del CHGLED del AXP2101 (registro `0x69`).

**Efecto colateral documentado:** poner el CHGLED en control manual se lo quita al
cargador, y el registro persiste con la placa apagada. Con la sonda apagada y cargando
por USB, el LED muestra lo último que escribió el firmware, **no** el estado de carga.

### Verificación sobre hardware

`verify OK (digest matched)`, y con el usuario pulsando el botón:

| Comprobación | Evidencia |
|---|---|
| Join **antes** del menú | `JOIN NUEVO por aire` (6,7 s) → `=== MENU:` (7,6 s) |
| **El menú no transmite** | 16 s en el menú (7,6 → 23,6 s), ni un uplink |
| Corta cicla las 6 opciones | `menu -> URBANO Clase C` → `menu -> TERRAZA Clase A` |
| Doble confirma y arranca | `CONFIRMADA: URBANO Clase A` → `=== ARRANCA ===` |
| **Sufijo de intento** | `ya habia corridas previas: este es el intento 2` → `00000000-URBANO-A-2` |
| Recordatorio del perfil | `el device profile del servidor debe ser: terreno-a` |
| Periodo real | TX1 a 23702 ms, TX2 a 31779 ms → **8,08 s** |
| Coherencia de la corrida | `run_id URBANO-A-2` · `fPort 11` · `DR1/SF9` · 14 B — **los cuatro coinciden** |

Confirmado además por el usuario sobre la placa: la pulsación larga aborta y devuelve
al menú, las cortas cambian de opción y la doble arranca. El LED y el parpadeo de la
línea de selección, verificados visualmente.

### El DevEUI del pinger apuntaba a un dispositivo inexistente

`servidor/pinger.py` tenía `DEV_EUI = "0011223344550002"`. El device real es
`...0001`, el del ejercicio 09 (D-16, revertida en R-04). Con ese valor el pinger se
suscribía al topic de un device que no existe: **no habría detectado ninguna corrida
ni enviado un solo ping, sin dar error — solo silencio.** H4, que es lo único que
justifica el coste de la Clase C, se habría quedado sin datos.

El origen es `firmware/credentials.json`, congelado en el diseño original. **Los cuatro
valores de su bloque `device` eran falsos** (DevEUI, `app_key`, device profile y su
nombre), más un `rx1_delay_s: 1` que es otro residuo de I-01. Nada lo lee en tiempo de
compilación —la fuente real es `main/config_lorawan.h`—, pero parece autoritativo, y
`pinger.py` copió de él. Corregido y marcado con un aviso explícito de que es una
ficha de referencia, no una fuente de configuración.

### Pendiente

**Antes de campo:**
- [ ] Decidir si se desactiva `PICARO_FORCE_FRESH_JOIN=1`. Fuerza un join OTAA real en
      cada arranque, lo que es correcto para depurar pero en el cerro significa que un
      join fallido deja la salida sin corrida
- [ ] Probar `FINALIZADO` de verdad (se puede forzar bajando `uplinks_objetivo`)
- [ ] Ejecutar `pinger.py` ya corregido contra el device real: nunca se ha usado
- [ ] **Clase C** con `perfil.py terreno-c`: verificar que el downlink llega al
      instante (H4)
- [ ] **A-08**: centinela de batería `0xFF` → 100 % en el payload
- [ ] Verificar la altitud real del gateway (cierra A-03 y A-05)
- [ ] Ensayo de autonomía en banco (Adenda 1)
- [ ] **A-07**: dashboard web para operar desde el móvil

---

## 2026-07-19 (validación, cont.) — D-41 · Join real en cada arranque · pinger

### D-41 · `PICARO_FORCE_FRESH_JOIN = 1` se mantiene

El flag ya estaba en 1; se confirma como decisión, no como resto de depuración.
Fuerza un join OTAA **real por aire en cada arranque**, ignorando la sesión guardada
en NVS. `JOIN OK` solo aparece si hubo JoinAccept, lo que **exige gateway en rango**.

Por qué es lo correcto para este experimento, y no solo cómodo para depurar: con el
flag a 0, RadioLib restauraría la sesión de NVS (`SESSION_RESTORED`) y la sonda
empezaría a transmitir **sin haber confirmado que hay un gateway escuchando**. En el
cerro eso significa transmitir al vacío durante 40 minutos y descubrir el problema al
analizar, con un PDR de cero que no distingue «no había enlace» de «se perdió todo».

**Modo de fallo aceptado (decisión del usuario).** Si el join no entra en el cerro, la
sonda reintenta y la corrida **no arranca**. Eso no es una avería: significa que el
enlace nunca fue viable, así que no hay experimento válido que ejecutar en ese punto.
El resultado —«desde aquí no hay cobertura»— es en sí mismo un dato, y se anota en la
hoja de campo. El operador lo ve en el OLED como `JOIN #n` subiendo sin llegar a
`JOIN OK`.

Coste conocido: cada arranque consume un DevNonce. RadioLib los persiste en NVS y los
incrementa (`Nonces restaurados de NVS`), así que el servidor no los rechaza por
repetición. No hay problema de desincronización.

### Punto 2 · pinger validado (conexión y topic)

`servidor/pinger.py`, ya con el DevEUI corregido, conecta al broker por TLS,
autentica como `picaro` y se suscribe al topic correcto:

```
[ok] Conectado. Escuchando application/<APP_ID>/device/0011223344550001/event/up
```

Es `...0001`, el device real, no el `...0002` inexistente de antes. Con la placa en
MENÚ (sin transmitir), el pinger espera sin detectar corrida durante 16 s, lo que es
además una confirmación **del lado servidor** de que la sonda no emite. El ciclo
completo —detectar corrida por su fPort y enviar los pings— queda por validar contra
una corrida en marcha, que requiere pulsar el botón físicamente. `paho-mqtt` no estaba
instalado en la máquina de trabajo; se instaló.

### Nota técnica: abrir el puerto serie RESETEA la placa

En el T-Beam Supreme (ESP32-S3 con USB-Serial/JTAG nativo), **abrir el puerto COM
pulsa la línea RTS, que está mapeada a EN (reset)**. Cualquier captura de serie —aun
sin enviar el pulso de reset explícito— reinicia el chip: se observa
`rst:0x15 (USB_UART_CHIP_RESET)` y un arranque completo.

**Consecuencia práctica:** no existe la «captura no invasiva» por serie en esta placa.
Al intentar validar el estado FINALIZADO de una corrida sin resetear, la abrí y la
saqué de ese estado, dejándola en MENÚ. La validación de que una corrida **terminó y
dejó de transmitir** debe hacerse por otras vías que no toquen el puerto:

- **En el OLED**, que muestra `FINALIZADO` (lo observó el usuario antes del reset).
- **Del lado servidor**, comprobando que dejan de llegar uplinks (el pinger, o la
  SQLite del dashboard).
- **En la microSD**, por el CSV de la corrida (el arranque confirma `CSV existente`).

El serie sirve para ver un arranque o una corrida en marcha, no para inspeccionar un
estado quieto sin destruirlo.

---

## 2026-07-19 (A-08) — Centinela de batería: un fallo de lectura ya no miente

### El defecto

`pmu_battery_percent()` devuelve `0xFF` cuando la lectura I2C del medidor (gauge)
falla. De ahí, el valor seguía dos caminos, y ambos mentían:

- En el payload, `payload_terreno.c` hacía `buf[13] = (batt_pct > 100) ? 100 : batt_pct`
  → `0xFF` se **saturaba a 100**: un fallo de lectura llegaba al servidor disfrazado de
  «batería llena», sin ningún aviso.
- En el OLED se imprimía con `%u` → aparecía `Bat 255%`.

Dos representaciones distintas del mismo dato, y la del servidor era la peligrosa: en
una campaña de autonomía, «100 %» por un fallo de lectura contamina justo la variable
que se mide.

Lo salvaba solo la microSD: `runlog` registra `batt_mV`, no el porcentaje, y los
milivoltios son lectura directa del ADC. Esa es la fuente honesta.

### La corrección, en los tres sitios

`0xFF` pasa a ser el valor reservado de «desconocido», coherente de punta a punta:

- **payload** (`payload_terreno.c`): `buf[13] = (batt_pct > 100) ? 0xFF : batt_pct`.
  Se propaga el centinela en vez de saturarlo. Cualquier valor fuera de 0..100 se
  normaliza a un único `0xFF`.
- **decoder** (`decoder.js`): si el byte 13 es `0xFF`, `battery_pct = null` y un
  warning que remite a `battery_v`. Los valores 0..100 decodifican igual que antes:
  cambio retrocompatible.
- **OLED** (`app_main.cpp`): `Bat --` cuando el porcentaje no es válido, con los mV
  siempre visibles.

### Verificación

- Firmware **compila y flasheado** (`verify OK (digest matched)`).
- `decoder.js` probado con Node y vectores: `87 -> 87`, `100 -> 100`, `0 -> 0`,
  `0xFF -> null` (con warning), 11 bytes → sin batería. `battery_v = 3.712` en todos.
- Decoder **desplegado a los dos perfiles de terreno** con `servidor/desplegar_decoder.py`,
  que hace round-trip (GET, cambia solo el codec, PUT, verifica) para no tocar ningún
  otro campo. Previsualización antes de escribir: el único diff era esta corrección.
  El perfil del ej.09 no se toca. Ambos perfiles verificados tras el PUT.

### Nueva herramienta

`servidor/desplegar_decoder.py` mantiene `terreno-a` y `terreno-c` con el mismo
`decoder.js` en un comando, en vez de copiar y pegar en la consola web. Por defecto
solo previsualiza; escribe con `--aplicar`. Es la contraparte de `perfil.py`: cuando
el formato del payload cambie, el codec del servidor se actualiza desde aquí y no a
mano.

---

## 2026-07-19 (A-07) — D-42 a D-46 · App de campo y microservicio, construidos

Se aborda **A-07**: operar y vigilar la campaña desde el teléfono, sin portátil en el
cerro. El diseño se congeló en un contrato único, `docs/CONTRATO-CAMPO.md`, y de ahí
salieron **en paralelo** —con un equipo de agentes: arquitecto, dos desarrolladores,
documentador y un pase de tester— el **microservicio** (FastAPI + Docker, junto a
ChirpStack) y la **app** (Flutter, APK local). Guía de uso: `docs/APP-CAMPO.md`.

Principio rector, heredado de I-01: el microservicio es **solo aditivo**. *Lee* del
MQTT y *llama* a la API REST de ChirpStack para lo que ya hacíamos a mano (conmutar el
perfil de nuestro device, encolar pings). La configuración global sigue intocable.

### D-42 · Despliegue Opción A — subdominio por Caddy, sin puerto nuevo

El contenedor `picaro-campo` se une a la red Docker externa `picaro` y escucha en un
puerto **interno** (8000), sin publicarlo. Caddy —el del stack de ChirpStack— gana un
bloque `campo.pi-caro.org { reverse_proxy picaro-campo:8000 }` que emite el certificado
(HTTP-01, puerto 80 ya abierto) y hace de pasarela también para el WebSocket. El
`docker-compose.campo.yml` es **separado**, declara la red como `external`, y no toca el
compose de ChirpStack. **Alternativas descartadas:** publicar un puerto nuevo y abrirlo
en el firewall (más superficie, TLS aparte); o una página estática hablando MQTT sobre
WSS (metería credenciales en el navegador). **Detalle de construcción:** la red real de
Docker es `picaro-chirpstack_picaro` (prefijo del proyecto compose), no `picaro`; el
compose lo resuelve con una variable overridable.

### D-43 · «Arrancar» = sesión de captura, no control de la radio

La radio se arranca **solo físicamente** (menú + doble pulsación, D-37). El botón
**Arrancar** de la app hace `POST /session/start`: conmuta el perfil, calcula el
`expected_fport` y abre la sesión. **Por qué:** separa *medir* (físico, en el cerro) de
*registrar/vigilar* (online, en el servidor). Y como fija el perfil desde la misma
selección con la que calcula el `expected_fport`, **cierra el punto ciego del manual**:
el desajuste perfil↔clase (lo que refutó H4 sin dejar rastro) pasa a ser **detectable**
por el aviso de desajuste de fPort. **Alternativa descartada:** controlar la sonda por
downlink (frágil en Clase A y en cobertura intermitente; rompería la seguridad de D-37).

### D-44 · Navegación · D-45 · Token · D-46 · Icono

Navegación por frecuencia de uso: se vive en el **Panel**; Mapa y Gráficos son consulta
rápida (barra inferior); Sesiones/Acerca/Ayuda son ocasionales (menú `≡` y botón `?`).
Autenticación: un **único token Bearer** local (no login/JWT, sobredimensionado para una
persona), sobre TLS obligado porque el servicio está expuesto a internet — el token es
toda la puerta y **no entra en git**. Icono: Pi embebido (chip) + señal LoRa + pluma de
Ícaro sobre cielo nocturno; la paleta de la app se deriva de él.

### Construcción y verificación

- **Microservicio**: FastAPI con ingesta MQTT (reusa `parse_chirpstack_up`), SQLite
  (reusa el esquema del dashboard + `session_id` + tabla `sessions`), API REST +
  WebSocket con token, CSV por sesión, y proxy a ChirpStack para perfil y pings
  (absorbe lo que eran `perfil.py` y `pinger.py`). **31 tests pytest en verde** y
  **arranque real de uvicorn** verificado (`/health`, auth 401, sesiones).
- **App Flutter**: 6 pantallas + configuración; cliente REST/WS; mapa OSM con degradado
  offline; gráficos en `CustomPainter`. **`flutter analyze` limpio** (0 errores/0
  warnings) y **APK compilado** con éxito, icono adaptativo y splash incluidos.
- **Coherencia app↔servicio verificada**: mismos endpoints, mismos 6 tipos de mensaje
  WS, clave `class` en el wire (aliasada en ambos lenguajes) y métricas con claves
  idénticas.

### Corrección durante el tester (fleco #3 del contrato)

`progress_pct` usaba el `fCnt` **absoluto** mientras `pdr_est` usaba el rango
`(last−first+1)`. Una segunda corrida sin reiniciar la sonda arranca con el contador
alto y habría mostrado >100 % y auto-finalizado al instante. Se alineó al **rango**
(recibidos+gaps) para espejar el «TX n/300» del dispositivo; corregido en `sessions.py`
y en dos tests, que codificaban la semántica vieja. El contrato sube a **v1.1** (§12)
con éste y los otros nueve flecos resueltos o documentados.

### Pendiente de A-07

- [ ] Crear el registro DNS `A` `campo.pi-caro.org` → `<IP_DEL_SERVIDOR>` (lo hace el usuario)
- [ ] Añadir el vhost a Caddy + la variable `DOMAIN_CAMPO` y recargar (aditivo)
- [ ] Rellenar el `.env` (token, contraseñas, GW_LAT/LON) y desplegar el contenedor por SSH
- [ ] `flutter create .` local + compilar el APK (Gradle 8.7 / AGP ≥8.2.1 si el JDK es 21)
- [ ] Prueba **end-to-end** con la sonda: sesión completa, desajuste de fPort, CSV, Clase C

---

## 2026-07-19 (A-07) — Despliegue del microservicio de campo

Desplegado el microservicio en el servidor en la nube, **Opción A** (subdominio por
Caddy, sin puerto nuevo), con autorización expresa del usuario para la recarga de Caddy.
Todo **aditivo**: ChirpStack no se tocó.

**Qué se hizo, por SSH (`root@lns.pi-caro.org`):**
- Código en `/opt/picaro-campo/{microservicio,despliegue-campo}` (scp de un tarball
  limpio, sin venv/cache). `.env` (600) con el token, la contraseña MQTT, el token de la
  API de ChirpStack y `GW_LAT/LON` del gateway.
- `docker compose -f docker-compose.campo.yml up -d --build`: contenedor `picaro-campo`
  en la red `picaro-chirpstack_picaro`, puerto interno 8000 **sin publicar**, volumen
  `campo-data` para la SQLite.
- Caddy: **backup** del Caddyfile (`Caddyfile.bak.<epoch>`) + bloque literal
  `campo.pi-caro.org { reverse_proxy picaro-campo:8000 }`, `caddy validate` → *Valid*,
  y **`caddy reload`** (recarga en caliente, sin recrear el contenedor).

**Verificación desde internet:** `campo.pi-caro.org/health` → 200 `mqtt_connected:true`;
`/sessions` con token → 200, sin token → 401; `/session/current` → `{session:null}`. Y
`lns.pi-caro.org` / `api.pi-caro.org` siguen en 200: la recarga no rompió el LNS.

**Detalles operativos** (para redepliegue/depuración):
- MQTT: el contenedor conecta al broker por `mqtt.pi-caro.org:8883` (TLS) y el hairpin a
  la IP pública **funciona** (`mqtt_connected:true`). No hizo falta apuntar a `mosquitto`
  interno.
- Red real: `picaro-chirpstack_picaro` (coincide con el default del compose; sin override).
- El **token** de la API (`CAMPO_TOKEN`) vive en `<infra-privada>/.campo-token`, fuera de git.
- Actualizar tras cambios de código: re-scp de `microservicio/` + `docker compose ... up
  -d --build` en `/opt/picaro-campo/despliegue-campo`.

**Pendiente de A-07:** instalar el APK en el teléfono (URL `https://campo.pi-caro.org` +
token) y la **prueba end-to-end con la sonda** — es la primera vez que app y
microservicio hablarán de verdad, y donde se validan sesión completa, aviso de desajuste
de fPort, descarga de CSV y el comportamiento de Clase C.

---

## 2026-07-19 (A-07) — Primera corrida real; replay y borrado de sesiones (D-47)

### La app funcionó de extremo a extremo en campo

Primera prueba real con la sonda: `20260719-URBANO-A-2`, URBANO Clase A, 42 uplinks
recibidos, PDR estimado 91 %. La app cambió el perfil al arrancar, la sonda transmitió,
el microservicio capturó (con `raw_json` íntegro) y el CSV se exportó. El sufijo `-2`
confirma que abortar/reanudar también funciona en real (quedaron dos sesiones: la
abortada `URBANO-A` con 34 rx y la buena `-2`). Validado de paso: cambio de perfil
automático, timing de 8 s, la corrección A-08 (batería 68 % real, no 255/100) y el GPS
(altitud ~1920 m junto al gateway — dato para A-05).

El 91 % y un RSSI que oscilaba de −59 a −118 dBm **a menos de 110 m del gateway** no es
un problema del sistema: el gateway estaba en la primera planta de una casa de dos
pisos, así que la losa obstruye. Confirmado por el usuario. Recordatorio para campo:
antena vertical y despejada.

### D-47 · Replay y borrado de sesiones

A raíz de la prueba, dos añadidos, ambos **sobre las sesiones del servidor** (que es
donde se acumulan; el teléfono no guarda una base local):

- **Replay**: desde el detalle de una sesión, *Ver mapa* / *Ver gráficos* redibujan esa
  sesión con los datos del servidor (`GET /sessions/{id}` + `/uplinks`), reutilizando
  los mismos widgets que la vista en vivo (refactorizados a `MapPanel` y `ChartsPanel`).
  Es una **foto fija**: no escucha el WebSocket, así que una sesión nueva que arranque
  no altera el replay abierto —se actualizan las pestañas en vivo, no el replay—. Esa
  separación fue la razón de elegir «vista propia» en vez de que las pestañas de abajo
  cambiaran de sesión.
- **Borrado**: nuevo `DELETE /sessions/{id}` (404 si no existe, **409 si está
  capturando**) + botón *Descartar sesión* con diálogo de confirmación que advierte de
  que es **irreversible**. Para no acumular sesiones de prueba en el servidor.

**Acerca de** reencuadrado: no es una «campaña», es una **herramienta open source** para
las pruebas de campo del proyecto radiosonda PiCARO (Clase A vs C). Autoría/MIT/correo
se mantienen.

### Verificación

- Microservicio: **34 tests** pytest en verde (los 31 + 3 de borrado). Redesplegado por
  SSH (`up -d --build`); el volumen conservó las dos sesiones. `DELETE` verificado desde
  internet (401 sin token, 404 inexistente) sin tocar datos reales.
- App: `flutter analyze` limpio (0 errores/0 warnings). APK v2 recompilado (con el
  permiso INTERNET) y copiado a `Downloads`.
- Contrato a **v1.2** (§13).

### Pendiente

- [ ] Instalar el APK v2 y probar en el teléfono el replay y el borrado con datos reales.
- [ ] Las corridas de campo de verdad: terraza (LoS), cerro (16 km), y **Clase C / H4**.
- [ ] Enganchar `cruzar.py` para cruzar la microSD (enviado) contra el CSV de la app
      (recibido) y obtener el PDR definitivo (hoy apunta al dashboard viejo).

---

## 2026-07-19 (A-07) — Distribución del APK: GitHub Release v1.0.0 firmada

El APK se publica desde el repo por **GitHub Releases** (no se mete el binario en git):
[`v1.0.0`](https://github.com/ovelazquezj/experimentos_campo_picaro/releases/tag/v1.0.0).
Como el repo es **privado**, la descarga queda limitada a colaboradores — coherente con
que es una herramienta de uso interno.

**Firma de release propia** (opción B, elegida por el usuario). El APK deja de ir con la
clave de debug y se firma con una clave estable, para que las **actualizaciones se
instalen encima** sin conflicto de firma:

- **Keystore: `<infra-privada>/picaro-campo-release.jks`** (PKCS12, RSA 2048, validez ~27 años),
  contraseña en `<infra-privada>/.campo-keystore`. **Ambos fuera de git.** Cert:
  `CN=Omar Velazquez, OU=PiCARO`. ⚠️ **Perder este keystore = no poder actualizar la app
  instalada** (habría que desinstalar/reinstalar). Respaldarlo.
- `android/app/build.gradle` firma el `release` leyendo `android/key.properties`
  (gitignorado). Como `android/` se regenera con `flutter create`, hay que reaplicar el
  `signingConfig` y recrear `key.properties`; documentado en `app/README.md`.

Publicar una versión nueva: subir `versionName`/`versionCode`, `flutter build apk
--release` (firma sola con la clave) y `gh release create vX.Y.Z <apk>`.

Estado de A-07: la app está **construida, desplegada, probada en campo y distribuible**.
Pendiente: las corridas de campo reales (terraza, cerro, Clase C / H4) y cruzar la
microSD con el CSV de la app (`cruzar.py` ya lo soporta).

---

## 2026-07-20 (v2) — D-48 a D-53 · Control de la sonda por BLE

La v1 dejaba **dos selecciones humanas independientes** que había que hacer coincidir a
mano: la corrida elegida en la app (que fija el device profile) y la elegida en la sonda
con el botón. Podían divergir, y el resultado de divergir es el fallo más caro de la
campaña: uplinks normales, PDR normal, fPort normal, y una medida de latencia
silenciosamente falsa. La v1 lo vigilaba **a posteriori** con el aviso de desajuste de
fPort. La v2 lo elimina **en el origen**: una sola selección, en un solo sitio.

Trabajo hecho por fases, con dos *spikes* de de-riesgo antes de escribir nada definitivo
(coexistencia BLE+LoRa, y emparejamiento nativo), firmware y app implementados en
paralelo contra un contrato de interfaz cerrado, e integración verificada sobre hardware.

### D-48 · La selección ocurre en la app y se propaga a las dos mitades

Elegir una corrida y pulsar **Arrancar** hace, con una sola acción: (a) `POST
/session/start` —que conmuta el device profile y abre la sesión, exactamente como en la
v1— y (b) una escritura por **BLE** ordenando a la sonda que arranque ese mismo
escenario y clase. El desajuste **deja de poder originarse en un error humano de
selección**, porque ya no hay dos elecciones que puedan discrepar.

**El orden es contractual: servidor primero, BLE después.** Los dos fallos posibles no
son simétricos. Si se hiciera al revés y fallara el servidor, la sonda estaría
**transmitiendo** contra un perfil que puede ser el equivocado — una corrida de Clase C
contra un perfil de Clase A no encola los downlinks inmediatos y produce justo la medida
falsa que la v2 viene a hacer imposible. En el orden elegido, un fallo del BLE deja una
**sesión vacía**: evidente al instante, y la app la cierra sola. Se prefiere el fallo
visible y reversible al invisible que contamina un dato.

**Al abortar el orden se invierte: BLE primero, servidor siempre.** BLE primero porque
parar la transmisión es lo urgente y es local; el servidor **sin condición**, porque
cerrar la sesión no puede depender de un enlace que quizá se cayó (ver D-52).

**El botón se conserva como respaldo COMPLETO** (no degradado): navegar, arrancar,
abortar y volver al menú, sin app, sin teléfono y sin cobertura. Y las pantallas de
configuración y de corrida quedan **idénticas** a la v1; la única pantalla nueva es la de
emparejado, que es un estado nuevo, no una modificación de los existentes.
**Alternativa descartada:** controlar la sonda por downlink LoRa (ya descartada en D-43,
y por lo mismo: frágil en Clase A y con cobertura intermitente). El canal nuevo es
**local** — exige estar a metros de la sonda — y por eso no reintroduce esa fragilidad.

**Detalle de diseño:** por BLE **seleccionar es arrancar**, equivalente exacto a la doble
pulsación pero diciendo además *cuál*. No hay comando de «mover el cursor»: navegar es un
gesto local del botón. De ahí que el BLE pueda arrancar desde `FINALIZADO` sin pasar por
el menú y el botón no — el botón no sabe decir «arranca la 3», sólo navegar. **El
comportamiento del botón no cambia en nada.**

### D-49 · Decisión I — LE Secure Connections en vez de autenticación propia

**Se cambió una decisión que ya estaba cerrada, y conviene dejar escrito por qué.** El
diseño aprobado (D2/P1) autenticaba **a nivel de aplicación**: un PIN de 8 dígitos en
NVS, reto-respuesta HMAC-SHA256 sobre un enlace **en claro**, con la misma criptografía
escrita dos veces (C con mbedTLS, Dart con `crypto`). Se eligió así para **evitar el
diálogo de emparejamiento del sistema de Android**.

Se cambió porque **se midió, y la premisa era falsa**. Nunca se había comprobado ni
cuánto costaba ese diálogo ni cuánta seguridad se estaba cediendo a cambio. Un spike
midió las dos cosas:

- **El diálogo cuesta muy poco:** aparece **encima de la app**, se teclea, se acepta y se
  vuelve sin salir de ella ni pasar por los Ajustes de Android. La premisa que justificaba
  todo el esquema propio no se sostenía.
- **El esquema propio era peor de lo que parecía:** 26,6 bits sobre un enlace sin cifrar
  se rompen **offline, en segundos, desde una sola captura pasiva**. No es criptografía,
  es una molestia.

| | HMAC a nivel de app | LE Secure Connections |
|---|---|---|
| Bits del código | 26,6 (8 dígitos) | **20** (6 dígitos) |
| Ataque pasivo (capturar y romper offline) | **roto en segundos** | **imposible** (ECDH P-256) |
| MITM | sin protección | ~1/10⁶ y **un solo intento** |
| Enlace cifrado | **no** | **sí**, llave de 16 B |
| Código propio | HMAC en C + HMAC en Dart + NVS + rotación | flags de `sdkconfig` y de `ble_hs_cfg` |
| Reconexión | rehacer reto-respuesta cada vez | **automática, 270 ms** |

**El esquema con MENOS bits resulta mucho más fuerte**, y ésa es la parte contraintuitiva
que hay que entender: no gana por tener un número más grande, gana porque **cambia la
clase de ataque disponible**. Contra el primero bastaba escuchar; contra el segundo hay
que interponerse en el instante exacto del emparejamiento y acertar **a la primera**, o
el emparejamiento aborta.

**Y además es menos código, no más.** Desaparecen del alcance: las dos implementaciones
del HMAC y su vector de prueba, las características `Reto` y `Auth`, el nonce y su ciclo
de vida, el secreto propio en NVS con su rotación, y la custodia del PIN en la app. Con
ello desaparecieron también **dos escaladas abiertas**: el vector de prueba que bloqueaba
el arranque del firmware, y la aceptación de riesgo de los 26,6 bits — que queda
**resuelta, no aceptada**.

**Ganancias que no estaban en el análisis original y merecen constar:** reiniciar la
sonda y **reinstalar la app** dejan de tener coste de re-provisión. Las llaves las
custodia el sistema operativo a cada lado, no la app; antes, un `flutter install` sobre
un teléfono de campo obligaba a volver a teclear el PIN.

### D-50 · `CONFIG_BT_NIMBLE_SM_LEGACY=n` y la comprobación de `authenticated`

Dos cerrojos contra el **mismo fallo**, que es el único de todo este diseño que
**funciona y parece que funciona**.

**El fallo:** un emparejamiento *Just Works* se completa con toda normalidad, da
`encrypted = 1` y `bonded = 1`, y **no tiene ninguna protección contra
man-in-the-middle**. No enseña ningún número, no da ningún error y no se distingue de un
emparejamiento bueno si sólo se mira `encrypted`.

**Cerrojo 1 — compilación.** `sm_sc = 1` declara que *queremos* Secure Connections, pero
**no basta por sí solo**: si el código de emparejamiento *legacy* está compilado y el par
declara que no soporta SC, la pila **puede negociar a la baja**, y el legacy tiene un
intercambio de llaves **recuperable en pasivo** — exactamente el agujero que la decisión I
existe para cerrar, entrando por otra puerta. La defensa real es **compilarlo fuera**:
`CONFIG_BT_NIMBLE_SM_LEGACY=n`. Configuración y compilación juntas; ninguna de las dos
basta sola. En la misma línea, `sm_io_cap = DISPLAY_ONLY` **no es cosmético**: con
`NO_INPUT_OUTPUT` el emparejamiento cae a *Just Works* directamente.

**Cerrojo 2 — verificación en tiempo de ejecución.** La sonda **no sale del estado de
emparejado** si no se cumplen las tres condiciones: `encrypted = 1` **y**
`authenticated = 1` **y** `key_size = 16`. `authenticated` es el único de los tres que
distingue Passkey Entry de *Just Works*. **Regla para quien toque este código: si en algún
punto se lee `encrypted` sin leer `authenticated` al lado, es un bug.**

Otras opciones que no son de relleno: `MAX_CONNECTIONS=1` (una app a la vez, lo que
elimina de raíz «¿y si dos móviles mandan órdenes contradictorias?»), `NVS_PERSIST=y`
(sin ella el bonding no sobrevive a un reinicio y habría que emparejar en cada arranque),
`MAX_BONDS=3` (principal + repuesto + margen) y `ROLE_CENTRAL/OBSERVER=n` (la sonda no
escanea). **`CONFIG_SPIRAM` sigue sin activar:** se midió y no hace falta.

### D-51 · El emparejamiento sólo se acepta con el dedo en el botón

**Fuera del estado de emparejado, cualquier intento de emparejarse se rechaza terminando
la conexión.** Las reconexiones de un móvil ya emparejado no se ven afectadas: ésas no son
un emparejamiento sino un cifrado con llaves existentes.

**Lo fuerza una restricción dura del proyecto, no una preferencia estética.** Si el
emparejamiento pudiera ocurrir en cualquier momento, el código de 6 dígitos habría que
pintarlo encima de la pantalla de corrida o de la de configuración, y las dos conservan su
comportamiento de la v1 **sin excepciones**. Como no hay dónde poner el número, no puede
haber emparejamiento fuera de la pantalla que sí lo tiene.

**Y resulta ser además la decisión de seguridad correcta**, que es lo que suele pasar
cuando una restricción está bien puesta: **nadie empareja un teléfono nuevo sin que una
persona pulse el botón de la sonda**. El gate de posesión física deja de depender de leer
un PIN de la pantalla y pasa a depender de **pulsar el botón**, que es más fuerte porque
no se puede fotografiar desde lejos.

**Consecuencia que se acepta a conciencia:** no hay recuperación remota. Si el teléfono se
pierde y el de repuesto no está emparejado, hay que ir hasta la sonda. El respaldo por
botón sigue funcionando —la salida de campo no se pierde—, pero la v2 deja de estar
disponible hasta entonces.

**Los gestos del estado de emparejado**, que reutilizan el vocabulario de la v1 sin añadir
reglas nuevas:

- **Corta → salir al menú.** Es lo más crítico del estado: un teléfono muerto, olvidado en
  casa o sin la app **no puede dejar la sonda encerrada** ahí. Sin esta salida se perdería
  la salida de campo entera. Por eso **sí** está anunciada en la pantalla: una salida de
  emergencia sin señalizar no es una salida de emergencia. La **larga** hace lo mismo,
  porque la regla que se enseña en campo —«larga = ir al menú, siempre»— no admite una
  excepción justo en el estado donde el operador ya está nervioso.
- **Doble → borra TODOS los emparejamientos.** Cierra el hueco de revocación: «olvidar el
  dispositivo» en Android sólo vale **si todavía tienes el teléfono**; si se perdió, sus
  llaves siguen siendo válidas contra la sonda. Conserva el significado que la doble ya
  tenía —*el acto deliberado e irreversible de esta pantalla*—, así que no hay regla nueva
  que aprender. **NO se anuncia en pantalla**, a propósito: anunciarla invita a probarla «a
  ver qué hace» y a desemparejar el móvil que está funcionando en mitad de una campaña.
  Eso significa que **el manual de campo es el único sitio donde ese gesto existe**, y así
  queda registrado aquí. *(Alternativa razonable si algún día molesta: anunciarlo pero
  exigir dos dobles seguidas.)*
- **Entrar en el estado NO borra nada.** El caso frecuente es *añadir* un teléfono de
  repuesto o rehacer uno que se olvidó del lado de Android; borrar rompería el que **sí**
  funciona, en mitad del campo.

**Y lo que costó tiempo en pruebas reales, anotado para no repetirlo:** el código **no
existe** hasta que un teléfono inicia el emparejamiento. Con `sm_io_cap = DISPLAY_ONLY`
NimBLE **no genera el passkey**: lo pide y espera que la aplicación lo elija, lo muestre y
lo inyecte. Al entrar en la pantalla no hay ningún número, y eso es **correcto** — pero se
interpretó como un fallo y se perdió un buen rato. Por eso la pantalla tiene **tres fases**
(esperando / código / fallo) y por eso el manual lo explica paso a paso. Lo mismo con
**reemparejar: hay que borrar por los dos lados**, o falla de formas confusas.

*(Y un detalle pequeño con consecuencias desproporcionadas: el código se imprime con
`%06lu`, no `%lu`. Un passkey `12345` se teclea como `012345`; imprimir cinco dígitos
haría fallar uno de cada diez emparejamientos, al azar, con un síntoma indistinguible de
haberlo tecleado mal — y se le echaría la culpa al operador.)*

### D-52 · El gate de la app: sin sonda no se elige, pero **Abortar siempre**

**El selector y Arrancar se deshabilitan si la sonda no está lista por BLE.** Es la regla
que hace que la v2 funcione: las dos mitades se fijan **juntas o ninguna**. Si se pudiera
elegir sin la sonda, volvería a existir la posibilidad de que app y sonda corran cosas
distintas.

**Abortar NO depende del BLE. Nunca.** Si el enlace se cae con una corrida en marcha,
tiene que poder cerrarse igualmente la sesión de captura del servidor; lo contrario
dejaría sesiones abiertas sin forma de cerrarlas desde el cerro.

**Cuando el gate está cerrado, la app dice por qué**, con el motivo concreto (sin conectar,
emparejando, en modo emparejar, haciendo el JOIN, firmware incompatible). Un control en
gris **sin explicación**, en campo, se interpreta como que la app está rota — y entonces
el operador reinicia cosas que funcionaban.

Del mismo criterio salen dos comportamientos más: un **aviso previo** al arranque cuando
la sonda está uniéndose o ya corriendo (evita un rechazo que el usuario no podía prever),
y el aviso explícito de «**la corrida sigue en la sonda**» cuando se cae el Bluetooth —
porque la corrida es autónoma y el operador no debe pensar que se le paró el equipo.
**Regla dura relacionada:** al reconectar, la app **re-lee el estado y no reenvía nunca un
comando pendiente**. Mientras el enlace estuvo caído, la corrida siguió; un comando
repetido «por si acaso» podría abortar una corrida que iba bien o arrancar dos veces la
misma. La verdad está en la sonda.

### D-53 · Aviso: la sonda se paró y la sesión sigue abierta

**El desajuste que faltaba, y que en la v1 no se veía en ninguna parte.** Se aborta con el
botón —o la corrida termina— y en el servidor queda una **sesión abierta grabando nada**.
Pasa siempre que se usa el respaldo por botón, con Bluetooth o sin él.

Importa por dos motivos, y el segundo es el que de verdad duele: reintroduce justo la
divergencia que la v2 elimina, y **falsea la duración de la sesión**, que es la ventana
temporal con la que `cruzar.py` acota el cruce contra la microSD.

La app lo detecta porque con el enlace BLE ve el estado de la sonda en el acto, y lo
muestra como banda **no descartable** en el Panel, con un botón *Cerrar sesión* y su
diálogo de confirmación.

**Dos decisiones dentro de este aviso:**

1. **No cierra la sesión sola.** Es el mismo criterio que se aplica cuando no llega el
   ACK: **no destruir nada por inferencia**. Cerrar una sesión no se deshace, y un estado
   leído mal mataría una captura viva.
2. **Sólo avisa si esa sesión llegó a verse corriendo.** Sin esa condición, el aviso
   saltaría en el segundo que va entre abrir la sesión y recibir el primer estado con
   `CORRIENDO` — es decir, en cada arranque, que es la forma más rápida de enseñar a
   ignorarlo.

Su hermano simétrico —**la sonda corre una corrida distinta de la de la sesión**— también
se avisa, y llega **antes** que el aviso de desajuste de fPort porque no depende de que
llegue ningún uplink. El aviso de fPort **no se retira**: ya no debería poder dispararse
por una selección humana, pero sigue cubriendo cualquier otra causa. Una red de seguridad
se quita cuando estorba, no cuando deja de saltar.

### Verificación en hardware

Todo lo de abajo está medido sobre la placa, no estimado.

**Coexistencia BLE + LoRaWAN — el riesgo que podía torcer el plan, cerrado.**

```
24 uplinks con el BLE conectado:   deltas de 8,07 s, sin un solo salto
37 uplinks con el enlace cifrado:  deltas de 8,08 s
```

**Lo que cierra la coexistencia es la cadencia, no el hecho de que transmitiera.** Si
NimBLE estuviera robando CPU o estorbando al planificador del SX1262, saldría aquí como
*jitter*. No hay ninguno. Cero errores, cero panics, cero asserts; NimBLE no vuelve a
escribir en el log tras el arranque.

**Memoria y flash.**

- Tras el JOIN quedan **~211 000 B** de SRAM interna libre, con un **bloque contiguo de
  ~168 000 B**. El bloque mayor importa tanto como el total: la fragmentación mata igual
  que el agotamiento.
- NimBLE cuesta **~59 KB** de SRAM interna.
- **La PSRAM sigue desactivada y no hace falta.** El riesgo que abría el rediseño queda
  cerrado y la sonda conserva su decisión de arranque sin PSRAM.
- Flash: binario ~723 KB sobre la partición `factory` de 3 MB → **77 % libre**.

**Emparejamiento.** `cifrado=1 autenticado=1 bonded=1 llave=16` — los cuatro. Es la prueba
de que hubo **Passkey Entry real y no *Just Works***. Reconexión con el bonding ya hecho:
**270 ms**, sin diálogo y sin código.

**End-to-end.** Elegir **URBANO-C** en la app ⇒ la sonda transmite en **fPort 12**. Es la
prueba que vale, porque el fPort codifica **escenario y clase** a la vez: si las dos
mitades no coincidieran, el número sería otro.

### Documentación

- `docs/MANUAL-DE-CAMPO.md` — reescrito para los dos caminos (app y botón). Incluye el
  **procedimiento de emparejado paso a paso**, con las dos cosas que costaron tiempo en
  pruebas reales bien señalizadas: que **el código aparece durante el emparejamiento, no
  antes**, y que **para reemparejar hay que borrar por los dos lados**. La tabla de gestos
  gana la columna del estado de emparejado, incluido el gesto destructivo que **no está en
  la pantalla y sólo existe aquí**.
- `docs/APP-CAMPO.md` — §1 reescrito (la app **sí** arranca ahora la sonda, y por qué eso
  no reintroduce el control por red), pantalla **Dispositivo (BLE)**, el indicador de la
  barra superior, el gate, y los dos avisos nuevos.
- `docs/CONTRATO-CAMPO.md` — **sin cambios de contrato** (§14 explica por qué: la mitad
  BLE no pasa por el microservicio).
- `firmware/README.md` — el módulo `ble_control`, las opciones de `sdkconfig` y los
  números medidos. `app/README.md` — pantalla nueva, notas del cliente BLE y build.

### Pendiente de la v2

- [ ] **Prueba negativa del CCCD**: con un escáner **sin emparejar**, intentar
      `setNotifyValue(true)` sobre la característica de Estado. El descriptor lo crea
      NimBLE automáticamente y **no damos por sentado** que herede las restricciones
      `_ENC|_AUTHEN` que sí declaramos en las características. Impacto bajo si resultara
      escribible (no es información sensible: quien está a rango ve el OLED), pero es una
      excepción a la invariante y **no está medido**. Se anota como pendiente en vez de
      afirmar algo que no se ha comprobado.
- [ ] La pantalla de **Ayuda** de la app sigue describiendo el flujo de la v1 (elegir
      también en la sonda). No es incorrecta —es literalmente el respaldo— pero ya no es
      el camino normal.
- [ ] Publicar el APK de la v2 (`gh release create`) y las corridas de campo reales con
      el flujo nuevo.

---

## 2026-07-24 — D-54 a D-58 · El JOIN bloqueante deja la sonda sin control (arreglo: join en segundo plano)

La v2 quedó implementada y verificada en placa (entrada del 2026-07-20), pero arrastraba un
**bug propio de la versión**. Al encender, el firmware entraba en un bucle de JOIN LoRaWAN
**bloqueante**: `app_main()` no pasaba del `while(!joined)` hasta cerrar el enlace. Sin
gateway en rango —banco, red caída, gateway apagado— la sonda se quedaba en `JOIN #n…`
**para siempre**, y con `PICARO_FORCE_FRESH_JOIN = 1` (D-41) eso ocurría en **cada arranque
fuera de cobertura**. Mientras duraba, el control por BLE era inalcanzable: un móvil
emparejado reconectaba pero su `Arrancar` se rechazaba (estado `UNIENDO`), y una sonda **sin
bond ni siquiera se podía emparejar**, porque tanto el emparejamiento como el menú vivían
*después* del join.

Es un bug **de la v2**, no una carencia heredada. En la v1 (solo botón) un JOIN bloqueante era
inocuo: no había nada que controlar durante el join. La v2 introduce el control remoto como
premisa, y esa premisa es la que el JOIN bloqueante rompe justo cuando el enlace no cierra.
Además **contradecía dos decisiones de la propia v2**: D-48/RF-8 —«el botón es respaldo
**completo**: navegar, arrancar, abortar y volver al menú, sin app y sin cobertura»— y D-52
—«**Abortar SIEMPRE disponible**, con enlace o sin él»—. Durante el JOIN el botón no hacía
nada de eso, y abortar no estaba disponible por ningún canal.

Estamos a tiempo (campaña: 14–16 ago 2026) y el arreglo es **parte de la v2**, no un
aplazamiento a una v3. El diseño detallado —arbitrio de radio, máquina de estados, análisis de
concurrencia revisado adversarialmente dos veces— vive en los documentos de traspaso
`equipo/CR-v2-join-en-fondo.md` y `equipo/DISENO-JOIN-EN-FONDO.md`, y el delta del contrato en
el Addendum A de `equipo/CONTRATO-BLE.md` (todos locales, no versionados).

### D-54 · C-Fondo: operable desde el arranque, el enlace se adquiere por detrás

**Decisión.** El join deja de gatear el control. El arranque cae de inmediato en un estado
**operable** (`SIN_ENLACE`) que se comporta como el menú —BLE anunciando, emparejamiento
posible, cursor navegable— y una **tarea de join en segundo plano** adquiere el enlace por
detrás. La invariante cambia de «unido ⟹ operable» a «**operable desde el arranque; el enlace
es un recurso que se adquiere, no una precondición del control**».

**Alternativas consideradas.**

- *Opción A — solo interrumpir el bucle* (una pulsación larga rompe el JOIN). Descartada: abre
  una válvula de escape pero **no hace verdad la premisa de la v2** —operar sin enlace—. Buen
  parche, no arreglo.
- *C-perezoso — diferir el join al arranque de la corrida.* Descartada: **pierde el primer
  uplink inmediato** (el join ocurriría al pulsar Arrancar) y **rompe el ACK de 2 s**, porque
  «Arrancar» tardaría un tiempo impredecible en confirmar. Son justo las dos propiedades que la
  v2 conserva.

**Por qué C-Fondo.** Cumple la premisa **y** conserva el uplink inmediato: cuando el operador
selecciona, el join suele estar ya hecho por detrás. El precio es la superficie de concurrencia
(D-55) y re-medir la coexistencia en placa (abajo).

**Restricción física que condiciona el diseño.** «En segundo plano» no es un segundo hilo
transmitiendo a la vez: `activateOTAA()` de RadioLib es bloqueante y atómico, el SX1262 y el
`LoRaWANNode` no son reentrantes, y las ventanas RX del join son críticas en tiempo. Dos tareas
tocando la radio a la vez = join roto. C-Fondo se apoya en que en `SIN_ENLACE`/menú/emparejado
**el bucle principal no toca la radio**: ahí la tarea de join la posee en exclusiva, sin
contención. La única disputa posible sería durante una corrida, y para entonces el join ya está
hecho y la tarea, dormida.

### D-55 · El arbitrio de propiedad de la radio

**Decisión.** La radio (SX1262 + `LoRaWANNode`) tiene **exactamente un dueño** en cada instante,
protegido por un **mutex**. La tarea de join la posee mientras la sonda está ociosa; el bucle
principal, durante la corrida.

**La clave que hace que no haya contención.** La tarea de join **suelta la radio ANTES de marcar
`unido`**, y el bucle solo la toma **DESPUÉS** de observar `unido` (una variable atómica, con
orden release/acquire). Como en ese instante la tarea de join ya soltó y se está autodestruyendo
(`vTaskDelete`), el bucle toma una radio **libre**: las dos tareas **nunca quieren el mutex a la
vez**. La tarea suelta además tras **cada intento** —no retiene la radio a través del backoff—,
así que si el operador arranca justo durante un `activateOTAA`, el peor caso es una espera
**acotada** de pocos segundos.

**Alternativa descartada.** La primera versión del diseño apelaba a la **herencia de prioridad**
del mutex para evitar que la tarea de join (prioridad baja) bloqueara al bucle. La revisión
adversarial lo desmontó: era **falso** (el bucle es de *menor* prioridad que la tarea de join,
no puede heredarla) e **innecesario**, porque la invariante «soltar precede a unido» ya garantiza
cero contención. Se eliminó la señal de preferencia `s_ceder_radio` como código muerto. El mutex
se queda solo para **afirmar dueño único** —un assert que caza cualquier doble-dueño en pruebas—
y aportar la barrera de memoria del traspaso.

**Por qué es seguro compartir el objeto `node`.** Las dos tareas lo tocan, pero **nunca a la
vez** (lo garantiza el mutex), y `unido` gatea que el bucle no transmita antes de que la sesión
sea válida. Un solo lock, sin orden de locks que violar —la radio LoRa no comparte bus con nada:
SD e IMU en otro SPI, OLED en I2C, BLE en la radio interna del S3— ⇒ no hay deadlock por orden.

### D-56 · Estados nuevos: `SIN_ENLACE` y `ESPERANDO_ENLACE`; `UNIENDO` retirado

**Decisión.** Se añaden dos valores al byte `estado` del contrato BLE:

| Valor | Estado | Significado |
|---|---|---|
| `0x06` | **`SIN_ENLACE`** | Menú operable, enlace LoRa **aún no** adquirido; la tarea de join reintenta por detrás |
| `0x07` | **`ESPERANDO_ENLACE`** | Se seleccionó una corrida sin enlace; arrancará en cuanto una la tarea de join. Abortar disponible |

y **`UNIENDO = 0x04` queda RETIRADO** —esta versión no lo emite nunca, y no se reutiliza—.
`CONFIG = 0x00` pasa a significar «menú operable **con** enlace ya adquirido»; la transición
`SIN_ENLACE → CONFIG` la hace la sonda **sola** al unir.

**Por qué un valor nuevo y no redefinir `UNIENDO`.** Mismo criterio que los UUIDs retirados del
contrato: un identificador retirado que nunca se reutiliza hace que una implementación
desactualizada **falle en voz alta** en vez de interpretar en silencio un estado por otro. Y
`ESPERANDO_ENLACE` no es un estado inventado de más: es el **reflejo directo** de haber elegido
la espera abortable (D-57), que necesita un estado publicado propio para que la app y el OLED lo
rendericen sin ambigüedad.

### D-57 · Seleccionar sin enlace: espera acotada y abortable (D2)

**Decisión.** `seleccionar(m)` estando en `SIN_ENLACE` **no se rechaza**. Fija la selección y
entra en `ESPERANDO_ENLACE`: el OLED muestra los segundos y la corrida arranca **sola** en cuanto
la tarea de join une. **Abortar está siempre disponible** durante la espera (larga en el botón, o
el botón Abortar de la app), y **nunca se bloquea en mudo** —el bug que se arregla—. El bucle
**no compite por la radio** durante la espera: solo sondea `unido`, para no congelar el
`activateOTAA` que precisamente va a unir.

**Alternativa considerada.** *Rechazar `seleccionar` hasta que haya enlace* (como hacía
`UNIENDO`). Descartada: obliga al operador a reintentar y reintroduce, por otra puerta, la
indisponibilidad que este arreglo elimina. La espera abortable cierra D-52 «de verdad»: abortar
funciona también **antes** de que exista el enlace.

**Consecuencia en el lado app: el gate se invierte.** El selector y `Arrancar` dejan de exigir
enlace LoRa —se habilitan también en `SIN_ENLACE`— y el enlace LoRa pasa a mostrarse como
**indicador aparte** («uniendo…» / «unida»), no como bloqueo. Lo que **sigue** gateando el
selector es el enlace **BLE seguro** con la sonda: sin él no se pueden fijar las dos mitades
juntas (D-52). `CORRIENDO` sigue siendo el ACK fiable de «hay corrida real transmitiendo»,
porque durante la espera la sonda publica `ESPERANDO_ENLACE`, no `CORRIENDO`; y el ACK de 2 s de
la v2 se conserva en el caso normal (ya unida al seleccionar).

### D-58 · Se acepta que esta corrección cambia el contrato BLE

**Decisión.** La v2 declaraba «la mitad BLE no cambia el contrato». Esta corrección lo cambia
—dos estados nuevos, uno retirado, la tabla de aceptación de comandos y el gate de la app— y esa
afirmación **se revierte y se documenta** (Addendum A del contrato).

**Por qué se puede.** No hay firmware desplegado contra la versión previa del contrato, así que
**no hay nada que versionar**: el byte `ver` sigue en `0x01`, mismo criterio que se aplicó al
rehacer el contrato por la decisión I (D-49). Firmware y app se implementan contra el addendum
congelado, sin hablarse, igual que el resto del contrato.

### Riesgo pendiente y verificación en placa

**Riesgo P4, a medir explícitamente.** NimBLE corre a prioridad muy alta (≈ 21) frente a la
tarea de join (2–3) y **puede expropiarla en su ventana RX** (RX1 ≈ 5 s, RX2 ≈ 6 s),
haciéndole perder el JoinAccept. El caso a medir es el **primer arranque con un móvil
emparejándose (SMP) concurrente con un `activateOTAA`**: hay que confirmar que el join termina
uniendo aun con emparejamiento simultáneo. La coexistencia medida en la v2 (8,07 s clavados) fue
con BLE **ya conectado y sin join concurrente**, así que **no cubrió** este tercer actor. Por eso
la decisión D3 de la CR quedó cerrada como «re-medir coexistencia».

**Estado.** El firmware **compila limpio** (ESP-IDF v5.5.2, sin avisos nuevos). Binario
~709 KB sobre la partición `factory` de 3 MB, **77 % libre**; C-Fondo añade ~3 KB. La memoria
(RNF-B2: ≥ 180 000 B libres y ≥ 140 000 B de bloque contiguo tras el JOIN, **incluido el stack
de la tarea de join**) y la coexistencia con la tarea viva **se miden en placa**: la verificación
en hardware queda **pendiente**. Y, como enseñó la sesión del 2026-07-19, «compila» y «funciona
en el dispositivo» son afirmaciones distintas —no se dará por buena hasta flashear—.

### Verificación en placa — 2026-07-24 (Fase E) y sub-arreglo D-59

Flasheado en la T-Beam (ESP-IDF v5.5.2, COM18) y capturado el arranque con `idf.py monitor`. Lo
**no-interactivo queda verificado en hardware**, cerrando el «pendiente» de arriba salvo lo que
exige a una persona:

- **El bug está muerto.** El menú operable aparece a **1 332 ms** y el join no cierra hasta
  **6 904 ms**: 5,5 s en los que la sonda es plenamente operable mientras une por detrás. La tarea
  de join **adquiere el enlace y se autodestruye**, exactamente como el diseño.
- **RNF-B2 PASA:** con la tarea de join viva, **204 244 B libres** (≥ 180 000) y bloque mayor
  **163 840 B** (≥ 140 000). BLE anuncia `PICARO-CAMPO` desde el arranque. Cero panics, cero
  asserts (el de dueño único de la radio no saltó).
- **El caso sin cobertura, visto sin querer:** en una sesión el join falló **43 veces (~15 min)**
  sin unir y la sonda **siguió operable todo el rato** — justo lo que en el firmware viejo habría
  sido un cuelgue de 15 min. *(Aparte: conviene revisar por qué el gateway no aceptaba los join en
  ese rato, antes de la campaña.)*

**Sub-arreglo D-59, hallado en la Fase E interactiva.** Al abortar con el botón una corrida que
estaba en `ESPERANDO_ENLACE`, **la app no se enteraba**: la sonda volvía al menú **sin publicar
`ABORTADA`**, y el aviso de sonda parada (D-53) solo se armaba si la corrida había llegado a verse
`CORRIENDO` —cosa que una corrida que nunca unió jamás hace—. La sesión quedaba **huérfana**: la
misma divergencia que la v2 existe para eliminar, colándose por la puerta del estado nuevo. Se
corrige en dos mitades: el **firmware** publica `ABORTADA` también al abortar la espera; la **app**
cuenta `ESPERANDO_ENLACE` como corrida viva para el aviso. **Verificado end-to-end con el móvil
real:** la banda *Cerrar sesión* aparece y cierra la sesión. Es un bug que **solo la prueba
interactiva podía destapar** —compilar, arrancar y flashear no lo tocan—.

**Pendiente de Fase E (exige operador):** emparejar un móvil nuevo, el **test P4** (emparejar
concurrente con el join en su ventana RX), los gestos del botón, y el end-to-end completo
(corrida → fPort correcto → uplinks en la app).

### Documentación

- `docs/MANUAL-DE-CAMPO.md` — el arranque ya no se cuelga en `JOIN…`: la sonda es operable de
  inmediato, el menú muestra el indicador de enlace (`Enlace: uniendo…` / `Enlace: OK`) y, si se
  arranca sin enlace, aparece la pantalla `ESPERANDO ENLACE` (arranca sola al unir; larga =
  abortar). Actualizados §2, §5, §7 y la tabla de diagnóstico.
- `docs/APP-CAMPO.md` — el gate del selector deja de exigir enlace LoRa (se muestra aparte); se
  describe el estado «esperando enlace» y se retira `UNIENDO` de los estados de la sonda; Abortar
  sigue siempre disponible.
- Detalle técnico completo (arbitrio, primitivas, handoff, análisis de deadlock/starvation) en
  los documentos de `equipo/` (locales) y en el Addendum A del contrato.

---

## 2026-08-29 — Cierre de A-03 y A-05 · Fresnel verificado con el perfil real: el enlace al cerro está despejado

**Veredicto: hay línea de vista con el 60 % de la primera zona de Fresnel
despejado en todo el trayecto.** Verificado contra el perfil de elevación real
(SRTM 30 m vía OpenTopoData, 90 puntos cada ~172 m). No hay obstrucción de
terreno entre el gateway y el cerro. H5 no tiene amenaza geométrica.

### Datos reales (medidos en sitio, sustituyen a los estimados)

| Magnitud | Bitácora (estimado) | Real (2026-08-29) |
|---|---|---|
| Gateway — coordenadas | 21.92, -102.27 (redondeada) | **21.92, -102.27** (redondeada) |
| Gateway — terreno | 2000 m (curva de nivel) | **1914 msnm** (antena a +15,5 m ⇒ 1929,5) |
| Cerro — coordenadas | 21.874164, -102.424828 | **21.8842552, -102.4173135** (punto real de operación) |
| Cerro — terreno | 2400 m | **2250 msnm** (sonda a +1,5 m ⇒ 2251,5) |
| Distancia | 16,35 km | **15,266 km** (haversine) |

La sospecha de A-05 era correcta: los 2000 m del gateway estaban inflados 86 m.
El SRTM devuelve **exactamente 1914 m** sobre la coordenada del gateway, lo que
de paso valida el dataset contra la medición en sitio. El nombre **CERRO16** y
sus fPort **se conservan** aunque la distancia real sea 15,27 km: renombrar a
estas alturas rompería la trazabilidad de corridas y codec por una etiqueta.

### Geometría recalculada (915 MHz, k = 4/3)

| Magnitud | Punto medio (7,63 km) |
|---|---|
| Radio 1.ª zona de Fresnel r1 | 35,4 m |
| Despeje recomendado (60 %) | 21,2 m |
| Abombamiento terrestre | 3,4 m |
| Línea de vista | 2090,5 m |
| Terreno máx. admisible | ≈ 2066 m |
| Terreno real | ~1890 m ⇒ **margen ~178 m** |

Con la distancia real el presupuesto mejora una pizca: FSPL 115,3 dB (−0,6 dB),
**margen SF10 ≈ 44,2 dB**. Sigue sin ser el factor limitante; nunca lo fue.

### El perfil, punto a punto

`analisis/perfil_elevacion.csv` — 90 puntos con terreno, línea de vista, r1,
despeje requerido (0,6·r1 + abombamiento), techo admisible y margen. Lectura:

- **El punto más ajustado del trayecto está a 340 m del gateway** (km 0,34;
  21.92, -102.28): terreno 1907 m, techo admisible 1930,1 m, **margen
  +23,1 m**. Es el entorno urbano inmediato al gateway: un edificio de más de
  ~23 m (7–8 plantas) en ese azimut invadiría la zona. A ojo no lo hay, pero es
  el único sitio del trayecto donde la geometría depende de lo construido y no
  del terreno.
- Del km 1 en adelante el margen crece de +44 m a **+150…+300 m** durante todo
  el valle: la línea de vista sube hacia el cerro mientras el terreno baja a
  ~1870–1890 m. Ahí no hay nada que discutir.
- **La aproximación final al cerro es una ladera limpia**: a 170 m de la cima
  el terreno (2202 m) aún despeja el techo admisible por +41 m. La zona de
  Fresnel se cierra sobre la sonda sin rozar la ladera.
- *Nota de dato:* el SRTM da 2269 m en la coordenada exacta de la cima frente a
  los 2250 m medidos (19 m, dentro del error típico del SRTM en picos). Es una
  discrepancia de dato en el punto donde está la sonda, no una obstrucción — si
  la cima real fuese más alta, la sonda sube con ella y los márgenes del
  trayecto solo mejoran.

**Método:** perfil interpolado linealmente entre las dos coordenadas; elevación
SRTM 30 m (OpenTopoData `srtm30m`, JSON crudo conservado en scratchpad);
r1 = √(λ·d1·d2/d) con λ = c/915 MHz; abombamiento = d1·d2/(2·k·Re), k = 4/3.

**Efecto sobre la campaña:** ninguna acción. La corrida del cerro (pendiente:
la CERRO16-A del 21/08 fue de banco) puede salir a campo sin reserva geométrica.
Si aun así el PDR cayese por debajo del criterio del 50 %, la causa habrá que
buscarla en desvanecimiento, interferencia o instalación — no en el terreno.

**Documentación tocada:** tabla de cuestiones abiertas (A-03 y A-05 cerradas),
§9.5 de `docs/EXPERIMENTO.md` (nota de revisión; la tabla de 2026-07-19 queda
marcada como superada), `analisis/perfil_elevacion.csv` (nuevo).

---

## 2026-08-29 — D-60, D-61 · Los dos fixes de los downlinks perdidos: gate de clase y ping ligado a sesión

Aplicación en el microservicio de los dos arreglos que salen del diagnóstico de
la campaña (fallos A y B del análisis de downlinks): **ningún** downlink llegó a
la corrida de Clase A (0/764) y **ningún** ping automático se envió en toda la
campaña. Solo código local del microservicio, contrato (v1.3, §15) y tests; el
firmware lleva su arreglo por separado y el despliegue a `campo.pi-caro.org`
queda pendiente de autorización.

### D-60 · Gate de clase en `start`: la sesión no se abre con la clase desajustada

**Decisión.** `POST /session/start`, después de conmutar el device profile, lee
del API de ChirpStack la **clase efectiva** del device (`classEnabled` en el
`GET /api/devices/{devEui}`, hermano de `device` y `deviceStatus`) y la compara
con la clase de la corrida. Si no coincide, la sesión **se rechaza con 409** y
un `detail` accionable: «clase desajustada: … el perfil ya quedó puesto: apaga y
enciende la sonda para que haga un JOIN nuevo y vuelve a arrancar». Por el
WebSocket sale además `warning {kind:"class_mismatch", expected, got}`. Si el
servidor no expone el campo (ChirpStack < 4.6), la sesión se abre con
`warning {kind:"class_unverified"}` — bloquear ahí dejaría la campaña sin poder
arrancar.

**Por qué.** ChirpStack v4 **congela** la clase operativa (`enabled_class`) del
device en el momento del JOIN OTAA según el perfil activo entonces, y el
`PUT /api/devices` con que `start` conmuta el perfil **no la actualiza** (issue
[#360](https://github.com/chirpstack/chirpstack/issues/360) de ChirpStack).
Como la sonda hace su único join al encender (`FORCE_FRESH_JOIN`, D-41),
normalmente **antes** de abrir la sesión, el servidor opera con la clase de la
corrida **anterior**: en campo, la Clase A recibió **0/764** downlinks (el
servidor la creía C y transmitía por RX2 a una sonda sorda) y los desajustes
inversos entregan pero miden la latencia equivocada — H4 inválida en ambos
sentidos.

**Alternativas consideradas.**

- *Abrir la sesión con un aviso «clase desajustada» y dejar medir.* Descartada:
  el gate existe precisamente para que una corrida no mida con la clase
  equivocada; con solo un aviso, la banda puede pasar desapercibida en campo
  (sol, prisa) y se repetiría el 0/764 con cara de corrida válida. Además el
  rechazo es **auto-corregible**: el perfil bueno ya quedó puesto por el propio
  `start`, así que apagar/encender la sonda congela la clase correcta y el
  siguiente `start` entra sin más.
- *Re-encolar el JOIN o forzar la clase desde el API.* No existe: la clase
  efectiva no es escribible por el API (ese es justamente el issue #360); la
  única palanca real es un join nuevo, y esa la tiene el operador con el botón
  de encendido.
- *Que el microservicio conmute el perfil ANTES de que la sonda encienda.* Es el
  orden correcto de operación (§12.10) pero no un gate: depende de disciplina
  humana, que es exactamente lo que falló. El gate convierte la disciplina en
  invariante.

### D-61 · El ping de latencia vive en el microservicio, ligado a la sesión

**Decisión.** Se retira el pinger suelto (`servidor/pinger.py` queda **marcado
obsoleto**, no borrado) y su función pasa al microservicio: mientras una sesión
está `capturing`, una **tarea asyncio ligada a la sesión** encola un ping fPort
98 (1 byte = secuencia, no confirmado) cada `PING_INTERVAL_S` (60 s por defecto,
configurable), por el **mismo camino** y con la **misma secuencia** 1..255 que
el `/ping` manual. Cada envío —manual o automático— se **persiste** en la tabla
nueva `downlinks` (`session_id, seq, fport, ts, iso, origin`) y se exporta como
`GET /sessions/{id}/downlinks` (JSON) y `GET /sessions/{id}/downlinks/csv`
(`<run_label>_dl.csv`), hermano del CSV de uplinks. La tarea **muere con la
sesión** (finish/abort/auto-finish) y con el apagado del servicio; un fallo de
ChirpStack en un tick no la tumba (reintenta al siguiente).

**Por qué.** El pinger automático de la campaña era un proceso `nohup` aparte y
**no envió nada en absoluto**: `downlinks_enviados.csv` quedó como el
placeholder del 19/07 y en los `_dl.csv` de la microSD no hay un solo ping con
cadencia de 60 s. Un proceso suelto falla en silencio y nadie lo nota hasta el
análisis. El `/ping` manual del microservicio, en cambio, **sí funcionó** — la
conclusión es que el camino bueno ya existía y lo que faltaba era atarle la
cadencia a la única señal fiable de «hay corrida en marcha»: la sesión de
captura. De paso, persistir cada envío en la misma SQLite da por fin el lado
«enviado» del cruce enviados/recibidos, que en la campaña no existió.

**Alternativas consideradas.**

- *Arreglar y supervisar el pinger suelto (systemd, healthcheck).* Descartada:
  seguiría siendo un segundo proceso con su propia detección de corrida por
  silencio de MQTT (frágil: fue el mecanismo que falló mudo), su propio CSV
  fuera de la SQLite y su propia secuencia — duplicando lo que la sesión ya
  sabe con certeza.
- *Hilo `threading` en vez de tarea asyncio.* Descartada: el microservicio ya
  ata su ciclo de vida al event loop de FastAPI (lifespan, `run_coroutine_
  threadsafe` del hub); una tarea asyncio se cancela limpia al cerrar la sesión
  y al apagar el servicio, sin joins de hilos a mano. El encolado HTTP, que es
  bloqueante, sale por `asyncio.to_thread` para no congelar el loop.
- *Secuencia propia para el automático.* Descartada: la sonda registra un único
  flujo de pings en la microSD; dos secuencias entrelazadas en el mismo fPort
  harían ambiguo el cruce por `(run, seq)`. Compartir la secuencia con el
  manual (reiniciada en `start`, como ya hacía) mantiene el cruce unívoco.

**Verificación.** Suite del microservicio: **46 passed** (36 existentes + 10
nuevos: gate por API y por unidad, clase no verificable, secuencia compartida y
persistencia manual/auto, ciclo automático con intervalo inyectado que dispara,
persiste y muere con la sesión, export JSON/CSV de enviados, 404s). El ciclo
automático se prueba con `PING_INTERVAL_S` de 50 ms inyectado — sin dormir 60 s.

**Documentación tocada:** `docs/CONTRATO-CAMPO.md` → **v1.3** (§15, más filas
nuevas en §6/§7/§8), cabecera de `servidor/pinger.py` (obsoleto),
`microservicio/README.md` y `.env.example` (`PING_INTERVAL_S`), tabla de
decisiones vigentes (D-60, D-61).

**Pendiente (requiere autorización):** redesplegar el microservicio en
`campo.pi-caro.org` (imagen nueva + `PING_INTERVAL_S` en el `.env`; la tabla
`downlinks` se crea sola en el arranque) y matar el `nohup` del pinger viejo si
siguiera vivo.

---

## 2026-08-29 — D-62 · Re-join por BLE: el remedio al gate de clase (D-60) que no apaga la sonda

El gate de D-60 rechaza con 409 una sesión cuya clase no coincide con la que ChirpStack
tiene congelada desde el último JOIN (issue #360 de ChirpStack: la clase efectiva se fija
en el JOIN OTAA según el perfil activo entonces, y un `PUT` de perfil posterior **no** la
actualiza). Efecto medido en la Serie 1 (16–21 ago 2026): Clase A recibió **0 downlinks en
764 uplinks** — el servidor la creía Clase C y transmitía por RX2 a una sonda que solo
escuchaba RX1/RX2 de verdad como Clase A —, y los desajustes en el sentido inverso
entregan pero miden la latencia de la clase equivocada, invalidando H4 en ambos sentidos.
El microservicio ya rechaza ese caso con 409 (D-60); lo que faltaba era **qué hacer** con
el rechazo.

El 409 es **auto-corregible del lado servidor**: el perfil correcto ya quedó puesto por el
propio `start` antes de comparar. Lo único que falta es que la sonda **rehaga el join**
para que ChirpStack congele la clase nueva. Como la sonda hace su único join al encender
(`FORCE_FRESH_JOIN`, D-41) — normalmente **antes** de que el operador arranque la sesión
en la app —, el remedio inicial era apagar y encender. Se descarta: cambiar de Clase A↔C
es el caso de uso **central** de la app (D-07, D-48), y un power-cycle manual reintroduce
exactamente el error humano que la v2 vino a eliminar.

### D-62 · Comando de re-join por BLE

**Decisión.** Se añade un tercer opcode a la característica `Comando` del contrato BLE:
`op = 0x03` (re-join), misma trama fija de 2 bytes que ya usan `seleccionar` y `abortar`.
Al recibirlo con la sonda en `CONFIG`/`SIN_ENLACE`, el firmware descarta la sesión LoRaWAN
activa (`clearSession()` de RadioLib + el blob de sesión en NVS a ceros, **conservando los
nonces**: el `DevNonce` tiene que seguir creciendo o el servidor rechazaría el
`JoinRequest` siguiente como repetido) y relanza el join OTAA en la tarea de segundo plano
de C-Fondo (D-54). La app, al recibir el 409 —que ya dejó el perfil correcto puesto—,
ordena el re-join por BLE y reintenta el arranque sola cuando la sonda vuelve a `CONFIG`.
Sin que el operador apague nada. Detalle completo del contrato: Addendum B de
`equipo/CONTRATO-BLE.md`.

**Alternativas consideradas.**

- *Power-cycle manual, como remedio permanente.* Descartada por instrucción directa: el
  cambio de clase A↔C es la razón de ser de la app (D-07), y pedirle al operador que apague
  y encienda la sonda cada vez que cambia de clase reintroduce en primera persona el error
  que la v2 existe para eliminar — la propia coordinación humana entre sonda y servidor.
- *Que la sonda decida sola rehacer el join al detectar un cambio de clase.* Descartada: la
  sonda **no tiene ninguna forma de saber** cuál es la clase efectiva del servidor —eso
  vive en ChirpStack, congelado desde el último JOIN— así que no hay ninguna señal propia
  que la sonda pueda observar para disparar el re-join por su cuenta. El 409 del
  microservicio (D-60) es la **única señal autoritativa** de que hay un desajuste, y esa
  señal solo la ve la app.
- *Reordenar el arranque para que el join ocurra después de conmutar el perfil.* Descartada:
  el join es **al encender** (D-41, `FORCE_FRESH_JOIN`) y no se puede posponer sin dejar la
  sonda inoperable mientras tanto — contradiría directamente C-Fondo/D-54, que existe
  precisamente para que la sonda sea operable desde el arranque sin depender de cuándo cierra
  el join.

**Por qué un comando BLE nuevo y no una de las anteriores.** Es la única opción que junta
las tres propiedades que hacen falta: usa la única señal fiable que existe (el 409), no
exige presencia física de nadie en la sonda, y no toca el orden de arranque que C-Fondo ya
fijó. Añadir un opcode es además **compatible hacia atrás**: el byte `ver` sigue en `0x01`
(mismo criterio que los Addenda anteriores del contrato) y un firmware que no lo conozca
responde `ATT 0x83` / `ult_cmd = PARAMETRO` en vez de fallar en silencio — la señal exacta
con la que la app detecta que en esa sonda solo queda el remedio manual.

**Consecuencias.**

- **Contrato BLE.** Addendum B de `equipo/CONTRATO-BLE.md`: opcode nuevo en §4.2, aceptación
  restringida a `CONFIG`(0x00)/`SIN_ENLACE`(0x06) —en cualquier otro estado, `ATT 0x84`—, sin
  valores nuevos de `ult_cmd` ni de error ATT (reutiliza los que ya había). No se emite
  `UNIENDO` (retirado, Addendum A): la sonda pasa por `SIN_ENLACE` y vuelve a `CONFIG`.
- **`lorawan_esta_unido()` deja de ser monótona.** Hasta D-62, una vez unida no volvía a
  `false`. Con el re-join sí: se pone a `false` al aceptar la petición y vuelve a `true`
  cuando el join nuevo completa. La nota `MENOR-5-2p` de Addendum A.3, que daba la monotonía
  por cierta para descartar una rama de su tabla como inalcanzable, queda **corregida** en
  Addendum B.4: la rama sigue siendo inalcanzable, pero porque `re-join` está prohibido en
  `FINALIZADA`/`ABORTADA`, no porque la función sea monótona.
- **El botón no gana gesto.** Su respaldo para esto sigue siendo apagar y encender, que logra
  lo mismo. No hace falta enseñarle un gesto nuevo a quien opera con el botón.
- **Garantías de concurrencia, sin ampliar la superficie de D-55.** Nunca hay dos tareas de
  join ni dos joins a la vez; una petición que llega mientras la tarea de fondo está
  terminando no se pierde (misma sección crítica que decide "morir o seguir"); llamadas
  repetidas colapsan en un único re-join; la sesión se descarta dentro de la tarea, con la
  radio ya en propiedad — el mutex D-55 no necesita ninguna excepción nueva.
- **Coreografía de la app, señalada y no cerrada aquí.** Si el 409 llega con la sonda en
  `FINALIZADA`/`ABORTADA` (encadenar una corrida sin pasar por el menú), el re-join no es
  directamente aplicable en ese estado: hace falta pasar antes por `CONFIG`/`SIN_ENLACE`. Es
  un detalle de orquestación del lado app, no del contrato, y queda anotado en Addendum B.2
  para quien la implemente.

**Documentación tocada:** `equipo/CONTRATO-BLE.md` → Addendum B (§4.2, aceptación por
estado, `ult_cmd`/ATT sin cambios, garantías de concurrencia, corrección a la nota
`MENOR-5-2p` de Addendum A.3) y §13 Referencias; tabla de decisiones vigentes (D-62);
`docs/MANUAL-DE-CAMPO.md` (§7, el arranque al cambiar de clase) y `docs/APP-CAMPO.md` (§3,
la misma nota del lado app). Firmware ya implementado y compilando —
`firmware/main/ble_control.c`, `firmware/main/lorawan.{h,cpp}`,
`firmware/main/app_main.cpp`, `firmware/main/escenarios.{c,h}` — verificado por lectura de
código, no en placa: la verificación en hardware queda pendiente, igual que el resto de
D-60/D-61.

---

## 2026-08-29 — D-63 · «Marcar finalizada» también para la sonda: sonda primero, servidor siempre

**Qué pasaba.** Bug reportado tras probar en campo el mismo día: al dar una corrida por
finalizada desde la app, la sonda **no se enteraba** y seguía transmitiendo. El operador
tenía que pararla a mano con pulsación larga del botón BOOT.

La causa estaba en el propio código, no en un descuido puntual: el botón **Marcar
finalizada** del Panel (`app/lib/screens/panel.dart`, dentro del bloque `if (capturing)`)
llamaba a `AppState.finishSession()`, que solo cerraba la sesión en el servidor. Su
comentario lo decía literalmente: «No toca la sonda: "marcar finalizada" es un gesto de
contabilidad del servidor, y la sonda se finaliza sola al llegar a `target_uplinks`». Era
coherente con el diseño original —la sonda se autofinaliza a los 300 uplinks (D-38) y el
microservicio autocierra la sesión al llegar el `fCnt` a `target_uplinks` (§3 de
`CONTRATO-CAMPO.md`)— pero el botón aparece **durante** la corrida y su nombre se lee como
«terminar la corrida», así que en la práctica cerraba solo una de las dos mitades.
Consecuencia: sonda transmitiendo sin ninguna sesión que la capture — uplinks huérfanos,
batería gastada, y el `fCnt` de la corrida siguiente contaminado.

El PDR bajo de la Serie 1 (D-60/D-61) hace este caso **más frecuente**, no una rareza: si
el servidor recibe menos uplinks de los que la sonda envía, la autofinalización por
`target_uplinks` no llega a dispararse nunca del lado servidor, y el operador acaba
buscando ese botón para cerrar una corrida que la sonda sigue transmitiendo.

### D-63 · Marcar finalizada: sonda primero, servidor siempre

**Decisión.** El botón consulta el estado BLE de la sonda antes de actuar
(`AppState.sondaSigueCorriendo`, getter nuevo sobre el mismo `_corridaViva` de D-53/D-59:
`CORRIENDO` o `ESPERANDO_ENLACE`). Si la sonda sigue viva, pide confirmación con un
diálogo — «La sonda sigue corriendo… ¿Paro también la sonda?» / **«Parar y finalizar»** —;
si el operador cancela, no se cierra nada. Al confirmar, `AppState.finalizarFundido()`
aplica el **mismo orden y motivo que abortar** (RF-5, decisión G — §10.5 de
`equipo/CONTRATO-BLE.md`): **sonda primero, servidor siempre**, porque lo urgente es que
deje de transmitir y es lo único que se resuelve sin red. Manda el comando BLE de parada
(`op = 0x02`, el mismo de `abortar()`) y **luego** cierra la sesión como `finish`. Si la
sonda ya había terminado sola, no se le manda nada por BLE: solo se cierra la sesión — el
caso para el que nació el botón. Si la sonda no confirma la parada (sin Bluetooth, o
rechazo), la sesión se cierra igual pero se avisa sin rodeos: «Sesión finalizada, pero la
sonda NO confirmó la parada… Párala con el botón: pulsación larga». Y si falla el cierre
del lado servidor después de haber parado la sonda, queda un aviso persistente de que la
sesión sigue abierta.

**Alternativas consideradas.**

- *Redirigir el botón a Abortar cuando la sonda sigue corriendo.* La corrida quedaría
  registrada como `ABORTADA`, que es honestamente lo que sería, y habría un único botón que
  para la sonda en cualquier circunstancia. Descartada por instrucción directa: el operador
  quiere resolverlo en **un solo gesto desde donde ya está** — pulsa «Marcar finalizada»
  porque para él la corrida **terminó**, no se abortó, y desviarlo a otro botón con otro
  nombre en mitad del flujo es justo la fricción que este fix vino a quitar.
- *Ocultar el botón mientras la corrida sigue en marcha.* Es el cambio más pequeño posible
  —ni diálogo nuevo, ni llamada BLE adicional— pero deja al operador **sin ningún atajo**
  justo cuando más lo necesita: sonda transmitiendo con menos uplinks recibidos que
  enviados por el PDR bajo del cerro, que es exactamente el escenario que dispara el bug.
  Ocultar el botón no arregla nada, solo esconde el síntoma y devuelve al operador a la
  pulsación larga como único camino.

**Por qué esta y no las anteriores.** Es la única que cierra las dos mitades desde el
mismo gesto que el operador ya identifica con ese nombre, sin inventar un botón nuevo ni
forzar un vocabulario («Abortar») que no describe lo que pasó cuando la corrida sí llegó a
su objetivo pero el servidor no se enteró por el PDR. Reutiliza además el mismo comando BLE
y el mismo orden que Abortar (decisión G): no hay superficie nueva en el contrato BLE, solo
un segundo llamador del mismo `op = 0x02`.

**Limitación aceptada.** Una corrida cortada así queda registrada como **`finished`**
aunque no llegara a `target_uplinks` — es decir, parcial. Tensión directa con **D-29**
(«corrida incompleta: marcar parcial y repetir»): D-63 no introduce un estado `parcial`
propio, cierra como `finished` igual que una corrida completa. El análisis puede
distinguirla de todos modos, porque su cuenta de uplinks recibidos se queda corta frente a
`target_uplinks` en el CSV/`summary` de la sesión — pero eso hay que **saberlo al leer los
resultados**: el estado de la sesión (`finished`/`aborted`) deja de ser, por sí solo, un
indicador fiable de que la corrida corrió completa. Aceptada conscientemente por el
usuario, con el mismo criterio que motiva D-29: lo que importa es que el dato de
completitud **exista y sea consultable**, no que viva en el campo `state`.

**Documentación tocada:** tabla de decisiones vigentes (D-63) y esta entrada;
`docs/MANUAL-DE-CAMPO.md` (§10, cerrar una corrida desde la app) y `docs/APP-CAMPO.md`
(§5, pantalla ① Panel). `docs/CONTRATO-CAMPO.md` **no cambia**: el endpoint
`POST /session/{id}/finish` es el mismo de siempre — la app simplemente lo llama después de
un paso BLE que ya queda fuera de ese contrato (§14, «la segunda mitad de la app»).
Código ya implementado: `app/lib/app_state.dart` (`finalizarFundido`, `sondaSigueCorriendo`)
y `app/lib/screens/panel.dart` (botón «Marcar finalizada»); no usa ningún opcode BLE nuevo.

---

## 2026-08-29 — A-09 · El déficit de RF no es una avería: es un sector ciego al oeste

**Hecho.** Cuatro medidas estáticas alrededor del gateway, con antena Semtech
marcada **US915** (queda descartada la banda como causa), 30–35 uplinks cada
una. **Las cuatro recibieron el 100 % de los uplinks, sin un solo hueco.**

| Punto | Distancia | Azimut | RSSI | Déficit |
|---|---|---|---|---|
| banco 30-ago | 229 m | 111° (ESE) | −72,2 dBm | **−22,8 dB** |
| banco A-2 | 93 m | 325° (NO) | −71,1 dBm | −29,6 dB |
| banco A-4 | 308 m | 233° (SO) | −89,3 dBm | −37,3 dB |
| banco A-3 | 260 m | 289° (ONO) | −101,4 dBm | **−50,9 dB** |
| TERRAZA (Serie 1) | 2,74 km | 299° (ONO) | −116,5 dBm | −45,6 dB |

**Qué se concluye.** El déficit **no es constante**: dos puntos a distancia casi
idéntica (229 m al ESE y 260 m al ONO) difieren en **28 dB**. Eso descarta la
avería fija —un conector malo o un transmisor flojo perderían lo mismo en todas
las direcciones— y señala al **extremo del gateway**: el déficit depende del
rumbo, no de la sonda, y se mantiene igual a 260 m que a 2,74 km dentro del
mismo sector.

**Por qué importa tanto.** El Cerro del Muerto está a **254° (OSO)** desde el
gateway, es decir, **dentro del sector malo**. La campaña se planificó apuntando
justo hacia donde el gateway oye peor, y eso explica los ceros de las dos
corridas de CERRO16 mejor que cualquier hipótesis sobre el terreno — que está
despejado (A-03, cerrada con el perfil real).

**Corrección de una conclusión anterior.** El análisis del cruce de PDR
(2026-08-29, mañana) afirmó que un déficit de ~50 dB «no puede ser propagación»
a 150 m y apuntaba a la cadena de RF. Era demasiado tajante: el argumento
asumía línea de vista, y en el sector este el mismo equipo pierde la mitad. La
medida por azimut es la que separa las dos explicaciones, y no se tenía.

**Qué queda por hacer.** Subir a la azotea, ponerse a la altura de la antena y
mirar al OSO (254°, hacia el cerro). La sospecha principal es el **tinaco sobre
cuya base está montado el mástil**: lleno de agua es opaco a 915 MHz y, si queda
al oeste de la antena, apantalla exactamente ese sector. La corrección será
mecánica (subir la antena, o moverla al lado oeste de la estructura), y se
verifica repitiendo la medida en el punto ONO: si el déficit baja al nivel del
sector este, está resuelto.

**Consecuencia para la campaña.** No tiene sentido subir al cerro mientras ese
sector siga ciego. Con el enlace del oeste reparado, el trayecto está despejado
y el presupuesto vuelve a dar el margen calculado (44 dB en SF10).

---

## 2026-08-29 (tarde) — A-09 reformulada: no hay sector ciego, y el cerro sale viable

**Tres correcciones de partida**, aportadas por quien estuvo en el sitio:

1. Las corridas etiquetadas **CERRO16 nunca se hicieron en el cerro**: son pruebas
   de banco en entorno urbano para verificar el join. Quedan **fuera del
   análisis** (se retiró `20260821-CERRO16-A` de `datos_sd`).
2. El **tinaco está 1 m por debajo de la antena** y no la obstruye.
3. El trayecto al **Cerro del Muerto tiene línea de vista limpia y clara**.

**El dato que zanja lo del sector ciego.** Con los CSV de la microSD ya
disponibles, el cruce da el PDR real de las cuatro pruebas de banco:

| Prueba | Azimut | Distancia | RSSI | **PDR** |
|---|---|---|---|---|
| 20260829-URBANO-A | 325° (NO) | 0,12 km | −71,3 dBm | **100,0 %** |
| 20260830-URBANO-A | 111° (ESE) | 0,23 km | −72,2 dBm | **97,0 %** |
| 20260829-URBANO-A-2 | 289° (ONO) | 0,26 km | −101,4 dBm | **96,7 %** |
| 20260829-URBANO-A-3 | 233° (SO) | 0,32 km | −89,0 dBm | **97,1 %** |

**Las cuatro cumplen el criterio, incluida la del sector supuestamente ciego.**
Un gateway apantallado en un sector no entrega el 96,7 % de los paquetes por ahí.
Lo que hay es **dispersión de RSSI por el entorno de cada punto de medida**
—*shadowing* urbano, del orden de 20-30 dB entre un punto con vista al mástil y
otro sin ella—, que es un fenómeno conocido y no una avería. La entrada de esta
mañana atribuyó al gateway lo que es del canal.

**Pronóstico del cerro.** Extrapolando desde cada punto medido con n = 2 —
justificado porque el trayecto es línea de vista con la primera zona de Fresnel
despejada (A-03) — a los 15,27 km:

| Referencia | RSSI previsto en el cerro | Margen SF10 |
|---|---|---|
| Presupuesto teórico (LoS puro) | −85,8 dBm | **+47 dB** |
| Mejor punto medido (ESE) | −108,7 dBm | **+24 dB** |
| Punto NO | −115,4 dBm | +18 dB |
| Punto SO | −123,2 dBm | +10 dB |
| Punto ONO (el más obstruido) | −136,8 dBm | sin enlace |

Con línea de vista limpia, los puntos urbanos obstruidos **no** son la referencia
aplicable: lo son el presupuesto y los puntos despejados. **El enlace al cerro es
viable**, con un margen previsible de +17 a +47 dB en SF10. Solo la extrapolación
desde el punto urbano más tapado predice fallo, y ese punto no se parece al
trayecto del cerro.

**Los downlinks funcionan.** Las cuatro pruebas registraron 6-8 downlinks cada
una, **todos por `rx1`** (columna `ventana` nueva, D-62). En la Serie 1 la Clase
A no recibió ninguno. El gate de clase (D-60) y el ping ligado a la sesión (D-61)
hacen su trabajo.

**Qué queda.** La duda que sigue abierta es por qué la Serie 1 rindió tan poco
(PDR 3-69 % con la sonda alejándose hasta 6 km en NLOS urbano). La explicación
más simple es que **el escenario URBANO es NLOS y se aleja**, no que el equipo
falle: a 300 m el mismo equipo entrega el 97 %. Antes de la Serie 2 conviene
fijar en el manual **cómo se coloca la sonda** (antena vertical, fuera del
vehículo) y aceptar que el criterio de PDR ≥ 80 % puede no ser alcanzable en
URBANO móvil, que es un resultado legítimo del experimento y no un fallo.

---

## 2026-08-30 (plan) — Serie 2: URBANO-C → CERRO16-A → CERRO16-C → URBANO-C-2

**Plan de mañana.** Se sube al Cerro del Muerto a ejecutar la Serie 2. El equipo
llega declarado sano —cuatro pruebas de banco con antena Semtech marcada
**US915** dieron **PDR 96,7-100 %** y 6-8 downlinks cada una, todos por `rx1`; no
hay avería ni sector ciego (A-09 reformulada)— y el trayecto al cerro, verificado
como LoS con la primera zona de Fresnel despejada en todo el recorrido (A-03,
cerrada 2026-08-29).

### La secuencia

Cuatro corridas, en este orden. Los dos cambios de clase ocurren **en el cerro**:

| # | Corrida | fPort | Dónde |
|---|---|---|---|
| 1 | URBANO Clase C | 12 | antes de subir |
| 2 | CERRO16 Clase A | 15 | en la cima |
| 3 | CERRO16 Clase C | 16 | en la cima |
| 4 | URBANO Clase C | 12 | al bajar |

La corrida 4 repite escenario y clase de la 1, así que el firmware la etiqueta
con el sufijo `-2` (D-39): son corridas distintas y no se mezclan en el
análisis. La 1 y la 4 acotan la jornada por los dos extremos — si difieren
mucho entre sí, lo que cambió es el canal urbano, no el equipo.

### Qué se espera medir

CERRO16-A y CERRO16-C dan el primer dato real de cobertura y alcance del
escenario 3 a **15,27 km**: las corridas etiquetadas CERRO16 hasta ahora eran
pruebas de banco en entorno urbano, no el cerro (A-09 reformulada), así que
quedaron fuera del análisis. El mismo par mide la latencia de downlink en
Clase A frente a Clase C con el gate de clase (D-60) y el ping ligado a la
sesión (D-61) ya operativos — el mismo día se verificó que entregan downlinks
por `rx1` en las cuatro pruebas de banco. Las dos corridas URBANO-C, al abrir y
cerrar la jornada, permiten ver si el PDR bajo de la Serie 1 (3-69 %) se repite;
la explicación de la Serie 1 es el escenario NLOS y el alejamiento hasta 6 km en
vehículo, no una avería del equipo — a 300 m el mismo equipo entrega el 97 %.

### Pronóstico del enlace en el cerro

Extrapolando con *n* = 2 desde los puntos de banco medidos —lícito porque el
trayecto es LoS con Fresnel despejado (A-03)— a los 15,27 km: **RSSI previsto
entre −109 y −123 dBm, margen SF10 de +17 a +47 dB**. El enlace se considera
viable.

### El join también va a SF10

Dato nuevo verificado hoy en el código de RadioLib: para US915 el JoinRequest se
envía con `drJoinRequest = 0`, es decir **SF10** — el mismo data rate que los
uplinks del escenario del cerro. Los re-joins que dispare cada cambio de clase
en el cerro (D-62) tienen por tanto el **mismo alcance** que la corrida en
marcha y no añaden riesgo de quedarse sin enlace. Es relevante porque D-41
(`FORCE_FRESH_JOIN`) hace que un join fallido **aborte la corrida**.

### Riesgos operativos y mitigación

- **A-10 (abierta).** El `run_id` que escribe la sonda en la microSD y el
  `run_label` que abre el servidor pueden divergir —cada uno numera sus
  intentos por su cuenta— y `cruzar.py` empareja por nombre de fichero, así que
  el cruce puede salir mal en silencio. Mitigación para mañana: anotar la hora
  UTC de inicio y fin de cada una de las cuatro corridas, que es lo que permite
  emparejarlas sin ambigüedad si los nombres no coinciden.
- **Los dos cambios de clase en el cerro.** C→A al llegar y A→C entre las dos
  corridas del cerro son el **primer uso en campo** del re-join automático por
  BLE (D-62): hasta hoy solo estaba verificado por lectura de código. Respaldo
  si se atasca: apagar y encender la sonda, que fuerza el mismo join OTAA
  (D-41) y deja a ChirpStack con la clase correcta congelada igual que lo
  haría el re-join.

---

## 2026-09-27 — Serie 2 en el cerro: CERRO16-A medida (PDR 92 %); CERRO16-C bloqueada por el join (A-11)

**Qué se hizo.** En la cima del Cerro del Muerto (21,88449 N, −102,41690;
2217–2274 m según el GPS) se corrió **CERRO16-A** (sesión 41, 14:04–14:44 UTC)
con el T-Beam. Al lado iba un **TTGO T3 (LMIC, SF7)** como referencia. Todo el
lado recibido quedó en `analisis/datos_app/20260927-*` y `analisis/datos_lns/`;
el análisis se reproduce con `analisis/cerro_20260927.py`. Informe completo en
[`analisis/resultados/20260927_cerro/INFORME.md`](analisis/resultados/20260927_cerro/INFORME.md).

**Resultados (solo servidor; falta la microSD):**

| | T-Beam SF10 | TTGO SF7 |
|---|---|---|
| PDR por fCnt | **92,0 %** (275/299) | 93,8 % (45/48) |
| RSSI medio | −110,6 dBm | −112,3 dBm |
| Margen de SNR en el p5 | +12,8 dB | +5,2 dB |

- **El pronóstico del 2026-08-29 se cumplió:** se esperaban −108,7 dBm
  extrapolando desde el mejor punto de banco y se midieron −110,6 dBm. El
  presupuesto teórico (−85,8 dBm) fue ~25 dB optimista y no debe usarse para
  estimar alcance.
- **Las pérdidas son sueltas** (24 ráfagas de longitud 1) y **casi todas en
  905,3 MHz** (A-12). El canal de cada pérdida se deduce porque RadioLib recorre
  los 8 canales sin repetir: en los 275 uplinks, ningún bloque alineado de 8
  fCnt repite canal.
- ~~ITPA-GW00 recibió 8 uplinks: diversidad de gateways~~ **Corregido el
  2026-09-28:** GW00 está en línea pero **sordo**. Recibe 0 paquetes al día
  desde el 20 de septiembre (el SenseCap recibe 7–9 mil); solo captó 8 uplinks
  del T-Beam (2,9 %) al límite de demodulación (−117 dBm / −18 dB). Apunta a
  una cadena de RF dañada. Hay **un solo gateway útil** (A-13).

**CERRO16-C no produjo datos.** El cambio de clase (D-60/D-62) funcionó del lado
del servidor: el perfil cambió y ChirpStack aceptó dos joins, a las 14:46:49 y
14:49:04. La sonda no recibió ninguno de los dos JoinAccept y, desde las
14:49:24, todos sus JoinRequest llegan con **MIC inválido** (A-11). Las sesiones
42 y 43 quedaron con 0 uplinks y 75 pings sin ruta de bajada. Es un fallo de la
pila en la sonda, no del enlace, y afecta también al vuelo.

**Incidente operativo menor.** El registro MQTT de la sesión de Claude se dio por
detenido a las 14:48 cuando en realidad su bucle de reconexión siguió activo
hasta las ~16:40. No se perdió nada: al contrario, capturó los 25 eventos de
MIC inválido. Para la próxima vez, detener el bucle (el proceso `bash`), no
solo el `ssh`.

**Siguiente paso.** (1) Descargar la microSD y cruzar. (2) Reproducir A-11 en
banco con log serie y corregirlo. (3) Repetir CERRO16-C.

**Adenda 2026-09-28 — data rate para 15 km y más.** El SNR medido en el p5 es el
mismo con SF10 y SF7 (−2,25 dB), así que el margen de cada DR sale de restar su
límite de demodulación. Con *n* = 2: DR0/SF10 deja +12,8 dB a 15,27 km (~21 km
con 10 dB de reserva de globo, ~33 km con 6 dB); DR1/SF9 da ~16 km / ~25 km;
DR3/SF7 da ~9 km / ~14 km. **Se recomienda DR0/SF10 con ADR desactivado** para
el vuelo. Más de ~20–30 km exige otro gateway u otra antena, no otro DR. Tabla
completa en el INFORME, §6.

---

## 2026-09-28 — A-11 corregida: el nodo se reconstruye tras cada join fallido

**Causa (confirmada en el código).** RadioLib 7.7.1, `processJoinAccept()`
(`LoRaWAN.cpp:811`), fija `rev` con el bit OptNeg de **cualquier** JoinAccept que
oiga, antes de comprobar el MIC, y no lo deshace si falla. Una JoinAccept de otra
red deja `rev = 1` la mitad de las veces. Desde entonces los JoinRequest se
firman con `nwkKey`, que en 1.0.x vale ceros, y el servidor los rechaza todos.
`clearSession()`, que es lo que usaba el re-join (D-62), no restaura `rev`.

**Remedio (`firmware/main/lorawan.cpp`).** `rearmar_nodo()` destruye el
`LoRaWANNode` y crea uno limpio (`beginOTAA`, ADR off) y le restaura **solo los
nonces**, para que el DevNonce siga creciendo. Se llama tras **cualquier** intento
de join fallido y en cada re-join (sustituye a `clearSession()` en
`descartar_sesion`). Una subclase final `PicaroNode` expone `rev` solo para
registrarlo: si un intento termina con `rev ≠ 0`, el log serie lo avisa (`A-11:
rev=1 tras el intento`). No se modifica RadioLib: los `managed_components` se
regeneran solos y un parche se perdería.

**Alternativas descartadas.** Parchear RadioLib dentro de `managed_components`: el
gestor de componentes lo sobrescribe o lo rechaza por el hash. Copiarlo a
`components/`: se congela una librería entera por una línea. Escribir `rev = 0` a
mano desde la subclase: arregla `rev`, pero no `joinNonce` ni `devAddr`, que
quedan envenenados por la misma trama.

**Verificación en banco (T-Beam en COM15, gateway del laboratorio).**
- Firmware de prueba con `PICARO_TEST_REV_CORRUPTO=1`, que fuerza `rev = 1`
  antes del primer join. La sonda registró `activateOTAA sin exito (-1116)` y
  `rev=1 ... se rearma el nodo`; el intento #2 dio `JOIN NUEVO`. ChirpStack
  registró **`Invalid MIC`**, el mismo síntoma del cerro, y a continuación un
  join válido.
- Firmware de producción (bandera en 0) flasheado de nuevo: join normal al
  primer intento.

**Pendiente.** Probar el re-join **por BLE desde la app** (op `0x03`), que es el
camino que falló en el cerro. El disparador real, una JoinAccept ajena, no se
puede provocar en banco sin un segundo servidor de red. Lo que se ha
comprobado es que el estado que deja esa trama ya no bloquea el join.

---

## 2026-09-28 — D-64 · Corrida VUELO: la telemetría completa de la cápsula en 11 bytes

**Decisión (usuario).** Nueva corrida para simular la cápsula, que volará 55 minutos:
DR0/SF10 (el único DR con alcance de 15 km o más con reserva de globo, INFORME del
cerro §6), **solo Clase A**, y **todos** los sensores de la T-Beam. Como en DR0 solo
caben 11 bytes, cada minuto la lectura se reparte en tres paquetes que salen cada 20 s,
con 1 byte de cabecera (tipo + nº de ráfaga) y un solo fPort (17). Se mantienen los
pings: en Clase A no miden latencia, pero sí si la cápsula recibe órdenes (el corte)
a esa distancia. Se mide desde **puntos fijos** en altura y distancia. Quedan fuera la
IMU (inestable en esta placa) y el RTC.

**Por qué uno cada 20 s y no los tres seguidos.** Una interferencia de pocos segundos,
como la de 905,3 MHz en el cerro (A-12), tumbaría una ráfaga entera si los tres
paquetes salieran juntos; repartidos, se pierde uno.

**Qué se cambió** (contrato común en `docs/VUELO-ESPEC.md`):
- **Firmware:**
  - `escenarios.c/.h`: escenario `VUELO` y **tabla explícita de corridas**. La regla
    `escenario = i/2`, `clase = i%2` ya no vale con un escenario solo A; los índices
    0–5 no cambian.
  - `payload_terreno.c`: `payload_vuelo_build()`, con sentinelas «no disponible» y
    altitud sin signo hasta 65 km.
  - `app_main.cpp`: bucle por ráfagas (una lectura por ráfaga, velocidad vertical entre
    ráfagas).
  - `runlog`: columnas `tipo,rafaga` y `<run_id>_lecturas.csv`.
  - `ble_control.c`: modo 0..6.
  - `telemetry`: `bme_ok`.
- **Decoder:** rama para el fPort 17, desplegada en `terreno-a`/`terreno-c` con
  `desplegar_decoder.py`. Los fPorts 11–16 no cambian: se verificó con un uplink real
  del cerro.
- **Microservicio 1.2.0:**
  - objetivo de uplinks por corrida (165 en VUELO);
  - métricas `vuelo` (por tipo y por ráfaga) y clave `vuelo` en cada uplink;
  - rechazo de VUELO-C;
  - 65 tests.
  - Redesplegado con copia de seguridad en `/opt/picaro-campo/microservicio.bak.202609290307`.
- **App 2.1.0:**
  - VUELO en el selector (fila propia) y modo 6 por BLE;
  - panel «Vuelo · última lectura», donde cada magnitud sale del último paquete que la
    trajo;
  - mapa y gráficas sin pintar nulls como ceros;
  - 29 tests. APK firmado en `app/build/app/outputs/flutter-apk/app-release.apk`,
    **sin publicar**.
- **Análisis:** `cruzar.py` reconoce VUELO y lo excluye del control A vs C; nuevo
  `vuelo.py`, que compara el margen medido con la curva del cerro.
- **Documentación:** CONTRATO-CAMPO v1.4, CONTRATO-BLE (modo 0x06), APP-CAMPO,
  EXPERIMENTO (corrida 4A), MANUAL §15, hoja de campo y READMEs.

**Verificación en banco** (T-Beam en COM15, gateway del laboratorio, sesión 44
`20260929-VUELO-A`, con un parche temporal de arranque automático y 3 ráfagas,
**ya revertido**):
- **Envío:** 9 de 9 enviados y recibidos (3 P1 · 3 P2 · 3 P3), a 11 B y 371 ms cada uno.
- **Pings:** los 3 llegaron por RX1, uno por minuto.
- **Decodificación correcta:** 28,04 °C, 809,7 hPa, 53 % de humedad, 4,153 V, rumbo
  165,7°, tiempo desde el arranque 45 / 105 / 165 s. Sin fix en interiores, así que P1
  llega sin posición, como se espera.
- **Gate de clase:** rechazó la sesión mientras la sonda seguía congelada en Clase C y
  la aceptó tras el re-join.

**Fallo encontrado en banco y corregido.** ChirpStack entrega los números del `object`
del codec como *double* (`"rafaga": 0.0`), y el microservicio descartaba esas ráfagas
(0 completas). Se aceptan los floats enteros (`_entero()`), con un test nuevo;
redesplegado, la sesión 44 da 3 de 3 ráfagas completas. `vuelo.py` tenía el mismo
fallo y también está corregido. La app no lo sufría (`asInt` ya convierte los
double).

**Pendiente:**
- Instalar el APK 2.1.0 en el teléfono.
- Probar desde la app la selección de VUELO por BLE y el re-join por BLE (A-11).
- Revisar en la microSD `*_lecturas.csv` y las columnas nuevas; en banco no se pudo
  leer sin sacar la tarjeta.
- Ir al primer punto fijo.

La sonda queda con el firmware de producción y VUELO-A seleccionada en el menú.


---

## 2026-10-13 — D-65 · Segunda sonda: T3 v1.6.1 (LoRa32), solo VUELO-A, sensores simulados

**Decisión (usuario).** Se añade una segunda sonda, una LILYGO T3 v1.6.1 (ESP32 +
SX1276), para probar la conexión con el gateway nuevo de Pabellón de Arteaga. Se opera
desde la misma app, por BLE, contra el mismo microservicio. Corre **una sola corrida,
VUELO-A** (DR0/SF10, el máximo alcance). **La placa simula los sensores** que no tiene
(GPS, BME280, magnetómetro) y manda los mismos P1/P2/P3 de 11 bytes que la T-Beam.

**El payload: primero un formato propio, luego sensores simulados (corrección).** El
pedido inicial era «simular un payload de 11 bytes». Se interpretó como un patrón de
prueba (contador `seq`, uptime, batería, patrón y CRC-8), con su propia rama en el
decoder, elegida por la variable de device `formato=estres`. En la app el panel de VUELO
salía vacío, y el usuario aclaró que lo pedido desde el principio era **que la placa
simulara los sensores**. Se retiró el formato propio:
- firmware: fuera `payload_estres`; los valores salen de `simulacion.h` en
  `telemetry_collect()`;
- decoder: vuelve, byte a byte, al anterior a D-65;
- ChirpStack: se borró la variable `formato` del device.

Con eso el decoder, el microservicio y la app tratan igual a las dos sondas.

**Distancia con el GPS del teléfono (opción 2, elegida por el usuario).** La posición
simulada de la placa no mide nada. La app manda la posición del teléfono, que va junto a
la sonda, y el servidor la guarda con la sesión. Se descartó la opción 1, que solo la
mostraba en pantalla y no dejaba registro.

Cómo se calcula:
- Cada uplink se empareja con la posición del teléfono más cercana en el tiempo, si está
  a ≤ 300 s.
- Se mide contra **el gateway que recibió el uplink**, con sus coordenadas de ChirpStack;
  si no las tiene, con `GW_LAT/GW_LON`. Es la opción b frente a la a (escribir a mano las
  coordenadas del gateway en la app): es automática y sirve con varios gateways.
- En ChirpStack, solo el Kerlink de Pabellón (`ITPA-IOT-GW01-kibts`) tiene coordenadas.
  Los otros tres están a 0,0 y caen en `GW_LAT/GW_LON`, que es el del laboratorio.
- La T-Beam sigue midiendo con su GPS, como siempre.

**Un microservicio, varias sondas, una sesión a la vez (alternativa A, elegida por el
usuario).** Primero se montó un segundo microservicio con su propio subdominio para la
T3. El usuario lo rechazó como antipatrón (un despliegue por sonda), y se retiró.
Alternativas que se valoraron:
- **A (elegida):** el servicio conoce varias sondas y cada sesión es de una.
- **B:** como A, pero simultánea, con una sesión por sonda; descartada por su coste,
  porque todo el servicio gira alrededor de «una sesión activa».
- **C:** cambiar a mano el `DEV_EUI` del servidor; descartada por frágil en campo.

En A:
- `POST /session/start` lleva un campo opcional `sonda`. Sin él, la sesión es de la
  T-Beam, así que el APK anterior sigue funcionando.
- El perfil, el gate de clase, los pings y la captura van al DevEUI de la sonda de la
  sesión. El MQTT recibe todos los devices de la aplicación y descarta los que no son
  de la sesión.
- La app reconoce la T3 por su nombre BLE (`PICARO-LORA32`) y solo le ofrece VUELO-A.
  El servidor tampoco abre otra corrida para ella, y el firmware rechaza otros modos
  por BLE.
- El nombre BLE propio es una desviación del CONTRATO-BLE §3.4, que pedía el mismo
  nombre en todas las sondas: ahora es el dato que identifica a la sonda.

**Hallazgos de hardware (esquemático T3_V1.6.1 y la unidad real):**
- **No hay botón de usuario.** **Decisión (usuario): la T3 se opera solo desde la
  app.** El botón queda desactivado (`BOTON_HABILITADO 0`): IO0 va al auto-reset del
  puente USB y el monitor serie generaría pulsaciones fantasma. La T3 renuncia al
  respaldo sin app (RF-8) que sí tiene la T-Beam.
- El puente USB es un **CH9102**, no el CP2104 del esquemático. Con un cable solo de
  carga, Windows no ve ningún puerto.
- Sin PMU: la batería se lee por ADC (IO35, divisor 1:2) y no hay porcentaje.
- El device ya existía en ChirpStack (`0011223344550003`, aplicación PiCARO) con
  firmware LMIC. Su JoinEUI registrado es `0000000000000000`, y es el que usa el
  firmware. La AppKey no se versiona (`credenciales_lora32.h` está en `.gitignore`).

**Qué se cambió:**
- **Firmware nuevo** `firmware_lora32/`, compilado con `PICARO_CORRIDA_FIJA=6`, con los
  sensores simulados en `simulacion.h`. Lo que es copia de la T-Beam y lo que es propio
  de la placa está en su README.
- **Decoder:** sin cambios netos. La rama `estres` se desplegó y se retiró; los perfiles
  `terreno-a`/`terreno-c` llevan otra vez el codec anterior.
- **Microservicio 1.3.0:** sondas `tbeam`/`lora32` (`DEV_EUI_LORA32`); columnas `sonda`
  y `dev_eui` en `sessions`, con migración automática de la SQLite; 79 tests (14
  nuevos). Desplegado con copia de seguridad en
  `/opt/picaro-campo/microservicio.bak.202610132019` (y `.env.bak.202610132019`).
- **App 2.2.0:** sonda según el nombre BLE, selector limitado a VUELO A con la T3, y
  `sonda` en `session/start`.
- **Microservicio 1.4.0:**
  - `POST /session/{id}/posicion`, `GET /sessions/{id}/posiciones[/csv]`;
  - tabla `posiciones`;
  - métricas `dist_gw_km_ultima`, `posicion_telefono` y `gateway_ultimo`;
  - columnas de distancia al final del CSV de uplinks;
  - coordenadas de cada gateway leídas de ChirpStack una vez y guardadas;
  - 94 tests, 15 de ellos nuevos.

  Desplegado con copia de seguridad en `/opt/picaro-campo/microservicio.bak.202610132107`.
- **App 2.3.0:**
  - GPS del teléfono con `geolocator` (`lib/gps/gps_telefono.dart`), activo solo
    mientras captura una sesión de la T3, con un envío cada 30 s;
  - bloque «Distancia · GPS del teléfono» en el Panel;
  - permisos de ubicación sin el tope de Android 11;
  - 36 tests. **Publicada como release `v2.3.0`** en GitHub (`picaro-campo-v2.3.0.apk`,
    misma firma que la v2.0.4: se instala encima). Incluye la 2.1 y la 2.2, que no se
    publicaron.
- **Contrato:** CONTRATO-CAMPO §17 (v1.5), puntos 9–11 para las posiciones.
  APP-CAMPO §3.4.

**Verificación en banco** (T3 en COM18, gateway del laboratorio):
- Join OTAA real al primer intento (~5,5 s).
- Con un parche temporal de arranque automático, **ya revertido**: CERRO16-A con 12 de
  12 uplinks en el microservicio, sin huecos, RSSI −77 dBm, SNR 11,8 dB, batería
  decodificada por la rama nueva y un ping recibido por RX1. Esto fue con el firmware
  anterior a fijar VUELO; la corrida VUELO desde la app queda por probar.
- **Producción 1.3.0:**
  - `URBANO` para `lora32` → 400;
  - `VUELO-A` para `lora32` → 201, gate de clase superado, sesión con el DevEUI de la
    T3;
  - las sesiones antiguas migradas como `tbeam`.
  
  La sesión de prueba (49) se borró.
- **Sensores simulados** (sesión de banco 51, borrada):
  - P1: 22,1478, −102,2766, 2010 m.
  - P2: 25,72 °C, 799,3 hPa, 48 %, batería 4,30 V, 9 satélites.
  - P3: HDOP 0,9, velocidad vertical 0,0.

  Decodificado por el codec estándar de VUELO, con `gps_fix`.
- **Posiciones en producción (1.4.0):**
  - `POST /posicion` → 201, y `posicion_telefono` aparece en las métricas;
  - la lectura de coordenadas contra el ChirpStack real devuelve las del Kerlink, y
    `None` para el SenseCap del laboratorio;
  - la sesión de prueba (52) se borró.

**Pendiente:**
- Instalar el APK 2.3.0 y correr VUELO-A desde la app con la T3, comprobando que llega
  la distancia del teléfono.
- Opcional: poner en `simulacion.h` el punto real de la prueba (solo afecta al mapa).
- Opcional: cargar en ChirpStack las coordenadas de los gateways que están a 0,0.
- La microSD de la T3 no monta (la tarjeta no responde): revisar si hay tarjeta.
- Prueba de campo en Pabellón de Arteaga.

## 2026-10-17 — D-66 · Mapa público de la red en https://pi-caro.org

**Decisión (usuario).** Un sitio público en el dominio `pi-caro.org`, sin uso hasta
ahora, con un mapa de los dispositivos de todas las apps del tenant Proyecto PiCARO.
Lo prioritario es **qué datos reportan** y **con qué calidad los capta cada gateway**.
Código en `mapa-publico/`; manual en su README.

**Decisiones cerradas:**
- **Los codecs no se normalizan.** Cada uno es de un equipo distinto y resolver su
  formato es parte de su reto de ingeniería. El `object` se publica tal cual; si el
  perfil no tiene codec, solo se muestran proyecto, nodo y señal.
- **Publicación opt-in** con el tag `publico=true` (dispositivo o app). Nada sale por
  accidente.
- **Geolocalización** detectada por nombres típicos, con override por tags
  `geo_lat/geo_lon` del device profile. Sin posición → **ITPA**, con las coordenadas
  del Kerlink ITPA-IOT-GW01 (el GW00 está a 0,0 en ChirpStack).
- **Identidad**: nombre de la app + nombre del dispositivo. Nunca EUIs ni IPs.
- **Hosting** en el mismo servidor del LNS, detrás de su Caddy; **SSE** para el
  tiempo real; **7 días** de historial; `www` redirige con 301 a la raíz.
- **Mínimo privilegio**: usuario MQTT que solo lee `event/up` y rol de Postgres con
  `SELECT` por columnas. Se prefirió a una API key de ChirpStack porque una key de
  tenant, aun de solo lectura, ve todo el tenant.

**Inventario de codecs (posición):** solo los perfiles de la radiosonda
(`Radiosonda-Terreno-*`) y `ESP32_MECA` traen `latitude/longitude`. LR1110 (GNSS
sin solver), Meteoro y Heltec-Join-fenix traen datos sin posición. Los perfiles Heltec
LoRa 32 V3 / Wifi v4 tienen el codec en `NONE`: solo señal.

**Verificación (2026-10-17):** con `LR1121-DevKit-Campo` publicado, los uplinks llegan
al navegador por SSE cada ~30 s a través de Caddy; ni la página ni la API contienen
DevEUI, DevAddr, EUIs ni IPs; certificados de Let's Encrypt emitidos para la raíz y
`www`; sin errores de consola en escritorio, móvil y modo oscuro.

**Nodos que dejan de transmitir (usuario, mismo día).** Al apagar la LR1110 seguía
viéndose activa: solo se atenuaba a los 60 min. Decisión: **inactivo (gris) a los
5 min** sin uplink y **fuera del mapa a las 24 h** (queda en la lista, en
"Inactivos"). Los publicados que nunca han transmitido se siguen mostrando en el ITPA
como "sin datos". La purga del historial conserva el último uplink de cada nodo para
que uno apagado no vuelva a parecer "sin datos".

**Pendiente:**
- ~~Poner `publico=true` en los nodos o apps que se quieran mostrar~~ (hecho: 11 nodos).
- Cargar en ChirpStack la ubicación de los gateways que están a 0,0.

## 2026-10-21 — D-67 · Identidad institucional en el mapa público

**Decisión (usuario).** El mapa de https://pi-caro.org lleva los colores y logos del
TecNM y del ITPA, y el logo del evento SatLink 2026, que además da el título al sitio:
**SatLink 2026 · Red PiCARO**.

- **Cabecera** en azul TecNM `#1B396A`. TecNM a la izquierda (versión blanca), ITPA
  en un recuadro blanco (su texto es oscuro) y el parche de SatLink a la derecha.
- **Franja tricolor ITPA** (amarillo, rojo, índigo) bajo la cabecera.
- **Modo oscuro** en el azul noche de SatLink.
- **El semáforo de señal no cambia**: los colores institucionales no se usan en los
  marcadores, donde el color significa calidad del enlace.
- **Móvil**: solo se permite recortar el **engrane del TecNM**. El ITPA no se recorta;
  los logos completos van en "Organizan", al pie de la lista.
- **Enlaces**: TecNM → tecnm.mx; ITPA → pabellon.tecnm.mx. SatLink sin enlace (no hay
  sitio del evento).

Se descartó la cabecera blanca: el logo del TecNM solo existe en blanco y habría
necesitado su propio recuadro azul.

**Verificado:** escritorio claro y oscuro, 1000 px y móvil (detalle y lista), sin
errores de consola.

**Corrección (usuario, mismo día).** «Los logos se ven muy mal, el del TecNM aparece
doble, el del Tec no es legible; faltan IEEE e IEA en los organizadores»:
- **TecNM doble**: no era la página, era la caché. Sin `Cache-Control`, el navegador
  usó el `index.html` nuevo con el `app.css` viejo, que no oculta el engrane.
  Arreglo: Caddy manda `no-cache` y los recursos llevan `?v=<versión>`.
- **Legibilidad**: logos exportados a 2–3× y más grandes en la cabecera (TecNM 62 px,
  ITPA 52 px).
- **Organizan** pasa a verse en todas las pantallas: TecNM, ITPA, IEEE e IEA.
- **Gateways**: se cargaron en ChirpStack las ubicaciones de ITPA-IOT-GW00 y
  del gateway del laboratorio; el mapa muestra ahora los 3 gateways activos.
