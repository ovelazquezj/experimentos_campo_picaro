# Diccionario de datos: pruebas de terreno

CSV anonimizados de las pruebas de terreno de la radiosonda PiCARO (julio a octubre
de 2026). Son la única entrada de los scripts públicos de `../scripts/`. Los generó un
extractor privado a partir de los datos crudos, que no se publican porque llevan
identificadores de red y coordenadas exactas:

- el respaldo de la base del microservicio de campo (2026-11-02): 52 sesiones, 3636
  uplinks, 15 195 pings y 178 posiciones del teléfono;
- los CSV de la microSD de la sonda y los que exportó la app de campo;
- los eventos de ChirpStack (txack) de la jornada del cerro y del grabador de octubre.

Codificación UTF-8, separador `,` y punto decimal (los CSV son para máquinas; el texto y
las figuras del reporte usan coma decimal). Una celda vacía significa "no disponible",
nunca cero.

## Convenciones

| Tema | Regla |
|---|---|
| Horas | `*_utc` en UTC (ISO-8601, sufijo `Z`). `*_local` en hora del centro de México, **UTC−6** fijo (sin horario de verano). |
| Sondas | `radiosonda PiCARO (T-Beam Supreme)`: GPS, BME280 y PMU reales. `radiosonda PiCARO (T3/LoRa32)`: **simula** GPS, BME280 y magnetómetro (D-65). Solo la batería y el uptime son reales. |
| Gateways | Por su nombre: `picaro-lab-ags-001` (laboratorio en Aguascalientes, a unos 25–30 km al sur del ITPA), `ITPA-IOT-GW00` (SenseCAP M2) e `ITPA-IOT-GW01-kibts` (Kerlink), los dos del campus del ITPA. En las columnas aparecen abreviados `lab`, `gw00` y `gw01`. |
| Posiciones | El laboratorio, la terraza y el punto NE son lugares privados y su posición **no se publica**. En `telemetria.csv` solo llevan posición los uplinks del cerro (sesión 41), un sitio público, a **3 decimales** (~110 m). En `sitios.csv` solo llevan centro, a **2 decimales**, el cerro y el campus del ITPA. |
| Distancias | Haversine calculado con las coordenadas exactas, con 0,1 km de resolución. Se publica la distancia de cada uplink a su mejor gateway, pero **no** distancias entre sitios ni rumbos: junto con posiciones conocidas permitirían situar el laboratorio por trilateración. |
| Inferencias | Las columnas o valores marcados *(inferido)* no son medidas directas. Se explica cada caso abajo. |

## sesiones.csv: una fila por sesión de captura (52)

