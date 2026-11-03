# Protocolo experimental — Radiosonda PICARO sobre LoRaWAN

**Proyecto:** pruebas_terreno
**Versión del protocolo:** 1.2
**Fecha de redacción:** 2026-07-18 · **Revisado:** 2026-07-19
**Estado:** pre-registrado (redactado **antes** de la toma de datos)

> Este documento fija objetivos, hipótesis, criterios numéricos y plan de
> análisis **antes** de recoger un solo dato. Es deliberado: si el criterio de
> éxito se define después de ver los resultados, siempre se encuentra alguna
> partición de los datos que "sale bien". Cualquier análisis no previsto aquí y
> realizado a posteriori debe declararse como **exploratorio** en la memoria
> técnica, no como confirmatorio.
>
> Toda modificación posterior a la primera corrida se registra en
> [`../BITACORA.md`](../BITACORA.md) con fecha y motivo.
>
> **Revisión 1.1 (2026-07-19), antes de tomar ningún dato.** Se corrigen los
> intervalos de uplink, que eran físicamente imposibles con la configuración real
> del servidor (§5.1), y se reduce el tamaño de muestra de 600 a 300 uplinks por
> corrida (§5.2). El criterio de fondo es nuevo y vinculante: **la configuración
> global del servidor no se modifica por este experimento**. Si un parámetro del
> diseño no cabe, se ajusta el diseño.
>
> **Revisión 1.2 (2026-07-19), antes de tomar ningún dato.** Se separa *seleccionar*
> de *arrancar* una corrida: el arranque pasa a ser un acto explícito del operador
> (§6.2), de modo que ningún uplink se registre mientras aún se monta el equipo. Se
> define cómo se separan los intentos de una corrida abortada (§5.2) y se eleva a
> sección propia la dependencia del device profile del servidor (§6.4), que es el
> único fallo de configuración capaz de refutar H4 sin dejar rastro. Se corrige una
> variable controlada que no correspondía al firmware real: el OLED **no** se apaga
> solo (§3.3). El procedimiento operativo detallado vive en
> [`MANUAL-DE-CAMPO.md`](MANUAL-DE-CAMPO.md).

---

## 1. Objetivo y preguntas de investigación

### 1.1 Objetivo general

Caracterizar el comportamiento de una radiosonda LoRaWAN en tres condiciones de
propagación representativas, y cuantificar el coste y el beneficio de operar en
**Clase C** frente a **Clase A**.

### 1.2 Preguntas de investigación

| ID | Pregunta |
|---|---|
| **P1** | ¿Qué relación de paquetes entregados (PDR) se obtiene en cada escenario, y cómo evoluciona con la distancia? |
| **P2** | ¿Cuánto se reduce la autonomía al mantener el receptor permanentemente activo (Clase C)? |
| **P3** | ¿Cuánto se reduce la latencia del comando de corte en Clase C respecto a Clase A? |
| **P4** | ¿Es alcanzable un enlace a **16,35 km** con SF10 y línea de vista, con la instalación de gateway disponible? |

### 1.3 Alcance y no-objetivos

Este experimento **no** pretende:

- Determinar el alcance máximo absoluto del sistema (requeriría un barrido de SF
  y de posiciones, no tres puntos fijos).
- Optimizar el consumo del firmware. El consumo se **mide**, no se optimiza.
- Evaluar ADR. ADR está desactivado en las seis corridas por diseño (§3.3).

---

## 2. Hipótesis

Cada hipótesis se enuncia en forma falsable y con criterio numérico explícito.
`H0` es la hipótesis nula; se rechaza según el criterio indicado.

> **Nota de estado (2026-08-30).** La Serie 2 cubre **H1** y **H2** (cobertura,
> con el primer dato real del escenario CERRO16 a 15,27 km), **H4** (latencia
> de downlink Clase A frente a Clase C, en el par CERRO16-A/CERRO16-C) y **H5**
> — que es la que se pone a prueba de forma más directa: las dos corridas del
> cerro son, literalmente, el experimento de viabilidad del enlace a 15,27 km.
> **H3**
> ya había salido de la campaña de campo hacia un ensayo de banco independiente
> (Adenda 1, al final de este documento). Detalle del diseño y el pronóstico de
> la Serie 2 en §5.4 y en [`../BITACORA.md`](../BITACORA.md), entrada
> 2026-08-30 (plan).

### H1 — Cobertura por escenario

> **H1:** El PDR difiere significativamente entre los tres escenarios.

- **H0₁:** PDR(esc.1) = PDR(esc.2) = PDR(esc.3)
- **Criterio de rechazo:** prueba de χ² sobre la tabla de contingencia
  (entregados / perdidos) × (escenario), con **α = 0,05**.
- **Estimación por corrida:** PDR = *n* recibidos en servidor / *n* enviados
  según registro del dispositivo (§7.1).

### H2 — Independencia entre clase y cobertura (**control**)

> **H2:** El PDR **no** difiere entre Clase A y Clase C dentro del mismo escenario.

Esta es la hipótesis de **control** del diseño, y merece un párrafo aparte
(§2.1). Es la única cuyo resultado esperado es la **no** diferencia.

- **H0₂:** PDR(A) = PDR(C) para cada escenario.
- **Criterio:** se **espera no rechazar** H0₂. Se declara problema de método solo
  si se cumplen **las dos condiciones a la vez**:
  1. χ² sobre (entregado × clase) significativo con **α = 0,05**, y
  2. |PDR(A) − PDR(C)| > **5 puntos porcentuales**.
- **Por qué las dos.** Con *n* = 300 por corrida, el χ² detecta como significativa
  una diferencia de 3–4 pp que carece de relevancia práctica. Usado en solitario
  llevaría a descartar corridas válidas. Exigir además un tamaño de efecto mínimo
  separa «hay señal estadística» de «la diferencia importa». **Ambos valores se
  reportan**, aunque solo uno se cumpla.
- **Interpretación de un fallo:** un rechazo de H0₂ **no** es un hallazgo sobre
  LoRaWAN; es un indicio de que el método experimental está contaminado
  (§2.1, §9).

### H3 — Coste de la Clase C en autonomía

> **H3:** La corriente media consumida en Clase C es significativamente mayor que
> en Clase A.

- **H0₃:** Ī(C) ≤ Ī(A)
- **Criterio de rechazo:** Ī(C) − Ī(A) ≥ **3 mA** de forma consistente en las
  tres parejas de corridas. Contraste: *t* de Student pareado por escenario,
  **α = 0,05**.
- **Magnitud esperada:** la recepción continua del SX1262 se sitúa en el orden de
  **5–10 mA**. Un resultado por debajo de 3 mA obligaría a verificar que la Clase
  C está realmente activa (§9.4).
