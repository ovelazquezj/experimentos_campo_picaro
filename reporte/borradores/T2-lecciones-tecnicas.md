# Lecciones técnicas de las pruebas de terreno LoRaWAN (US915)

> **Borrador T2.** Lecciones para otras universidades que monten una radiosonda o un
> experimento de cobertura LoRaWAN con un servidor ChirpStack propio. No es una
> cronología: cada lección dice qué pasa, por qué y cómo evitarlo.
>
> **Equipos.** Radiosonda PiCARO (T-Beam Supreme, ESP32-S3 + SX1262, RadioLib 7.7.1 sobre
> ESP-IDF) y radiosonda PiCARO (T3/LoRa32, ESP32 + SX1276, sensores simulados). Red:
> ChirpStack v4 (4.19), US915 sub-banda 2, gateways picaro-lab-ags-001 (laboratorio en
> Aguascalientes), ITPA-IOT-GW00 e ITPA-IOT-GW01-kibts (campus del ITPA).
>
> **Cifras.** Salen de los CSV anonimizados de `reporte/datos/` (sesiones, pdr,
> telemetria, latencias, downlinks, incidentes y perfil_cerro). Las que proceden solo de
> la bitácora del proyecto se indican como tales. Lo que es inferencia va marcado como
> *(inferencia)*. Horas en UTC-6.

---

## Índice