| Columna | Descripción |
|---|---|
| `session_id` | Identificador de la sesión en el microservicio. Faltan los números 4-14, 49, 51 y 52: no están en el respaldo. Las 49, 51 y 52 fueron pruebas de banco que se borraron (D-65). |
| `run_label` | Etiqueta de la corrida, `AAAAMMDD-ESCENARIO-CLASE[-INTENTO]`, tal como la puso la app. **No siempre coincide con el `run_id` de la microSD**: el firmware y la app cuentan los intentos por separado (ver `corrida_sd`). |
| `escenario`, `clase`, `fport_esperado` | Escenario declarado (`URBANO`, `TERRAZA`, `CERRO16`, `VUELO`), clase LoRaWAN (A/C) y fPort de la corrida (11-17, D-12/D-64). |
| `sonda` | Alias de la sonda. |
| `estado` | `finished` (cerrada como terminada) o `aborted` (abortada). |
| `objetivo_uplinks` | Objetivo fijado de antemano: 300 (165 en VUELO). |
| `recibidos` | Uplinks que capturó el microservicio en la sesión. |
| `fcnt_min`, `fcnt_max` | Rango de fCnt recibido. |
| `pdr_fcnt` | `recibidos / (fcnt_max − fcnt_min + 1)`: PDR estimado por los huecos de fCnt, el mismo método de `cerro_20260927.py`. No ve las pérdidas anteriores al primer uplink ni las posteriores al último. Donde hay microSD manda `pdr.csv`. |
| `enviados_sd`, `corrida_sd` | Uplinks del log de la microSD y su `run_id`, si existe. Se emparejan por solape temporal y fPort. |
| `n_intentados` | Mejor estimación de los uplinks intentados: `max(recibidos, rango de fCnt, enviados_sd)`. Es la N del criterio de validez. |
| `inicio_local`, `fin_local`, `duracion_sesion_min` | Apertura y cierre de la sesión en la app. |
| `primer_uplink_local`, `ultimo_uplink_local`, `duracion_datos_min` | Ventana real de datos. Difiere de la anterior cuando la sesión quedó abierta (la 66). |
| `pings_encolados` | Pings de downlink (fPort 98) que encoló el microservicio durante la sesión. |
| `gateways` | `nombre:uplinks` de cada gateway que recibió algo. |
| `sitio` | Sitio de la sesión (ver `sitios.csv`). *(inferido)*: se asigna por la mediana de las posiciones y su dispersión, no por anotación de campo. |
| `sitio_metodo` | Origen de la posición: `gps_sonda`; `gps_microsd` (sin fix en el servidor, posición tomada del log de la tarjeta); `gps_telefono` (T3: GPS del teléfono que va junto a la sonda, descartando los fixes con precisión > 100 m); `inferido_rssi` (sin posición, y solo la recibió el gateway del laboratorio con RSSI medio > −85 dBm, así que se asume banco junto al laboratorio); `ninguno`. |
| `dist_gw_mediana_km`, `dist_gw_max_km` | Distancia al gateway que mejor recibió cada uplink, mediana y máxima. Solo cuentan los uplinks recibidos con posición. |
| `dispersion_pos_km` | Distancia máxima de una posición a la mediana: más de 1 km cuenta como corrida móvil. |
| `valida_para_analisis` | 1 si la sesión entra al análisis, 0 si no (ver criterio). |
| `motivo_exclusion` | Por qué vale 0. Se separan con ` \| ` si hay varios. |

### Criterio de `valida_para_analisis`

Vale 1 cuando se cumplen **las tres** condiciones:

1. **Estado y tamaño.** `estado = finished` con `n_intentados ≥ 1`, o bien
   `estado = aborted` con `n_intentados ≥ 30`. El 30 es el mínimo de pings por corrida
   del protocolo (EXPERIMENTO §5.2).
2. **No es banco documentado bajo otra etiqueta.** Se excluyen las sesiones 15, 16 y 27:
   eran pruebas de join en la ciudad etiquetadas `CERRO16` (bitácora, 2026-08-29 tarde).
   También la 44, que fue la verificación en banco de VUELO con 3 ráfagas (D-64).
3. **No está repetida.** Una sesión `aborted` se considera repetida si **después**, el
   mismo día, hay otra con el mismo escenario, clase, sonda y sitio que cumple 1 y 2.
   Es el caso del sufijo `-2`/`-3` de D-39. Una sesión `finished` nunca es repetida:
   dos corridas completas en el mismo sitio cuentan como réplicas. Como en `cruzar.py`,
   los intentos no se concatenan.

Además se excluye la sesión 66 por el incidente que se describe en `incidentes.csv`.
Una sesión válida puede tener un PDR bajo: la validez mide la calidad de la sesión, no
el resultado del enlace.

Para comparar escenarios conviene filtrar también por `sitio`. Varias sesiones con
etiqueta `URBANO` son en realidad mediciones estáticas junto a un gateway:
`LAB_BANCO`, o `ITPA` en el caso de la sesión 40.

## telemetria.csv: un uplink recibido por fila (3636)