- **Métrica derivada:** autonomía estimada en horas = capacidad útil (mA·h) /
  Ī, reportada para ambas clases.

### H4 — Beneficio de la Clase C en latencia de downlink

> **H4:** La latencia del comando de corte es sustancialmente menor en Clase C.

- **H0₄:** mediana de latencia(C) ≥ mediana de latencia(A)
- **Criterio de rechazo:** mediana(C) ≤ **1 s** y mediana(A) ≥ **0,4 × intervalo
  de uplink** del escenario. Contraste: *U* de Mann-Whitney, **α = 0,05**.
- **Predicción teórica:** en Clase A el comando espera al siguiente uplink, por lo
  que su latencia se distribuye ~uniformemente en [0, intervalo] con media ≈
  **intervalo/2**, más `rx1_delay`. En Clase C la latencia debe aproximarse al
  RTT de red (~180 ms medidos México↔servidor en la nube) más el tiempo de aire del
  downlink en RX2.

### H5 — Viabilidad del enlace a 16,35 km

> **H5:** El enlace a 16,35 km con SF10 y LoS es viable.

- **Criterio de aceptación:** PDR ≥ **50 %** en el escenario 3, con SNR mediano
  ≥ **−15 dB**.
- **Por qué 50 % y no el 80 % de los otros escenarios.** A esta distancia, en el
  límite del presupuesto útil, recibir la mitad de los paquetes ya demuestra que
  el enlace existe y es explotable con redundancia. Aplicar el mismo umbral que en
  entorno urbano haría fallar el criterio aunque el enlace funcionase, que es
  precisamente el error que se quiere evitar al pre-registrar el criterio.
- **Nota:** esta hipótesis es de **viabilidad**, no comparativa. Un resultado
  negativo no invalida el experimento; documenta un límite (§9.5).

### 2.1 Sobre H2: por qué el control está integrado en el diseño

La clase LoRaWAN describe el comportamiento del **receptor** del nodo. No
modifica la potencia de transmisión, el factor de propagación, el ancho de banda
ni el canal de subida. En consecuencia, **la clase no puede afectar físicamente a
la probabilidad de que un uplink llegue al gateway**.

Esto convierte a H2 en un control gratuito e integrado: al medir cada escenario
dos veces con la única diferencia de la clase, se obtiene una **réplica** de la
medida de cobertura. Si ambas coinciden dentro del margen de 5 puntos, se gana
confianza en que el procedimiento es reproducible. Si divergen, existe una
variable no controlada —deriva temporal de la propagación, cambio de ruta,
caída de tensión de batería (§9.3)— y las conclusiones sobre H1 y H5 quedan en
entredicho hasta resolverlo.

Un experimento que no puede detectar su propio fallo no es un experimento.

### 2.2 Lo que H5 realmente pone a prueba

El presupuesto de enlace calculado para este trayecto concreto (§4.4) arroja un
margen de **43,6 dB en SF10** y de **36,6 dB en SF7**. Con línea de vista limpia,
el enlace de 16,35 km funcionaría **incluso en SF7**.

De ahí se sigue una precisión importante para la memoria técnica: **H5 no pone a
prueba la sensibilidad del factor de propagación, sino la geometría del
trayecto**. SF10 se elige por margen frente a obstrucción parcial y
desvanecimiento, no porque haga falta para cubrir la distancia. Si H5 se rechaza,
la causa estará casi con seguridad en el despeje del terreno (§9.5), no en el DR
elegido.

---

## 3. Variables

### 3.1 Variables independientes (manipuladas)

| Variable | Niveles | Cómo se fija |
|---|---|---|
| **Escenario** | 1 URBANO (móvil en vehículo), 2 TERRAZA (piso 5 exterior), 3 CERRO16 (LoS 16,35 km) | Ubicación física + perfil de radio, seleccionado con el botón |
| **Clase LoRaWAN** | A, C | Menú del dispositivo → `setClass()` en RadioLib **y** device profile de ChirpStack. Las dos mitades deben coincidir (§6.4) |

La selección se hace **en campo con el botón físico** y persiste en NVS; no
requiere recompilar ni conectar un portátil. Un único binario cubre las seis
corridas, lo que además garantiza que el firmware es idéntico en todas ellas
(§3.3).

Diseño factorial completo 3 × 2 = **6 corridas** (§5).

### 3.2 Variables dependientes (medidas)

| Variable | Unidad | Fuente | Definición operativa |
|---|---|---|---|
| **PDR** | % | (a) ∩ (b) por `fCnt` | recibidos / enviados |
| **RSSI** | dBm | (b) `rxInfo` | mediana por tramo de distancia |
| **SNR** | dB | (b) `rxInfo` | mediana por tramo de distancia |
| **Corriente media Ī** | mA | (a) `batt_mA` | media temporal sobre la corrida |
| **Autonomía** | h | derivada de Ī | capacidad útil / Ī |
| **Latencia de downlink** | ms | (c) − marca de encolado en servidor | t(GPIO) − t(encolado) |
| **Airtime acumulado** | s | (a) `airtime_ms` | Σ por corrida |
| **Ciclo de trabajo real** | % | derivada | airtime acumulado / duración |
| **Distancia** | m | (a) lat/lon vs posición del gateway | Haversine |

### 3.3 Variables controladas (fijadas e idénticas en las seis corridas)

| Variable | Valor | Justificación |
|---|---|---|
| **ADR** | **Desactivado** | Con ADR activo, la red cambiaría el DR durante la corrida y el escenario dejaría de ser una condición fija |
| **DR / SF** | Fijo por escenario (§5.1) | Variable de diseño, no ajustable en vuelo |
| **Potencia TX** | Máxima permitida en US915 sub-banda 2, idéntica en todas | Evita confundir clase con potencia |
| **Región / sub-banda** | US915, sub-banda 2 (canales 8–15 + 65) | Coincide con el gateway y el servidor |
| **`rx1_delay`** | **5 s** | Valor del servidor compartido, que **no se modifica** (§4.2). Determina el ciclo mínimo de uplink (~6,5 s) y, con él, los intervalos de §5.1 |
| **Payload** | 11 bytes (+3 opcionales) | Idéntica carga útil ⇒ airtime comparable entre clases |
| **Gateway** | SenseCAP M2, misma posición y antena | Cambiar la instalación invalidaría la comparación entre escenarios |
| **Carga inicial de batería** | 100 %, misma referencia | Crítico para H3 y para evitar el confusor de §9.3 |
| **Dispositivo** | El mismo nodo físico | Elimina variabilidad entre unidades |
| **Firmware** | **Binario idéntico** en las seis corridas; escenario y clase se eligen en el menú y persisten en NVS | Trazabilidad, y elimina el riesgo de compilar mal una corrida |
| **OLED** | **Permanentemente encendido** en las seis corridas | Es la única verificación en campo de que la sonda transmite, y el menú necesita verse. Al ser idéntico en A y C no introduce sesgo entre clases, pero **sí impide medir H3 en campo**: consume 20–30 mA y sepultaría la diferencia A/C de 5–10 mA (ver la nota siguiente) |