1. [Diseño del experimento: dos fuentes para el PDR](#1-diseño-del-experimento-dos-fuentes-para-el-pdr)
2. [La tabla de data rates de US915 no es la de EU868](#2-la-tabla-de-data-rates-de-us915-no-es-la-de-eu868)
3. [Máximo alcance en US915: SF10, y el payload cabe en 11 bytes](#3-máximo-alcance-en-us915-sf10-y-el-payload-cabe-en-11-bytes)
4. [El join también va a SF10](#4-el-join-también-va-a-sf10)
5. [rx1_delay = 5 s fija el intervalo mínimo en Clase A](#5-rx1_delay--5-s-fija-el-intervalo-mínimo-en-clase-a)
6. [ChirpStack congela la clase del dispositivo en el JOIN](#6-chirpstack-congela-la-clase-del-dispositivo-en-el-join)
7. [El ping de latencia debe vivir dentro de la sesión, y la sesión debe morir sola](#7-el-ping-de-latencia-debe-vivir-dentro-de-la-sesión-y-la-sesión-debe-morir-sola)
8. [RadioLib: una JoinAccept ajena envenena el nodo (MIC inválido)](#8-radiolib-una-joinaccept-ajena-envenena-el-nodo-mic-inválido)
9. [Fresnel y perfil SRTM antes de subir al cerro](#9-fresnel-y-perfil-srtm-antes-de-subir-al-cerro)
10. [Lecciones cortas](#10-lecciones-cortas)
11. [Fuentes de las cifras](#11-fuentes-de-las-cifras)

---

## 1. Diseño del experimento: dos fuentes para el PDR

**Contexto.** La métrica principal es el PDR (*packet delivery ratio*): paquetes
recibidos entre paquetes enviados. El servidor de red sabe muy bien qué llegó, pero no
sabe qué se envió.

**Por qué dos fuentes.**

| Fuente | Qué aporta | Qué no puede aportar |
|---|---|---|
| **Sonda → microSD**, una fila por intento de transmisión (`fCnt`, hora GNSS, código de retorno de la radio) | El **denominador**: lo enviado, incluidos los intentos que fallaron en la propia radio | Calidad del enlace |
| **Servidor → base de datos**, una fila por uplink recibido | El **numerador** y la calidad del enlace: RSSI, SNR, gateway, frecuencia, DR | Lo que nunca llegó |

Sin el registro del emisor no se distingue «no se envió» de «se perdió». La clave de
unión es el `fCnt`, y la corrida se identifica por el `fPort` (11-16 = escenario ×
clase), que viaja fuera del payload y no cuesta tiempo en el aire.

**Lo que enseñan los datos: el PDR por huecos de `fCnt` puede engañar.** La alternativa
barata, contar huecos entre el primer y el último `fCnt` recibido, solo ve el tramo
recibido. Si las pérdidas caen al principio o al final, el denominador queda corto y el
PDR sale inflado:

| Corrida | PDR por `fCnt` (solo servidor) | PDR con microSD | Enviados en la microSD |
|---|---|---|---|
| URBANO-A, 18-ago (sesión 23) | 6,5 % (10 de 155) | **3,3 %** (10 de 300) | 300 |
| URBANO-A, 21-ago (sesión 25) | 59,2 % (29 de 49) | **18,3 %** (30 de 164) | 164 |
| TERRAZA-C, 17-ago (sesión 20) | 67,3 % | **66,8 %** (199 de 298 al aire) | 300, 2 fallidos en la radio |

En las 13 corridas con microSD, el cruce contra la base del microservicio y contra la
captura MQTT dio los mismos recibidos (columna de control `recibidos_campo_db`).

**Detalles de método que conviene copiar.**

- **Los fallos locales de transmisión cuentan aparte.** Se registran en la microSD
  (`tx_fallidos`) y el PDR se calcula sobre lo que salió al aire. Por ejemplo, en
  TERRAZA-C fueron 2 de 300.
- **Intervalo de confianza siempre.** El PDR se reporta con IC95 de Wilson. Con 30-35
  uplinks, un 100 % tiene un límite inferior de ~89 %.
- **El nombre de corrida no es una buena clave.** La sonda y el servidor numeran sus
  intentos por separado, y la corrida «-A» de la microSD resultó ser la «-A-2» del
  servidor, porque este ya había gastado el nombre base. Empareja por **ventana
  temporal** o haz que una sola parte asigne el identificador (cuestión A-10).
- **Hora común.** Los dos extremos usan la hora UTC del GNSS. Sin esa referencia, la
  latencia de downlink incluye la deriva entre dos relojes.
- **Un control gratis.** La clase (A o C) no afecta al enlace ascendente, así que el PDR
  no debería cambiar entre A y C en el mismo escenario. Si cambia, falla el método, no
  el fenómeno.

**Cómo evitar problemas.** Guarda en la sonda un CSV por intento de transmisión, con su
código de retorno. Descarga la microSD antes de la corrida siguiente. No publiques un
PDR calculado solo con el servidor sin decir que lo es: la sesión del cerro (41) todavía
lo tiene así (92,0 %, 275 de 299 por `fCnt`) porque su microSD no se ha descargado.

---

## 2. La tabla de data rates de US915 no es la de EU868

**Contexto.** La especificación inicial pedía «SF9 = DR2» y «SF7 = DR4».

**Síntoma (evitado antes de salir a campo).** Con esa tabla, el escenario «SF9» habría
transmitido en SF8 y el «SF7» en SF8 a 500 kHz. El experimento no habría medido lo que
decía medir.

**Causa.** Se trasladaron a US915 los números de EU868.

| DR | US915 (subida) | EU868 |
|---|---|---|
| DR0 | **SF10** / 125 kHz | SF12 |
| DR1 | **SF9** / 125 kHz | SF11 |
| DR2 | SF8 / 125 kHz | SF10 |
| DR3 | **SF7** / 125 kHz | SF9 |
| DR4 | SF8 / **500 kHz** | SF8 |

**Solución.** URBANO a DR1/SF9, TERRAZA a DR3/SF7 y CERRO16 a DR0/SF10 (decisiones D-02
a D-05), con ADR desactivado para que el DR sea una variable controlada (D-06).

**Cómo evitarlo.** Toma la tabla de los *Regional Parameters* de la LoRa Alliance para
tu región, no de un tutorial. Comprueba en el servidor (`txInfo` del uplink) que el SF
que llega es el que programaste: en este proyecto, la columna `sf` de [`telemetria.csv`](../datos/telemetria.csv).

---

## 3. Máximo alcance en US915: SF10, y el payload cabe en 11 bytes

**Contexto.** La pregunta era el alcance máximo, no ahorrar tiempo en el aire.

**Hecho de la norma.** En US915 no hay SF11 ni SF12 de subida. DR0 (SF10/125 kHz) es el
de mayor alcance, unos 9 dB de presupuesto más que SF7. Pero el límite de permanencia
de 400 ms deja **11 bytes de aplicación** en DR0.

**Cálculo reproducible** (fórmula de tiempo en el aire de Semtech, CR 4/5, preámbulo de
8 símbolos, cabecera explícita, CRC, 13 bytes de cabecera LoRaWAN):

| Payload de aplicación | SF | Tiempo en el aire |
|---|---|---|
| 11 B | SF10 | **370,7 ms**, dentro de 400 ms |
| 12 B | SF10 | 411,6 ms, fuera |
| 14 B | SF9 | 226,3 ms |
| 14 B | SF7 | 66,8 ms |

**Solución adoptada (D-09, D-10, D-11).**

- **Estructura base.** 11 bytes, `packed`, *little-endian*: latitud y longitud en
  `int32` (grados × 10⁷), altitud en `int16` y temperatura en `int8` (°C × 2, con paso
  de 0,5 °C, de −64 a +63,5 °C).
- **Por qué cayó la temperatura.** El byte se recortó ahí porque la precisión de
  centésimas era mayor que la incertidumbre del BME280 en campo.
- **Batería opcional.** 3 bytes de batería cuando el DR lo admite (SF9 y SF7). El codec
  decodifica según la longitud recibida.
- **Telemetría de vuelo (D-64).** No cabe en 11 B, así que cada lectura se reparte en
  **3 paquetes de 11 B** con 1 byte de cabecera (tipo + número de ráfaga), en un solo
  fPort y **separados 20 s**, no seguidos. Así, una interferencia de pocos segundos
  tumba un paquete y no la lectura entera.

**Cómo evitarlo.**

- **Diseña el payload para el DR más lento que vayas a usar.** Una estructura de 19
  bytes heredada habría dejado el techo en SF9.
- **Usa centinelas para «no disponible».** Por ejemplo, 0xFF en la batería. Un valor
  saturado se confunde con un dato real, como un 100 % de batería que no existe.
- **Declara el *endianness* en el codec.** El ESP32 es *little-endian*; un codec que lea
  *big-endian* decodifica basura sin dar error.

---

## 4. El join también va a SF10

**Contexto.** Si un join falla en el cerro, la corrida se aborta (D-41: join OTAA real en
cada arranque).

**Hecho.** En US915, RadioLib envía el JoinRequest con `drJoinRequest = 0`, es decir, a
**SF10**: el mismo DR que la corrida de máximo alcance. Un re-join desde el cerro tiene
el mismo alcance que los uplinks.

**Cómo aprovecharlo.** Si tu pila hace el join a un DR más rápido, el join puede fallar
donde los datos llegarían. Comprueba en el código o en el `txInfo` del evento `join`
del servidor a qué SF se une la sonda antes de planificar un sitio lejano.

---

## 5. rx1_delay = 5 s fija el intervalo mínimo en Clase A

**Contexto.** El servidor tenía `rx1_delay = 5 s`, puesto como margen frente a la
latencia hasta un servidor en otro continente. El experimento quería intervalos de
5 s, 2,5 s y 3 s.

**Síntoma.** Con 5 s, esos intervalos son físicamente imposibles. En Clase A la sonda no
transmite hasta cerrar RX1 (a `rx1_delay`) y RX2 (1 s después):

    ciclo mínimo ≈ tiempo en el aire + rx1_delay + 1 s + margen ≈ 6,5 s

Con un intervalo más corto, la pila retrasa la transmisión por su cuenta y la cadencia
real deja de ser la nominal. La Clase C no lo arregla: también abre RX1 tras cada
uplink.

**El atajo que salió mal (R-01 y el incidente I-01).** Se bajó `rx1_delay` a 1 s en la
configuración de **región** del servidor (el RTT medido era de ~180 ms). Ese ajuste es
**global**: otro proyecto del mismo servidor dejó de completar el join. Volver a 5 s lo
restableció al primer intento (R-03). Además, durante el diagnóstico se descartó esa
causa con un argumento plausible y falso («el JoinAccept usa `join_accept_delay`, no
`rx1_delay`»), y se perdieron horas buscando en el firmware.

**Solución (R-04).** El servidor es un dato de entrada y el experimento se deriva de él.

- **Intervalos.** Pasaron de 5 / 2,5 / 3 s a **7 / 7 / 8 s**: el mínimo viable más un
  margen.
- **Duración.** Bajó de 600 a **300 uplinks** por corrida, para que la jornada fuera
  viable. El error estándar del PDR sube de ~1,2 a ~1,7 puntos, √(0,9·0,1/300).
- **Dispositivo.** No se creó uno nuevo. Basta con **dos device profiles** (Clase A y
  Clase C) y conmutar el del dispositivo, que es un cambio aditivo y reversible.

**Consecuencia medible.** En Clase A, la latencia de un downlink no baja de
`rx1_delay`. El ping espera al siguiente uplink y sale 5 s después. En el cerro (sesión
41, uplink cada 8 s, gateway del laboratorio) la mediana fue de **9,6 s**, con un rango
de 4,9 a 22,2 s (n = 28). Cuadra con esperar de media medio intervalo (4 s) más los 5 s
de RX1 *(inferencia sobre el mecanismo)*.

**Cómo evitarlo.**

- **No cambies la configuración global de un servidor compartido.** Ni `region_*.toml`
  ni los temporizadores. Sí puedes crear perfiles y dispositivos.
- **Calcula los intervalos a partir de los temporizadores del servidor**, nunca al
  revés.
- **Pon a prueba primero la hipótesis que te culpa a ti.** Si una explicación exculpa tu
  último cambio, comprobarla deshaciéndolo cuesta minutos.

---

## 6. ChirpStack congela la clase del dispositivo en el JOIN

**Contexto.** La clase (A o C) era una variable del experimento. Un mismo dispositivo
alternaba dos device profiles, y el microservicio de campo conmutaba el perfil al abrir
cada sesión.

**Síntoma.** Según la bitácora del proyecto, en la primera serie de campo la Clase A
recibió **0 downlinks en 764 uplinks**. En los desajustes inversos los downlinks
llegaban, pero medían la latencia de la clase equivocada.

**Causa.** ChirpStack v4 fija la clase efectiva del dispositivo (`classEnabled`) **solo
al procesar el JOIN OTAA**, con el perfil activo en ese momento. Un `PUT` del perfil por
la API no la actualiza (issue público #360 de ChirpStack). La sonda se unía al
encenderse, normalmente antes de que el operador abriera la sesión, así que el servidor
trabajaba con la clase de la corrida anterior. Si la creía en Clase C, enviaba por RX2 a
una sonda en Clase A que ya no escuchaba. El firmware y la radio quedaron exonerados.

**Solución.**

- **Gate de clase (D-60).** Al abrir sesión, el microservicio conmuta el perfil, **lee**
  la clase efectiva (`classEnabled`, en el `GET` del dispositivo, disponible desde
  ChirpStack 4.6) y, si no coincide con la corrida, **rechaza con 409** y un mensaje
  accionable. El perfil bueno ya queda puesto, así que el siguiente join congela la
  clase correcta. Se descartó «abrir con un aviso»: con sol y prisa nadie lo lee, y se
  repetiría el 0/764 con cara de corrida válida.
- **Re-join remoto (D-62).** Ante el 409, la app ordena a la sonda por BLE que rehaga
  el join OTAA sin apagarla y reintenta sola. Apagar y encender queda como respaldo.
- **Verificación.** En las cuatro pruebas de banco posteriores, todos los downlinks
  llegaron por RX1. En la verificación de la corrida VUELO, el gate rechazó la sesión
  mientras la sonda seguía en Clase C y la aceptó tras el re-join.

**Cómo evitarlo.** Si cambias de clase con el dispositivo ya unido, **cuenta con
rehacer el join**. Que la herramienta lo verifique, no la disciplina del operador. Ante
cualquier «la Clase C no funciona», mira primero la clase efectiva en el servidor, no la
radio.

---

## 7. El ping de latencia debe vivir dentro de la sesión, y la sesión debe morir sola

**Contexto.** Para medir la latencia de downlink se encolaba un ping (fPort 98, 1 byte
de secuencia) cada 60 s.

**Síntoma 1: el pinger mudo.** El pinger era un proceso aparte que detectaba la corrida
por el silencio de MQTT. **No envió ni un ping automático en toda la primera
campaña**: nunca llegó a desplegarse, y nadie lo notó hasta el análisis.

**Solución 1 (D-61).**

- **Una tarea ligada a la sesión.** El ping pasa a ser una tarea asíncrona del
  microservicio que solo existe mientras la sesión captura. Comparte la secuencia con
  el ping manual, para que el cruce por `(corrida, seq)` sea unívoco.
- **Cada envío se persiste** en una tabla `downlinks`, que da por fin el lado «enviado»
  del cruce de bajada.
- **Muere con la sesión** (fin, aborto, fin automático) y con el apagado del servicio.

**Síntoma 2: la sesión que no se cerró.** Una sesión VUELO de la radiosonda PiCARO
(T3/LoRa32), la 66, quedó abierta del **23-oct 08:23 al 2-nov 11:13**, es decir,
**10,12 días**. Recibió 17 uplinks, el último el 23-oct a las 08:28, y el ciclo encoló
**14 526 pings automáticos**, **14 521 de ellos después del último uplink**. En Clase A
sin uplinks no sale ninguno al aire, pero la cola del dispositivo y la tabla de envíos
se llenan de basura y contaminan cualquier estadística de bajada si no se excluyen.

**Causa.** El ping estaba ligado a la sesión, pero la sesión solo terminaba por acción
humana o al alcanzar el objetivo de uplinks. Sin la sonda, ninguna de las dos ocurre.
La decisión de diseño D-53 («no cerrar por inferencia») es correcta para la sesión,
pero no para el ciclo de ping.

**Solución propuesta (pendiente).** Que el ciclo de ping **se detenga solo tras N
minutos sin uplinks** y deje la sesión abierta con un aviso. Así se cumple D-53 (no
destruir datos por inferencia) y se corta el tráfico inútil.

**Cómo evitarlo.**

- **Todo proceso periódico necesita una señal de vida del otro extremo**, además del
  estado administrativo.
- **Excluye estas sesiones del análisis de bajada y documéntalo.** En este reporte, la
  66 está fuera de [`downlinks.csv`](../datos/downlinks.csv) y de [`latencias.csv`](../datos/latencias.csv), pero sus uplinks sí están en
  [`telemetria.csv`](../datos/telemetria.csv).

---

## 8. RadioLib: una JoinAccept ajena envenena el nodo (MIC inválido)

**Contexto.** En el cerro, tras medir la Clase A, se pidió un re-join para pasar a Clase
C.

**Síntoma.** El servidor aceptó los joins, pero la sonda no recibió ninguna JoinAccept.
Desde entonces **todos** sus JoinRequest llegaban con **MIC inválido** (25 en la
captura). Las dos sesiones de Clase C del cerro (42 y 43) se quedaron con 0 uplinks, y
la latencia en Clase C quedó sin medir en toda la campaña.

**Causa (confirmada en el código).** En RadioLib 7.7.1, `processJoinAccept()` fija la
revisión (`rev`) con el bit OptNeg de **cualquier** JoinAccept que oiga, **antes** de
verificar el MIC, y no lo deshace si la verificación falla. Una JoinAccept de otra red
deja `rev = 1` la mitad de las veces. Desde ese momento el nodo firma sus JoinRequest
con `nwkKey`, que en LoRaWAN 1.0.x vale ceros. `clearSession()` no restaura `rev`.
Desde un cerro, o desde un globo, la sonda oye muchas más redes ajenas que en el
laboratorio.

**Solución (A-11).**

- **Reconstruir el nodo.** Tras **cualquier** join fallido, y en cada re-join, se
  destruye el `LoRaWANNode` y se crea uno limpio, restaurando **solo los nonces**, para
  que el DevNonce siga creciendo.
- **Sin parchear la librería.** RadioLib no se toca: el gestor de componentes la
  regenera o rechaza el parche por el hash.
- **Por qué no basta `rev = 0`.** Escribirlo a mano no arregla `joinNonce` ni `devAddr`,
  que la misma trama deja envenenados.
- **Verificación en banco.** Con una bandera de prueba que fuerza `rev = 1`, el servidor
  registró `Invalid MIC`, el mismo síntoma del cerro, y el intento siguiente unió. El
  disparador real, una JoinAccept ajena, no se puede provocar sin un segundo servidor
  de red.

**Cómo evitarlo.** Si un nodo RadioLib con las claves bien puestas empieza a dar
`Invalid MIC` en el join, sospecha de esto antes que de las claves. Prueba siempre en
banco el **camino de recuperación** de un join fallido, no solo el join bueno. Y deja
para el final del día, o para un banco, los cambios de clase que exijan re-join en un
sitio remoto.

---

## 9. Fresnel y perfil SRTM antes de subir al cerro

**Contexto.** El escenario CERRO16 era un enlace con línea de vista de **15,27 km**
(haversine) entre el gateway del laboratorio y la cima de un cerro al OSO.

**El presupuesto de enlace no es el límite.** Con espacio libre, a 915 MHz y 15,27 km,
la FSPL es de 115,3 dB y el margen teórico en SF10, de ~44 dB. Lo que decide si el
enlace existe es la **geometría**: el despeje de la primera zona de Fresnel.

**Método (A-03).**

- **Perfil del terreno.** SRTM 30 m, 90 puntos cada ~172 m, interpolados linealmente
  entre gateway y cerro.
- **Fresnel.** r₁ = √(λ·d₁·d₂/d).
- **Abombamiento terrestre.** d₁·d₂ / (2·k·R), con k = 4/3.
- **Criterio.** Despejar el 60 % de r₁ más el abombamiento.

| Punto | Margen sobre el techo admisible |
|---|---|
| Primer kilómetro (entorno urbano junto al gateway) | **+23 m**, el más ajustado |
| Punto medio (r₁ = 35 m) | +188 m |
| Extremos (antena del gateway y sonda en la cima) | r₁ = 0: el margen es la altura de cada antena sobre el SRTM. La antena del gateway está ~15 m sobre el suelo, y la sonda, 6,5 m sobre el SRTM con su altitud GPS |

La línea de vista usa una sola altitud de la sonda: la mediana de su GPS en la cima más
1,5 m (2274 + 1,5 m). El perfil fino no se publica; [`perfil_cerro.csv`](../datos/perfil_cerro.csv) lo da agregado
por kilómetro.

**Dos trampas evitadas.**

- **Altitud del gateway (A-05).** La curva de nivel daba **86 m más** que la medida en
  sitio y el SRTM. Con ese error, toda la tabla de techo admisible se desplaza: no se
  puede cerrar Fresnel sin cerrar antes la altitud real de la antena (aquí, ~15 m sobre
  el suelo).
- **Una sola altitud para la sonda.** En la cima el SRTM da 2269 m y la mediana del GPS
  de la sonda, 2274 m. Una primera versión del perfil tomaba para la sonda una altitud
  unos 20 m menor que la del GPS y la dejaba «bajo tierra» en el extremo. Usa la
  altitud medida de la sonda más su altura sobre el suelo, y no compares el margen en
  los extremos, donde r₁ = 0 y una diferencia de unos metros entre SRTM y GPS está
  dentro del error de ambos.

**El presupuesto teórico fue ~25 dB optimista (A-09).**

- **Pronóstico.** Se había previsto extrapolando con n = 2 desde el mejor punto de banco
  con vista despejada.
- **Medido en el cerro.** RSSI medio de **−110,6 dBm** (pronóstico −108,7), frente a
  −85,8 dBm del presupuesto en espacio libre.
- **Margen real.** SNR en el p5 de −2,25 dB: **+12,8 dB** sobre el límite de SF10
  (−15 dB).
- **PDR.** 92,0 % por `fCnt`, contra un criterio del 50 %.

**Las medidas de banco engañan a corta distancia.** Cuatro puntos a 0,1-0,3 km del
gateway diferían hasta ~30 dB en RSSI, pero dieron todos un PDR de 96,7-100 %. Era
*shadowing* urbano del punto de medida, no un sector ciego del gateway.

**Cómo evitarlo.**

- **Perfil SRTM antes de salir.** Se hace desde el escritorio en minutos.
- **Altitud de la antena medida, no de curva de nivel.**
- **Pronostica el alcance desde medidas reales con vista despejada**, no desde el
  presupuesto en espacio libre.
- **No juzgues un gateway por un punto de banco.** Cambia de punto antes de concluir.

---

## 10. Lecciones cortas

- **Las pérdidas pueden venir de un solo canal (A-12).** En el cerro, la frecuencia de
  905,3 MHz recibió 17 uplinks frente a 35-38 en cada uno de los otros siete canales
  ([`telemetria.csv`](../datos/telemetria.csv), sesión 41). La bitácora lo atribuye a un interferente transitorio.
  RadioLib recorre los 8 canales sin repetir, así que el canal de cada pérdida se puede
  deducir del `fCnt`. Repartir los paquetes de una lectura en el tiempo (lección 3)
  limita el daño.
- **ChirpStack entrega los números del codec como *double*.** Una ráfaga `0` llega como
  `0.0`. Un microservicio que comparaba enteros descartó todas las ráfagas en banco.
  Acepta los *float* con valor entero.
- **El instante del `txack` depende del gateway.** En este reporte, el `txack` llegó
  ~5,1-5,3 s después del uplink con Basics Station (laboratorio) y con el Kerlink, que
  lo emiten al transmitir, y ~0,6 s después con el SenseCAP por UDP, que lo emite al
  aceptarlo (mediana de `dt_uplink_txack_s` en [`latencias.csv`](../datos/latencias.csv)). Para comparar
  latencias entre gateways se usó `uplink + retardo RX1 − encolado`, uniforme para
  todos.
- **Pings con periodo múltiplo del uplink.** En la corrida VUELO (uplink cada 20 s, ping
  cada 60 s), la latencia mediana fue de ~6 s en las sesiones 62 y 63 (n = 34), casi
  igual al retardo RX1. *(Inferencia:* el ping quedó en fase con los uplinks y casi
  siempre se encolaba justo antes de uno.) Si quieres medir la distribución real, rompe
  la fase con un periodo que no sea múltiplo o con un jitter aleatorio. Cuando se
  pierden uplinks, como en la sesión 64 (PDR por `fCnt` del 47,3 %), la mediana sube a
  **46 s** y el máximo a 227 s (n = 37).
- **Un gateway «en línea» puede estar sordo (A-13).** Uno de los gateways del campus
  enviaba estadísticas cada 30 s y recibía 0 paquetes al día. Vigila los paquetes
  recibidos por gateway, no solo su latido.
- **Abrir el puerto serie de un ESP32 lo reinicia** (DTR/RTS). Una sonda en plena
  corrida no se conecta al PC «solo para mirar».

---

## 11. Fuentes de las cifras

| Cifra | Fuente |
|---|---|
| PDR por `fCnt` frente a microSD (sesiones 20, 23 y 25) | [`sesiones.csv`](../datos/sesiones.csv) (`pdr_fcnt`) y [`pdr.csv`](../datos/pdr.csv) (`pdr`, `enviados_aire`, `tx_fallidos`) |
| PDR de banco 96,7-100 % e IC95 | [`pdr.csv`](../datos/pdr.csv) |
| Tiempo en el aire de 11 B y 12 B en SF10 | Cálculo con la fórmula de Semtech (13 B de cabecera LoRaWAN, CR 4/5) |
| Latencia de 9,6 s en el cerro, ~6 s en la T3 y 46 s en la sesión 64 | [`latencias.csv`](../datos/latencias.csv) (`lat_tx_estimada_s`, por sesión) |
| `txack` de ~0,6 s frente a ~5 s | [`latencias.csv`](../datos/latencias.csv) (`dt_uplink_txack_s`, por `gw_tx`) |
| Sesión 66: 10,12 días y 14 526 / 14 521 pings | [`incidentes.csv`](../datos/incidentes.csv) |
| Sesiones 42 y 43 con 0 uplinks | [`sesiones.csv`](../datos/sesiones.csv) |
| Cerro: PDR del 92,0 %, RSSI de −110,6 dBm y SNR p5 de −2,25 dB | [`sesiones.csv`](../datos/sesiones.csv), [`telemetria.csv`](../datos/telemetria.csv) (sesión 41) |
| Uplinks por canal en el cerro | [`telemetria.csv`](../datos/telemetria.csv) (`freq_mhz`, sesión 41) |
| Márgenes de Fresnel | [`perfil_cerro.csv`](../datos/perfil_cerro.csv) |
| 0/764 downlinks en Clase A, RTT de ~180 ms, 25 JoinRequest con MIC inválido, altitud del gateway, −85,8 / −108,7 dBm | Bitácora del proyecto (sin CSV público) |