| Columna | Descripción |
|---|---|
| `session_id` … `clase` | Sesión a la que pertenece el uplink. |
| `ts_utc`, `hora_local` | Hora del uplink según el evento de ChirpStack. |
| `f_cnt`, `f_port`, `dr`, `sf`, `freq_mhz` | Contador, puerto, data rate, spreading factor (de `txInfo`) y frecuencia del canal en MHz. |
| `gw_mejor`, `rssi_dbm`, `snr_db` | Gateway con mejor SNR y su RSSI/SNR. Es el criterio de `cerro_20260927.mejor_rx`: decide si el paquete llega. |
| `n_gateways`, `gateways` | Cuántos gateways y cuáles lo recibieron (`;`). |
| `rssi_lab`, `snr_lab`, `rssi_gw00`, `snr_gw00`, `rssi_gw01`, `snr_gw01` | RSSI (dBm) y SNR (dB) en cada gateway. Vacío si ese gateway no lo recibió. Algunos `rxInfo` vienen sin SNR. |
| `lat`, `lon`, `decimales_pos` | Posición redondeada. **Solo en la sesión 41 (cerro)**; vacía en el resto (ver Convenciones). |
| `alt_m` | Altitud del GPS de la sonda o del teléfono, en m s. n. m. |
| `fuente_pos` | `gps_sonda` (T-Beam con fix), `telefono` (T3: posición del teléfono a ≤ 300 s del uplink, con precisión ≤ 100 m) o vacío. **La posición que manda la T3 es simulada y no se publica.** |
| `precision_tel_m` | Radio de precisión del fix del teléfono. |
| `dist_gw_mejor_km`, `dist_lab_km` | Distancia al `gw_mejor` y al gateway del laboratorio. `dist_lab_km` solo se publica cuando el mejor gateway es el del laboratorio (entonces coincide con `dist_gw_mejor_km`). |
| `gps_fix`, `satelites` | Estado del GPS de la T-Beam. Vacío en la T3. |
| `bateria_v`, `bateria_pct` | Batería: PMU en la T-Beam; ADC en la T3, que no da porcentaje. En CERRO16 (DR0) el uplink no lleva batería (README de análisis); la de la microSD está en `pdr.csv`. |
| `temperatura_c`, `presion_hpa`, `humedad_pct` | BME280 de la T-Beam. La presión y la humedad solo vienen en el paquete P2 de VUELO. **Vacío en la T3**, porque ahí son simulados. |
| `sensores_simulados` | 1 para la T3. |
| `tipo_paquete`, `rafaga` | Solo en VUELO (fPort 17): `posicion`, `ambiente` o `navegacion`, y el número de ráfaga (D-64). |

## downlinks.csv: un ping encolado por fila (669)

`session_id`, `run_label`, `sonda`, `escenario`, `clase`; `seq` (byte de secuencia
1-255); `fport` (98 = ping de latencia, D-14); `ts_utc` y `hora_local` del
**encolado** en el microservicio; `origen` (`auto`: ciclo de 60 s ligado a la sesión,
D-61; `manual`: botón de la app).

**No incluye la sesión 66** (ver `incidentes.csv`). Que un ping esté aquí solo dice
que se encoló: si salió por el aire lo dice `latencias.csv`, y si la sonda lo recibió
solo consta en su microSD, que no se ha cruzado.

## latencias.csv: un ping emitido por gateway por fila (99)

Sale del evento `txack` de ChirpStack. Solo hay captura de esos eventos en la jornada
del cerro (sesión 41, desde las 08:17 locales) y en las corridas VUELO de la T3 del 18
y el 23 de octubre (sesiones 62-64). En el resto de sesiones no se grabaron, y de la
Clase C no hay ninguna medida en esta campaña: las sesiones 42 y 43 nunca volvieron a
unirse (A-11). La única medida de Clase C sobre esta red es la del evento SatLink 2026,
en su propio conjunto de datos.

| Columna | Descripción |
|---|---|
| `seq`, `fport`, `origen` | Ping emparejado. |
| `ts_encolado_utc`, `ts_txack_utc` | Encolado en el microservicio y llegada del txack. |
| `lat_encolado_txack_s` | `txack − encolado`. **Su sentido depende del gateway**: Basics Station (laboratorio) y el Kerlink confirman tras emitir (~5 s después del uplink), y el SenseCAP por UDP (GW00) confirma al aceptar la orden (~0,6 s). No sirve para comparar gateways. |
| `uplink_previo_utc`, `dt_uplink_txack_s` | Uplink de Clase A que abrió la ventana: el último anterior al txack, a menos de 30 s. |
| `ventana`, `retardo_ventana_s` | `RX1` si `timing.delay` = 5 s, `RX2` si es 6 s. |
| `lat_tx_estimada_s` | **Métrica recomendada.** `uplink_previo + retardo_ventana − encolado`: instante estimado de emisión por radio menos encolado. Es uniforme entre gateways. En Clase A incluye la espera hasta el siguiente uplink. *(inferido)* |
| `gw_tx`, `freq_tx_mhz`, `sf_tx`, `bw_tx_khz` | Gateway, frecuencia, SF y ancho de banda de la emisión (RX1 en US915: 500 kHz). |
| `fcnt_down`, `emparejamiento` | Contador de bajada y regla con que se emparejó el ping. *(inferido)*: cada sesión arranca con un join, así que `fCntDown` empieza en 0 y los pings son el único tráfico de bajada. Por eso `seq = fCntDown + k`, y se elige el `k` que empareja más txack con una latencia entre 0 y 600 s. Sale `k = 1`, salvo `k = 2` en la sesión 64. |
| `fuente` | Captura de la que sale el txack. |