> **Sobre el OLED y H3.** Una versión anterior de este protocolo daba por hecho un
> apagado automático de la pantalla a los 30 s. **Ese comportamiento no existe en el
> firmware** y su ausencia se confirmó revisando el driver. La consecuencia no es que
> falte implementarlo, sino que refuerza una decisión ya tomada por otra vía: **H3 no
> es medible en campo** y se traslada a banco (Adenda 1). El AXP2101 de esta placa no
> mide corriente de batería, y la caída de tensión esperable en 40 minutos (~1,4 mV)
> queda por debajo del ruido de la propia lectura (5–20 mV). Añadir ahora un apagado
> automático sería además contraproducente: el menú tiene que poder verse parpadear y
> la pantalla de `FINALIZADO` tiene que ser legible al llegar a la sonda.

---

## 4. Materiales y equipo

### 4.1 Nodo (radiosonda)

| Elemento | Especificación |
|---|---|
| Placa | LilyGo T-Beam Supreme (ESP32-S3) |
| Radio | SX1262, 868/915 MHz |
| GNSS | Quectel L76K (UART) — posición y **referencia horaria UTC** |
| Sensor ambiental | BME280 (I²C) — temperatura |
| PMU | AXP2101 (I²C) — tensión y **corriente** de batería |
| Almacenamiento | microSD (SPI) — registro local |
| Firmware | ESP-IDF v5.x + RadioLib 7.7.x |
| Antena | De serie del T-Beam Supreme, ~2 dBi (valor asumido en §4.4) |

### 4.2 Infraestructura

| Elemento | Especificación |
|---|---|
| Gateway | SenseCAP M2, 8 canales, US915 sub-banda 2, Basics Station sobre TLS mutuo |
| Servidor de red | ChirpStack 4.19.0 (servidor en la nube) |
| Consola / API | `lns.pi-caro.org` · `api.pi-caro.org` |
| Broker MQTT | `mqtt.pi-caro.org:8883` (TLS) |
| Captura en servidor | Dashboard PICARO Mission Control → SQLite |
| Device | `0011223344550001` — **el mismo del ejercicio 09**, reutilizado |
| Device profiles | Dos perfiles **nuevos** (Clase A y Clase C), ambos con el codec de 11/14 bytes |

> **El servidor no se modifica.** La configuración global —regiones, `rx1_delay`,
> temporizadores— queda intacta: la comparten el ejercicio 09 y los equipos del
> curso, y alterarla por este experimento rompería trabajo ajeno.
>
> Lo admisible es **añadir**: los dos device profiles nuevos no tocan nada
> existente. El device se reutiliza y se le **conmuta el perfil** según lo que se
> vaya a ejecutar —ejercicio 09, corrida Clase A o corrida Clase C— y se devuelve
> al perfil del ejercicio 09 al terminar la campaña.

### 4.3 Emplazamientos

| Punto | Coordenadas | Terreno | Antena sobre el suelo |
|---|---|---|---|
| **Gateway** | `21.92, -102.27` | 2000 m snm ⚠️ | 15,5 m |
| **CERRO16** | `21.8741637679742, -102.42482836119612` | 2400 m snm | ~1,5 m |
| **TERRAZA** | `21.93, -102.30` | < 1900 m snm | ~15 m (piso 5) |

Los 15,5 m del gateway se descomponen en azotea de casa de dos plantas (8 m),
base del tinaco (1,5 m) y mástil (6 m). Antena **Raigen de fibra de vidrio,
5,8 dBi**, con 90 cm de coaxial (~0,3 dB de pérdida, despreciable).

**Distancias medidas (haversine):**

| Trayecto | Distancia | Rumbo |
|---|---|---|
| Gateway ↔ CERRO16 | **16,35 km** | — |
| Gateway ↔ TERRAZA | **2,74 km** | 118° (ESE) desde el edificio |

> ⚠️ **Dato pendiente de verificar.** La altitud de 2000 m del gateway procede de
> leer la curva de nivel más cercana en Google Maps, no de una medición. Resulta
> sospechosa: sitúa el gateway 100 m por encima de un edificio de la ciudad a
> 2,74 km, estando montado sobre una vivienda y no sobre un promontorio. Si el
> valor real fuese ~1890 m, la tabla de despeje de §9.5 se desplaza unos 110 m y
> el margen disponible se reduce en la misma medida. **Verificar antes de dar por
> cerrada la evaluación de H5.**
>
> **Verificado el 2026-08-29:** la sospecha era fundada — **1914 msnm** medidos
> en sitio (86 m menos). La distancia real al punto de operación del cerro es
> **15,266 km**. La evaluación con el perfil real está en la nota de revisión de
> §9.5: trayecto despejado.

### 4.4 Presupuesto de enlace calculado

Para el trayecto al cerro, en condiciones de espacio libre:

| Magnitud | Valor |
|---|---|
| Potencia de transmisión | +20 dBm |
| Ganancia de antena del nodo | ~2 dBi |
| FSPL a 16,35 km / 915 MHz | 115,9 dB |
| Ganancia de antena del gateway | +5,8 dBi |
| Pérdida de cable | −0,3 dB |
| **Potencia recibida estimada** | **−88,4 dBm** |

| Data Rate | Sensibilidad | Margen |
|---|---|---|
| DR0 / SF10 | −132 dBm | **43,6 dB** |
| DR1 / SF9 | −129 dBm | 40,6 dB |
| DR3 / SF7 | −125 dBm | 36,6 dB |

Para el escenario TERRAZA (2,74 km), el margen en SF7 es de **52,1 dB**.

La conclusión metodológica de estos números está en §2.2: el enlace no está
limitado por el presupuesto sino por la geometría del trayecto.

---

## 5. Diseño experimental

### 5.1 Matriz de corridas

Diseño factorial completo, 3 escenarios × 2 clases:

| Corrida | Escenario | DR / SF | Payload | Airtime aprox. | Intervalo | Duración | Clase | fPort |
|---|---|---|---|---|---|---|---|---|
| **1A** | URBANO — vehículo a 30–40 km/h | DR1 / SF9 | 14 B | ~226 ms | 8 s | 40 min | A | 11 |
| **1C** | URBANO — vehículo a 30–40 km/h | DR1 / SF9 | 14 B | ~226 ms | 8 s | 40 min | C | 12 |
| **2A** | TERRAZA — piso 5 exterior, LoS, 2,74 km | DR3 / SF7 | 14 B | ~72 ms | 8 s | 40 min | A | 13 |
| **2C** | TERRAZA — piso 5 exterior, LoS, 2,74 km | DR3 / SF7 | 14 B | ~72 ms | 8 s | 40 min | C | 14 |
| **3A** | CERRO16 — LoS a 16,35 km | DR0 / SF10 | 11 B | ~371 ms | 8 s | 40 min | A | 15 |
| **3C** | CERRO16 — LoS a 16,35 km | DR0 / SF10 | 11 B | ~371 ms | 8 s | 40 min | C | 16 |
| **4A** | VUELO — puntos fijos en altura y distancia (D-64) | DR0 / SF10 | 3 × 11 B | ~371 ms c/u | 20 s (ráfaga de 3 por minuto) | 55 min | A | 17 |

**VUELO (4A), añadida el 2026-09-28 (D-64).** No forma parte del factorial A×C: simula la
telemetría de la cápsula (55 min de vuelo) mandando **todos** los sensores de la T-Beam en
tres paquetes de 11 bytes por minuto, y se corre desde **puntos fijos** a distintas
distancias y alturas. Su objetivo es validar la curva de alcance de SF10 obtenida en el
cerro el 2026-09-27 (margen de +12,8 dB a 15,27 km; `analisis/resultados/20260927_cerro/INFORME.md`
§6) y comprobar que los downlinks (pings, y por extensión el corte) llegan a esa distancia.
Criterio de aceptación: PDR ≥ 50 %, el mismo que el cerro. Formato y métricas en
[`VUELO-ESPEC.md`](VUELO-ESPEC.md); análisis con `analisis/vuelo.py`.

Las duraciones son **consecuencia** de fijar 300 uplinks por corrida (§5.2), no un
parámetro independiente.

Notas sobre la elección de DR:

- **DR0 / SF10 es el máximo alcance disponible en US915.** SF11 y SF12 no existen
  para uplink en esta región. El escenario 3 usa por tanto el mejor presupuesto
  de enlace que la banda permite.
- **DR0 limita el payload a 11 bytes** por la restricción de *dwell time* de
  400 ms de US915 (~371 ms de airtime con 11 bytes). Esta restricción determinó
  el formato de payload de todo el proyecto (§7.2).
- **Los intervalos son consecuencia, no elección.** El servidor tiene
  `rx1_delay = 5 s` y no se modifica (§3.3, §4.2). En Clase A no se puede
  transmitir hasta cerrar RX1 (5 s) y RX2 (6 s), de modo que el ciclo mínimo es
  `airtime + rx1_delay + 1 s (RX2) + margen` ≈ **6,5 s**. Los intervalos de
  5 / 2,5 / 3 s de la versión 1.0 eran **físicamente imposibles**: el stack los
  habría retrasado por su cuenta y la cadencia real no habría coincidido con la
  nominal, invalidando el cálculo de ciclo de trabajo. Los 7 / 7 / 8 s actuales
  son el mínimo con margen razonable.

### 5.2 Tamaño de muestra

Fijado **antes** de la toma de datos:

| Métrica | Valor por corrida | Justificación |
|---|---|---|
| **Uplinks** | **300 exactos** — la corrida termina al alcanzarlos | Con PDR ≈ 0,8 el error estándar es √(0,8·0,2/300) ≈ 2,3 pp. La diferencia de dos proporciones queda en ≈ 3,3 pp, de modo que el efecto mínimo de 5 pp de H2 sigue siendo resoluble, aunque con menos holgura que con 600 |
| **Duración** | *Derivada:* 35 / 35 / 40 min | Consecuencia del intervalo de cada escenario |
| **Pings de downlink** | **≥ 30** por corrida | Permite estimar mediana y RIC de la latencia con robustez |

**Por qué 300 y no 600.** Con intervalos de 7–8 s, 600 uplinks serían 70–80 min por
corrida y unas **7 horas de campo** para las seis, sin contar desplazamientos.
300 mantienen un PDR estable y hacen la campaña ejecutable en las fechas
previstas. Es una concesión consciente de precisión a favor de viabilidad, y
queda declarada aquí en lugar de descubrirse a mitad de campaña.

**Por qué se fija el número de uplinks y no el tiempo.** Con una duración fija de
35 minutos los escenarios darían 300, 300 y 262 uplinks: el del cerro tendría
menos muestras y su PDR no sería directamente comparable por tener distinta
precisión estadística. Fijando *n* se iguala el peso estadístico de las seis
corridas. La disparidad es menor que en la versión 1.0 —los intervalos son ahora
casi iguales— pero el criterio se mantiene, y además el firmware cuenta paquetes,
no minutos.

Una corrida que no alcance los 300 uplinks se **marca como parcial y se repite**.
Los datos parciales se conservan, pero solo las corridas completas entran en el
análisis principal; su uso en cualquier análisis secundario debe declararse.

**Cómo se separan los intentos.** Un intento parcial y su repetición comparten
escenario, clase y `fPort`, de modo que sin una separación explícita acabarían
mezclados y el conjunto resultante no describiría ninguna de las dos situaciones. El
firmware la establece en el origen: al reanudar una corrida abortada el mismo día
sondea la microSD y abre un fichero nuevo con número de intento
(`20260814-CERRO16-C-2.csv`). El análisis los trata como **corridas distintas** —
todos figuran en `resumen.csv`, pero la comparación A vs C (H2) y las figuras utilizan
el intento **más completo** de cada celda y declaran por escrito cuáles quedaron fuera.

La alternativa —fundir los intentos— fue descartada: si una corrida se abortó fue por
alguna razón, casi siempre un cambio en las condiciones, y sumar 20 uplinks tomados
bajo una circunstancia a 300 tomados bajo otra introduce precisamente el sesgo que el
control de H2 pretende detectar. Sumarlos después, si se justifica, es trivial;
separarlos una vez mezclados, imposible.

### 5.3 Réplicas y orden

- **Réplicas:** 1 réplica por celda en la primera campaña (6 corridas). El par
  A/C de cada escenario actúa además como réplica de la medida de cobertura
  (§2.1).
- **Alternancia obligatoria:** dentro de un escenario, las corridas A y C se
  ejecutan **el mismo día y consecutivas**, alternando el orden de inicio entre
  escenarios (p. ej. esc.1 → A,C; esc.2 → C,A; esc.3 → A,C). Esto reparte
  cualquier deriva temporal entre ambas clases en lugar de cargarla sobre una.
- **Carga de batería:** cada corrida comienza con la batería a plena carga y la
  misma referencia de tensión.

### 5.4 Nota de estado — Serie 1 ejecutada, Serie 2 en curso