## pdr.csv: corridas con log de microSD (13)

Sale de **`analisis/cruzar.py` sin modificar**: `cruzar_corrida()` y
`elegir_representativa()`, con una tolerancia de ventana de 120 s, la que trae por
defecto. El lado recibido son los CSV de la app. Como control se cruzó también contra
la base del microservicio y los recibidos coinciden en las 13 corridas
(`recibidos_campo_db`).

**Por qué `recibidos` no siempre coincide con el de `sesiones.csv`.** `sesiones.csv`
cuenta todo lo que capturó el servidor en la sesión; `pdr.csv` cuenta solo los paquetes
recibidos que emparejan con un envío al aire de la microSD. Difieren en dos corridas:

- **Sesión 25** (30 aquí, 29 en `sesiones.csv`): la microSD registra dos transmisiones
  con el mismo `fCnt` 0, separadas 8 s. El servidor lo recibió una vez, pero el cruce
  por `fCnt` lo cuenta para las dos. El valor real es 29 de 164.
- **Sesión 20** (199 aquí, 202 en `sesiones.csv`): un huérfano (`fCnt` 599, posterior al
  último registro de la microSD) y dos paquetes (`fCnt` 576 y 594) que la microSD marcó
  con `tx_rc ≠ 0` pero que llegaron al servidor. El cruce no los cuenta como enviados al
  aire.

| Columna | Descripción |
|---|---|
| `corrida_sd`, `session_id`, `run_label_app` | `run_id` de la microSD y sesión de la app con la que solapa en el tiempo. |
| `intento`, `fport`, `sitio` | Intento según el sufijo de la microSD, fPort y sitio de la sesión. |
| `enviados_total`, `tx_fallidos`, `enviados_aire` | Log de la sonda. `tx_rc ≠ 0` no salió por la antena. |
| `recibidos`, `huerfanos` | Cruce por fCnt dentro de la ventana temporal. Un huérfano es un paquete recibido que no consta en la microSD; suele ser el borde de la corrida contigua. |
| `pdr`, `pdr_bruto` | `recibidos / enviados_aire` y `recibidos / enviados_total`. |
| `pdr_ic95_inf`, `pdr_ic95_sup` | Intervalo de Wilson al 95 % (EXPERIMENTO §8.2). |
| `pdr_minimo`, `cumple_pdr`, `completa` | Criterio del escenario (0,80 / 0,50) y si se alcanzó el objetivo de uplinks. |
| `representativa_celda` | La que usa `cruzar.py` en cada escenario × clase: la de más enviados. |
| `rssi_*`, `snr_*` | Media, p10 y p90 de lo recibido. Si un fCnt llegó por varios gateways, cuenta el de mejor RSSI (criterio de `cruzar.py`). |
| `dist_gw_*`, `dist_recorrida_km` | Distancias al gateway del laboratorio (GPS de la microSD). |
| `airtime_total_s`, `duracion_min`, `ciclo_trabajo_pct` | Tiempo en el aire y ciclo de trabajo. |
| `batt_inicial_mv`, `batt_final_mv` | Batería al principio y al final según la microSD. |

La jornada del cerro (sesión 41) **no está aquí**: su microSD no se ha descargado. Su
PDR por fCnt (0,920) está en `sesiones.csv`.

## sitios.csv: lugares de prueba (8)

`sitio`; `descripcion`; `lat_2d`/`lon_2d` (centro redondeado a 2 decimales, solo en
los sitios públicos: cerro y campus del ITPA; vacío en los lugares privados, los sitios
móviles y los que no tienen posición); `alt_gps_mediana_m`; `gw_referencia`;
`dist_gw_min_km_medida`/`dist_gw_max_km_medida` (rango de distancias a
`gw_referencia` medido en `telemetria.csv`); `perfil` (geometría del trayecto según el
protocolo y la bitácora); `sesiones` y `sesiones_validas`. No lleva distancias entre
sitios ni rumbos (ver Convenciones).