> **Serie 1 (16-21 de agosto de 2026).** Se ejecutaron corridas de los
> escenarios URBANO y TERRAZA. **Ninguna corrida alcanzó el criterio de PDR**
> de §10.2 (PDR observado entre 3 % y 69 %, frente al ≥ 80 % exigido en esos
> escenarios). El diagnóstico posterior —cuatro pruebas de banco con el mismo
> equipo, PDR 96,7-100 %— descarta una avería (`docs/PRUEBA-RF-BANCO.md`;
> A-09 reformulada en la bitácora). La explicación es que el escenario URBANO
> es **NLOS y se aleja hasta 6 km** en vehículo: a 300 m el mismo equipo
> entrega el 97 %. Es un resultado legítimo del protocolo (§10.1: rechazar una
> hipótesis no es un fracaso), no un fallo de método.
>
> **Serie 2 (2026-08-30).** Ejecuta cuatro corridas, no las seis de la matriz
> de §5.1: **URBANO Clase C, CERRO16 Clase A, CERRO16 Clase C y una repetición
> de URBANO Clase C** (fPort 12, 15, 16 y 12 de nuevo, con sufijo `-2` por
> §5.2). Da el primer dato real de cobertura del escenario CERRO16 —las
> corridas etiquetadas `CERRO16-A/C` anteriores eran pruebas de banco en
> entorno urbano, no el cerro, y quedan fuera del análisis— y el primer par
> A/C del cerro para H4. El trayecto está verificado LoS con Fresnel despejado
> (§9.5) y el pronóstico de enlace es favorable. Detalle completo del plan,
> pronóstico numérico y riesgos operativos en [`../BITACORA.md`](../BITACORA.md),
> entrada 2026-08-30 (plan).
>
> El escenario TERRAZA y el resto de la matriz de §5.1 no cubierto por la
> Serie 1 ni la Serie 2 quedan pendientes de una campaña posterior.

---

## 6. Procedimiento de campo

### 6.1 Antes de salir

1. Verificar que el gateway aparece **ONLINE** en la consola.
2. Confirmar `rx1_delay = 5 s` en la configuración de región del servidor.
   **No se modifica:** los intervalos del experimento se derivan de él, no al revés.
   El firmware fuerza un **join OTAA real en cada arranque** (`FORCE_FRESH_JOIN = 1`):
   `JOIN OK` prueba que hay gateway en rango, en lugar de reutilizar una sesión de NVS
   que dejaría transmitir sin enlace confirmado. Un join que no entra en el cerro
   **aborta la corrida y es un resultado válido** (no hay cobertura en ese punto), no
   un fallo del equipo; se registra en la hoja de campo.
3. Asignar al device `0011223344550001` el **device profile correspondiente a la
   clase de la corrida** (A o C) y confirmar que lleva el codec de 11/14 bytes
   (`python servidor/perfil.py terreno-a` o `terreno-c`; ver §6.4).
   Al terminar la campaña, devolverlo al perfil del ejercicio 09.
4. Arrancar el dashboard en modo `mqtt` y comprobar que recibe.
5. Insertar microSD **vacía o con nombre de corrida único**; verificar espacio.
6. Sincronizar el reloj del equipo que encola downlinks con UTC.
7. Cargar la batería al 100 %.

### 6.2 Por cada corrida

El orden de los tres primeros pasos **no es arbitrario**: el device profile va antes
que todo lo demás porque es la única condición del experimento que la sonda no puede
verificar ni corregir por sí misma (§6.4).

1. **Ajustar el device profile del servidor a la clase de la corrida**
   (`python servidor/perfil.py terreno-a` | `terreno-c`).
2. Encender la sonda y esperar `JOIN OK` en el OLED. El join ocurre **antes** de
   elegir la corrida, de modo que al confirmar el primer uplink salga en el acto.
3. En el menú, seleccionar escenario y clase con **pulsaciones cortas**, y verificar
   en pantalla que el `fPort` y el perfil requerido son los previstos.
   **Navegar el menú no transmite:** nada se aplica hasta confirmar.
4. Verificar en la traza serie: región, DR, SF, clase y **ADR desactivado**. El
   `rx1_delay` debe ser **5 s**, que es el valor del servidor y no se modifica; si
   aparece otro, la sesión guardada en NVS es antigua y hay que rehacer el join.
5. Esperar **fix GNSS válido** (≥ 4 satélites).
6. **Arrancar con doble pulsación** y registrar en la hoja de campo (§6.3) la hora
   UTC de inicio. La corrida comienza en ese instante, no antes.
7. Ejecutar hasta **300 uplinks** sin interrupciones. El firmware indica el progreso
   en el OLED (`TX n/300`) y muestra `FINALIZADO` al terminar, sin encadenar la
   siguiente corrida.
8. Durante la corrida, encolar **≥ 30 pings de latencia** (fPort 98) en instantes
   **aleatorios**, no periódicos, para no correlacionarlos con el ciclo de uplink.
9. Registrar hora UTC de fin y observaciones.
10. Extraer y respaldar el CSV de la microSD **antes** de la siguiente corrida.

**Si una corrida se aborta** (pulsación larga), lo registrado se conserva: al reanudar
el mismo escenario y clase el mismo día, el firmware crea un fichero con número de
intento (`20260814-CERRO16-C-2.csv`) en lugar de reutilizar el anterior. Los intentos
se analizan como **corridas distintas** (§5.2). Debe anotarse **el motivo del aborto**
en la hoja de campo: un intento corto sin explicación no es interpretable.

> En la cima del Cerro del Muerto **sí hay cobertura de datos** (verificado en
> sitio el 2026-07-19), pero no se depende de ella. El OLED es la
> única forma de verificar en campo que la sonda transmite y mantiene fix, y el
> log de microSD el único registro hasta el regreso. Comprobar el OLED antes de
> dar por iniciada la corrida deja de ser cómodo y pasa a ser obligatorio.

### 6.3 Hoja de campo (registro manual)

Hay información que **ningún log captura** y sin la cual los datos no se
interpretan después. La cumplimenta el **asistente desde el móvil**, con
`campo/hoja-de-campo.html`, que funciona **sin conexión**. Aunque en la cima del
Cerro del Muerto sí hay cobertura (§6.2), el procedimiento no depende de ella:
puede fallar, y la hoja tiene que seguir sirviendo.

| Campo | Ejemplo |
|---|---|
| ID de corrida | `20260814-CERRO16-C` |
| Hora UTC inicio / fin | 17:02 / 17:32 |
| Operador / asistente | — |
| Meteorología | despejado, 24 °C, viento flojo |
| Modo de desplazamiento | estático / a pie / vehículo a ~40 km/h |
| Ruta seguida | descripción o traza |
| Obstáculos a la vista | arbolado denso tramo km 3–4 |
| Altura de la sonda sobre el suelo | 1,5 m (en mano) |
| Orientación de la antena | vertical |
| Incidencias | pérdida de fix en túnel 17:31–17:33 |

### 6.4 Dependencia crítica: el device profile del servidor

**La clase LoRaWAN se configura en dos sitios y ambos deben coincidir.** El firmware
determina cómo se comporta el **nodo** (si mantiene o no la ventana RXC abierta); el
device profile de ChirpStack determina cómo se comporta el **servidor** (si encola el
downlink de inmediato o espera a la ventana RX del siguiente uplink). Medir la
latencia de Clase C exige las dos mitades.

Esta es la **única condición del experimento que el dispositivo no puede verificar ni
corregir**, y su modo de fallo es especialmente traicionero:

| | Con el perfil correcto | Con el perfil equivocado (nodo en C, servidor en A) |
|---|---|---|
| Uplinks | llegan | llegan igual |
| PDR | correcto | correcto |
| `fPort` | 16 (CERRO16-C) | 16 (CERRO16-C) — **la corrida se etiqueta como Clase C** |
| Latencia de downlink | < 1 s | segundos, hasta el siguiente uplink |
| Aviso de error | — | **ninguno** |

El resultado se lee como *«la Clase C no aporta ninguna ventaja»*, que es exactamente
la conclusión contraria a la que llevarían los datos bien tomados. **H4 quedaría
refutada por un error de configuración, no por el fenómeno físico.**

Mitigaciones adoptadas:

1. El menú de la sonda muestra, junto a la corrida seleccionada, el perfil que debe
   estar activo (`Perfil: terreno-c`), de modo que el operador lo verifique en el
   único momento en que puede hacerlo: antes de arrancar.
2. El ajuste del perfil es el **paso 1** del procedimiento de cada corrida (§6.2) y
   del manual de campo, por delante de encender la sonda.
3. `servidor/perfil.py` hace el cambio en un comando y **verifica el resultado**, en
   lugar de depender de la navegación por la consola web.

Ninguna de las tres es una comprobación automática. Si al analizar una corrida de
Clase C las latencias salen del orden del intervalo de uplink, la primera hipótesis a
descartar es esta, **no** una limitación de la Clase C.

### 6.5 Seguridad del mecanismo de corte

**En esta campaña no existe actuador físico.** La placa va soldada y no se le
añade hardware, así que ningún mecanismo recibe la orden y el firmware no
conmuta ningún GPIO (`CORTE_HABILITAR_GPIO = 0`). La variable que se mide es la
**latencia del comando de downlink**: el instante de llegada registrado por la
sonda, cruzado con el de envío registrado por el servidor.

El comando de corte se mantiene en el diseño porque es el caso de uso que
justifica la Clase C —una orden de liberación que llega tarde es inútil— y
porque podría montarse hardware más adelante. La distinción entre ambos fPort
sigue vigente:

- **fPort 99, byte mágico `0xA5`** → corte real. Cualquier otro valor se ignora
  y se registra.
- **fPort 98, cualquier byte** → ping de latencia: solo enciende el LED y marca
  tiempo. **No** actúa sobre el mecanismo.

Las ≥ 30 medidas de latencia por corrida se toman **siempre con fPort 98**.
Medir latencia con el comando real implicaría accionar el cortador decenas de
veces por corrida, lo que es inviable y peligroso.

---

## 7. Instrumentación y captura de datos

### 7.1 Tres fuentes, y por qué las tres

| Fuente | Qué registra | Por qué es imprescindible |
|---|---|---|
| **(a) Dispositivo → microSD** | Lo que se **envió** | El servidor solo ve lo que llegó. Sin el registro del emisor **no se puede distinguir "no se envió" de "se perdió"**, y por tanto no se puede calcular PDR |
| **(b) Servidor → SQLite** | Lo que **llegó**, con RSSI/SNR/gateway | Aporta la calidad de enlace, que el nodo no conoce |
| **(c) Log de downlinks (dispositivo)** | Instante UTC de recepción de cada comando | Único punto donde se observa el extremo receptor de la latencia |

Esta redundancia es el núcleo metodológico del experimento: **la métrica
principal (PDR) sólo existe como intersección de (a) y (b)**.

### 7.2 Formato de registro (a) — microSD

CSV, una fila por intento de transmisión:

```
run_id,fcnt,utc,lat,lon,alt,sats,fix,temp_c,batt_mV,batt_mA,dr,sf,airtime_ms,tx_rc
```

`tx_rc` registra también los **intentos fallidos localmente**, que no aparecerán
en el servidor y que deben contarse como enviados o excluirse de forma explícita
y documentada.

### 7.3 Formato de registro (b) — servidor

El dashboard almacena en SQLite, por uplink: `fCnt`, `fPort`, `rssi`, `snr`,
`gateway_id`, `dr`, marca de tiempo, `object` decodificado y `raw_json`.

### 7.4 Clave de unión y etiquetado

- **Clave de unión: `fCnt`.** Contador de trama, único y creciente dentro de la
  sesión LoRaWAN. Permite el `JOIN` entre (a) y (b) y la identificación exacta de
  los paquetes perdidos.
- **Etiquetado de corrida: `fPort` 11–16.** El puerto de aplicación viaja fuera
  del payload y el servidor lo registra en cada uplink, por lo que identifica la
  combinación escenario × clase **a coste cero de tiempo de aire**. Cada paquete
  queda autoetiquetado y el análisis separa las corridas sin intervención manual.

### 7.5 Sincronía temporal

Ambos extremos se refieren a **UTC procedente del GNSS L76K**. Es lo que hace
medible la latencia de downlink: el instante de encolado se registra en el
servidor y el instante de activación del GPIO en el nodo, y ambos comparten
referencia. Sin esta sincronía, la latencia medida incluiría la deriva
desconocida entre dos relojes independientes.

**Requisito:** no iniciar corrida sin fix GNSS válido, ya que la referencia
horaria depende de él.

---

## 8. Plan de análisis

### 8.1 Preparación

1. Cargar CSV de microSD (a) y volcado SQLite (b).
2. `JOIN` por `fCnt` dentro de cada `run_id`.
3. Clasificar cada trama enviada como **entregada** o **perdida**.
4. Calcular distancia nodo–gateway por Haversine para cada trama.
5. Descartar tramas sin fix GNSS válido (documentando cuántas).

### 8.2 Contraste por hipótesis

| Hipótesis | Métrica | Prueba | α |
|---|---|---|---|
| **H1** cobertura entre escenarios | PDR | χ² de independencia (entregado × escenario) | 0,05 |
| **H2** control clase↔cobertura | PDR | χ² por escenario **y** tamaño de efecto; **se espera no rechazar**. Problema solo si χ² significativo **y** Δ > 5 pp | 0,05 |
| **H3** consumo A vs C | Ī (mA) | *t* de Student **pareado** por escenario | 0,05 |
| **H4** latencia de downlink | ms | *U* de Mann-Whitney (no se asume normalidad) | 0,05 |
| **H5** viabilidad 16,35 km | PDR, SNR | Estimación puntual + IC binomial (Wilson) 95 % | — |