*(inferido)* `ITPA-IOT-GW00` estuvo cerca de la sonda, y no en el ITPA, al menos el
2026-08-31: en la sesión 36, sin GPS, lo recibió con −22 dBm de media. Las distancias a
GW00 usan su posición actual, en el ITPA.

## perfil_cerro.csv: despeje de Fresnel gateway ↔ cerro, por kilómetro (16 filas)

Sale de un perfil SRTM de 30 m con 90 puntos cada ~172 m entre el gateway del
laboratorio y la cima. **Se publica agregado por kilómetro**, sin el perfil fino del
terreno ni coordenadas: casado contra el SRTM, el perfil fino permitiría situar el
laboratorio.

Cálculo: línea de vista recta entre la antena del gateway (~15 m sobre el suelo) y la
sonda en la cima, con una sola altitud de la sonda, la mediana de su GPS más 1,5 m
(2274 + 1,5 m, `sitios.csv`). Techo admisible = línea de vista − (0,6 · r₁ +
abombamiento terrestre, k = 4/3). Margen = techo admisible − terreno.

Columnas: `km_ini`, `km_fin` (tramo; el último acaba en la cima, a 15,3 km); `puntos`
(puntos del perfil en el tramo); `fresnel_r1_max_m` (radio máximo de la 1.ª zona de
Fresnel en el tramo, redondeado al metro); `margen_min_m` (margen mínimo del tramo,
truncado al metro).

**Los dos extremos del trayecto no entran**, porque ahí r₁ = 0 y el margen es solo la
altura de la antena sobre el terreno SRTM. En el gateway la antena está ~15 m sobre el
suelo. En la cima el SRTM da 2269 m, y la sonda, con su altitud GPS, queda 6,5 m por
encima. En un pico, una diferencia de unos metros entre el SRTM de 30 m y el GPS está
dentro del error de ambos.

## incidentes.csv: sesión 66

`20261023-VUELO-A-2` (T3). La sesión quedó abierta por error del 2026-10-23 08:23 al
2026-11-02 11:13 (hora local), unos 10 días. Recibió 17 uplinks, el último a las 08:28
del 23-oct. El ciclo de ping de 60 s (D-61) siguió encolando **14 526 pings
automáticos**, 14 521 de ellos después del último uplink. Por eso se excluye de
`downlinks.csv` y `latencias.csv`. Lección: el ciclo de ping debería cortarse solo
cuando pasa un tiempo sin uplinks.

## clase_efectiva.csv

Una fila por sesión con uplinks. Generado por un extractor privado a partir de la base del microservicio y de la microSD de la sonda.

| Columna | Unidad / valores | Origen |
|---|---|---|
| session_id, run_label, escenario, sonda, estado | — | sesión del microservicio |
| clase_sonda | A / C | clase con que operaba la sonda (la de la corrida) |
| clase_servidor | A / C | clase efectiva del servidor (`deviceClassEnabled` de los uplinks); ChirpStack la fija en el join |
| coincide | 1 / 0 | clase_sonda = clase_servidor |
| uplinks_lns | paquetes | uplinks recibidos por el servidor en la sesión |
| uplinks_sd | paquetes | filas del log de uplinks de la microSD (vacío si no se descargó) |
| dl_enviados_persistidos | pings | envíos guardados por el microservicio (solo existe desde el 29-ago-2026) |
| origen_envios | auto / manual | origen de esos envíos |
| dl_recibidos_sd | pings | downlinks registrados por la sonda en su microSD (vacío si no hay microSD) |
| seq_max_recibida | — | secuencia más alta recibida (cota inferior de los enviados cuando no hay registro de envíos) |

## downlinks_recibidos_sd.csv

Una fila por downlink que la sonda registró en su microSD.

| Columna | Unidad / valores | Origen |
|---|---|---|
| session_id, run_label | — | sesión |
| clase_sonda, clase_servidor | A / C | como en `clase_efectiva.csv` |
| t_utc | ISO 8601, reloj de la sonda | microSD. Ojo: el reloj de la sonda puede llevar minutos de desfase respecto al servidor |
| fport, seq | — | fPort 98 = ping; seq = secuencia de 1 byte |
| ventana | rx1 / rx2 / vacío | ventana en que se recibió (solo en el firmware a partir del 29-ago) |