Se emplean pruebas no paramétricas para la latencia porque su distribución en
Clase A es aproximadamente uniforme, no normal.

### 8.3 Productos gráficos

1. **PDR por escenario y clase** — barras con IC 95 %.
2. **PDR frente a distancia** — bins de distancia, un trazo por escenario.
3. **RSSI y SNR frente a distancia** — dispersión con mediana móvil.
4. **Curva de descarga de batería** — tensión y corriente frente a tiempo, A y C
   superpuestas; la **pendiente** es el resultado de H3.
5. **Distribución de latencia de downlink** — histograma o violín, A vs C.
6. **Mapa del track** con los puntos coloreados por RSSI y los perdidos marcados.
7. **Airtime acumulado y ciclo de trabajo** por corrida.

### 8.4 Métricas derivadas a reportar

- Autonomía estimada (h) por clase.
- Ciclo de trabajo real (%) por escenario.
- Distancia máxima con PDR ≥ 80 %.
- Diferencia de latencia mediana A − C (ms) y su intervalo de confianza.

---

## 9. Amenazas a la validez

### 9.1 Deriva temporal de la propagación

Las condiciones de propagación varían con la hora, el tráfico y la meteorología.
**Mitigación:** corridas A y C del mismo escenario consecutivas y el mismo día
(§5.3); alternancia del orden entre escenarios.

### 9.2 Variabilidad de la ruta en el escenario móvil

En el escenario 1 el recorrido no será idéntico entre corridas.
**Mitigación:** ruta predefinida y anotada en la hoja de campo; análisis de PDR
**por tramo de distancia**, no agregado, para reducir el efecto de la geometría.

### 9.3 Caída de tensión de batería (confusor entre H3 y H1)

Este es el confusor más sutil del diseño. A medida que la batería se descarga, la
tensión disponible puede **reducir la potencia real de transmisión**. Si una
corrida se prolonga o parte de menor carga, se degradaría el PDR por una causa
ajena al escenario, y se atribuiría erróneamente a la propagación —confundiendo
la variable de autonomía con la de cobertura.

**Mitigación:** carga inicial idéntica (100 %) en todas las corridas; duración
acotada y equivalente; registro de `batt_mV` en cada trama para poder verificar
*a posteriori* que la tensión no cayó por debajo del umbral de regulación; si lo
hizo, se trunca la corrida en ese punto para el análisis de cobertura.

### 9.4 Verificación de que la Clase C está realmente activa

Un fallo silencioso en `setClass()` produciría dos corridas idénticas y un
resultado espurio de "la Clase C no consume más".
**Mitigación:** H3 con magnitud esperada explícita (5–10 mA). Un resultado
inferior a 3 mA **obliga** a verificar la configuración antes de interpretar
nada. Verificación adicional: la latencia de downlink (H4) debe caer
drásticamente; si no lo hace, la clase no está activa.

### 9.5 Despeje del terreno en el enlace de 16,35 km

> **Revisión 2026-08-29 (cierra A-03 y A-05).** Con las coordenadas y altitudes
> reales medidas en sitio —gateway a **1914 msnm** (no 2000) y cerro a
> **2250 msnm** (no 2400), distancia real **15,266 km** (no 16,35; el nombre
> CERRO16 se conserva)— el perfil de elevación SRTM 30 m confirma **línea de
> vista con el 60 % de la primera zona de Fresnel despejado en todo el
> trayecto**. Punto medio (7,63 km): r1 = 35,4 m, 60 % = 21,2 m, abombamiento
> 3,4 m, línea de vista 2090,5 m sobre terreno de ~1890 m (margen ~178 m). El
> punto más ajustado está a 340 m del gateway, con **+23,1 m** de margen sobre
> el entorno urbano. FSPL a 15,27 km: 115,3 dB ⇒ margen SF10 ≈ **44,2 dB**.
> Perfil completo en `analisis/perfil_elevacion.csv` y entrada 2026-08-29 de la
> bitácora. **La tabla siguiente queda superada**: se calculó con los 2000 m
> estimados del gateway y las coordenadas antiguas; se conserva como registro.

**El SF no es el factor dominante a esa distancia** (§2.2, §4.4). Con 43,6 dB de
margen en SF10, el resultado de H5 depende esencialmente del **despeje de la
primera zona de Fresnel**.

Parámetros calculados para el trayecto gateway ↔ CERRO16 *(superados, ver nota)*:

| Magnitud | Valor |
|---|---|
| Radio de la 1.ª zona de Fresnel en el punto medio (8,2 km) | **36,6 m** |
| Despeje recomendado (60 %) | **22,0 m** |
| Abombamiento terrestre en el punto medio (k = 4/3) | 3,9 m |

De ahí se deriva la **altitud máxima admisible del terreno** en cada punto del
trayecto. Si el perfil real la supera en algún punto, hay obstrucción aunque
exista línea de vista óptica:

| km desde el gateway | Terreno máx. | | km desde el gateway | Terreno máx. |
|---|---|---|---|---|
| 0,5 | 2019 m | | 8,2 *(punto medio)* | **2183 m** |
| 1 | 2027 m | | 10 | 2226 m |
| 2 | 2046 m | | 12 | 2276 m |
| 4 | 2088 m | | 14 | 2329 m |
| 6 | 2132 m | | | |

**Verificación pendiente (A-03 en la bitácora).** ~~Contrastar esta tabla con el
perfil de elevación real entre ambas coordenadas antes de la primera corrida.~~
**Hecha el 2026-08-29** con el perfil SRTM 30 m real: trayecto despejado (ver la
nota de revisión al inicio de esta sección). A-03 y A-05 cerradas en la bitácora.

Para el escenario TERRAZA (2,74 km) el radio de Fresnel en el punto medio es de
15,0 m (60 % = 9,0 m). Con el terreno urbano en torno a 1900 m y la línea de vista
a 1965 m, obstruir requeriría un edificio de unas 18 plantas en el punto medio.

SF10 proporciona el margen que la banda permite; **la geometría del trayecto
decide si ese margen se aprovecha**. Un resultado negativo en H5 debe reportarse
como una limitación de la instalación y el trayecto evaluados, no como una
propiedad del protocolo.

### 9.6 Validez externa

Los resultados son válidos para esta instalación de gateway, esta banda y este
hardware. La extrapolación a otras instalaciones requiere replicar el
procedimiento. En particular, el escenario 3 caracteriza **un** enlace de 16,35 km,
no la clase de todos los enlaces de esa distancia.

### 9.7 Réplica única

Con una sola réplica por celda no se puede separar la variabilidad entre
corridas de la debida al tratamiento. Se declara explícitamente y se propone
como ampliación de la campaña. El control de §2.1 mitiga parcialmente esta
limitación al proporcionar una réplica implícita de la medida de cobertura.

---

## 10. Criterios de éxito

### 10.1 Éxito del experimento (independiente del resultado)

El experimento se considera **exitoso** si, al margen de qué hipótesis se
confirmen:

- [ ] Se completan las **6 corridas** con **300 uplinks** cada una.
- [ ] Se obtienen **≥ 30 medidas de latencia** válidas por corrida.
- [ ] Las tres fuentes de datos se cruzan sin pérdida: toda trama en (a) tiene
      resolución conocida —entregada o perdida— en (b).
- [ ] **H2 no se rechaza** (control superado, §2.1).
- [ ] Todas las corridas disponen de hoja de campo completa.
- [ ] Los datos brutos quedan respaldados y son reproducibles desde cero.
- [ ] La verificación A-03 (perfil de elevación) se completó **antes** de la
      corrida del cerro.

Nótese que **rechazar una hipótesis no es un fracaso**: un PDR bajo a 16,35 km es un
resultado, y documenta el límite real del sistema. El fracaso sería no poder
saber si el dato es fiable.

### 10.2 Criterios técnicos por hipótesis

| Hipótesis | Criterio | Resultado esperado |
|---|---|---|
| H1 | χ², α = 0,05 | Rechazo de H0 (los escenarios difieren) |
| H2 | χ² significativo **y** \|ΔPDR\| > 5 pp | **No** rechazo (control) |
| H3 | ΔĪ ≥ 3 mA, *t* pareado | Rechazo de H0 (C consume más) |
| H4 | mediana(C) ≤ 1 s, Mann-Whitney | Rechazo de H0 (C responde antes) |
| H5 | PDR ≥ **50 %**, SNR ≥ −15 dB | Sin predicción; es una medición de viabilidad |

Umbral de **cobertura útil** en los escenarios 1 y 2: **PDR ≥ 80 %**. En CERRO16
el umbral es del 50 % por las razones expuestas en H5.

### 10.3 Entregables

1. Datos brutos: CSV de microSD (6) + volcado SQLite del servidor.
2. Hojas de campo (6).
3. Cuaderno de análisis reproducible (`../analisis/`).
4. Las siete gráficas de §8.3.
5. Informe de resultados con contraste de las cinco hipótesis.
6. Registro de cualquier desviación respecto a este protocolo, en
   [`../BITACORA.md`](../BITACORA.md).

---

## Anexo A — Parámetros de configuración fijados

| Parámetro | Valor |
|---|---|
| Región | US915, sub-banda 2 (canales 8–15 + 65) |
| Versión LoRaWAN | 1.0.x, activación OTAA |
| ADR | Desactivado |
| `rx1_delay` (servidor) | **5 s** — valor del servidor compartido, no se modifica |
| Payload | 11 bytes (+3 opcionales de batería cuando el DR lo permite) |
| fPort de uplink | 11–16 según corrida |
| fPort de corte real | 99, byte `0xA5` |
| fPort de ping de latencia | 98 |
| Clases evaluadas | A y C |
| Intervalo de uplink | **8 s** en los tres escenarios |
| Device | `0011223344550001` (compartido con el ejercicio 09) |
| Device profiles | Dos nuevos (Clase A / Clase C), se conmutan según la corrida |
| Uplinks por corrida | 300 |
| Réplicas | 1 por celda (6 corridas) |
| Selección de corrida | Botón físico, persistida en NVS |
| Mecanismo de corte en campo | Sin hardware; solo se mide latencia de comando |
| Fechas previstas | 14–16 de agosto de 2026 |
| Equipo | 2 personas (operador y asistente) |

## Anexo B — Estructura del payload

```c
typedef struct __attribute__((packed)) {
    int32_t latitude;    // grados × 1e7    (4 bytes)
    int32_t longitude;   // grados × 1e7    (4 bytes)
    int16_t altitude;    // metros          (2 bytes)
    int8_t  temperature; // °C × 2          (1 byte)
} RadiosondaPayload_t;   //                 = 11 bytes
```

En los escenarios 1 y 2 (DR1 y DR3) se añaden 3 bytes opcionales
(`batt_mV` uint16 + `batt_pct` uint8), que **no caben en DR0** por el límite de
11 bytes de US915. El codec del servidor decodifica por longitud.

La consecuencia metodológica es que **en el escenario 3 la telemetría de batería
sólo existe en el registro de microSD**, no en el servidor. El análisis de H3 se
apoya, por tanto, siempre en la fuente (a), que está disponible en las seis
corridas.

---

_Documento interno del proyecto `pruebas_terreno`. No se publica en el
repositorio `radiosonda_PIcaro` ni en su wiki._

---

# Adenda 1 — La autonomía no es medible en las corridas de campo

*Añadido el 2026-07-19, tras implementar el firmware. Afecta a H3.*

Al escribir el driver del PMU se descubrieron dos hechos que invalidan el
planteamiento original de la hipótesis de autonomía:

**1. El AXP2101 no mide corriente de batería.** Solo expone tensión y
porcentaje. El ADC de corriente existía en el AXP192 de placas anteriores, no
en este. La columna `batt_mA` del CSV queda vacía por diseño.

**2. Una corrida de 35–40 min no resuelve la diferencia.** Si la autonomía debe
deducirse de la pendiente de descarga, el orden de magnitud no da:

| Duración | Consumo extra en Clase C | Caída de tensión asociada |
|---|---|---|
| **0,6 h (una corrida)** | 3,6 mAh · 0,12 % | **≈ 1,4 mV** |
| 4 h | 24 mAh · 0,8 % | ≈ 9,6 mV |
| 24 h | 144 mAh · 4,8 % | ≈ 58 mV |

El ruido de la lectura de batería bajo los pulsos de ~120 mA del transmisor es
de **5–20 mV**. En una corrida la señal buscada es un orden de magnitud menor
que el ruido: cualquier valor que se obtuviera sería indistinguible de la
deriva del sensor.

## Corrección del protocolo

**H3 sale de la campaña de campo y pasa a un ensayo de banco independiente.**
Las 6 corridas siguen sirviendo sin cambios para cobertura (H1, H2, H5) y
latencia (H4).

Dos vías, no excluyentes:

- **Medida directa de corriente** con un medidor USB en línea, en banco, con la
  sonda en cada clase durante unos minutos. Responde a la pregunta de forma
  directa y es lo más barato.
- **Ensayo de descarga largo**: ≥ 20 h por clase, estático, hasta una caída de
  tensión definida. Da una curva real, pero cuesta dos días de banco.

Reportar la autonomía a partir de corridas de 35–40 min habría producido una cifra
con apariencia de medida y sin contenido. Es preferible declararlo aquí.
