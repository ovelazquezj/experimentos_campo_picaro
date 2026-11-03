# Análisis de las pruebas de terreno

Convierte los datos crudos de las 6 corridas en las métricas del experimento.
El protocolo está en [`../docs/EXPERIMENTO.md`](../docs/EXPERIMENTO.md).

## Las 6 corridas

| Escenario | DR/SF | Intervalo | Uplinks | Duración | fPort A/C |
|---|---|---|---|---|---|
| `URBANO` | DR1 / SF9 | 8 s | 300 | ~40 min | 11 / 12 |
| `TERRAZA` | DR3 / SF7 | 8 s | 300 | ~40 min | 13 / 14 |
| `CERRO16` | DR0 / SF10 | 8 s | 300 | ~40 min | 15 / 16 |

Los intervalos **no son de elección libre**. El servidor tiene `rx1_delay = 5 s`
y no se toca: en clase A no se puede transmitir hasta cerrar RX1 (5 s) y RX2
(6 s), así que el ciclo mínimo real ronda los 6,5 s.

## Por qué hacen falta dos fuentes

El servidor **solo ve lo que le llegó**. No distingue *"no se envió"* de *"se
perdió en el aire"*. El PDR únicamente se puede calcular si el denominador sale
del log del propio dispositivo.

| Fuente | Qué contiene | De dónde sale |
|---|---|---|
| **(a)** CSV de la microSD | lo que se **envió** | la sonda, un fichero por corrida → `datos_sd/` |
| **(b)** CSV descargados de la app | lo que **llegó** | la app de campo (Sesiones → Descargar CSV) → `datos_app/` |

> El lado recibido es ahora el **CSV de la app** (la exportación del microservicio),
> no el SQLite del dashboard viejo. Si aún conservas aquella base, puedes cruzar
> contra ella con `--db`; es una alternativa, no el flujo por defecto.

Se cruzan por `fcnt` ↔ `f_cnt`, acotando además por la ventana temporal de cada
corrida. Filtrar solo por `f_port` no basta: si una corrida se repite, ambas
comparten `f_port`, y si el dispositivo rehace el join el `fCnt` vuelve a
empezar y puede colisionar.

## Instalación

```bash
# desde pruebas_terreno/analisis/
pip install -r requirements.txt
```

`cruzar.py` funciona sin instalar nada (solo biblioteca estándar). `matplotlib`
hace falta para las figuras; `scipy` es opcional.

### Posición del laboratorio y EUIs (fuera de git)

La posición exacta del gateway del laboratorio y los EUIs reales no se publican.
Los scripts los leen de `sitios_privados.json` (en `.gitignore`) a través de
`sitios.py`:

```bash
cp sitios_privados.example.json sitios_privados.json   # y pon los valores reales
```

Sin ese fichero se usa la plantilla (posición redondeada a 2 decimales y EUIs de
ejemplo) con un aviso: los scripts corren, pero las distancias no son exactas.

### Datos crudos (no se publican)

`datos_app/`, `datos_sd/`, `datos_lns/`, `../caja_negra/`, `perfil_elevacion.csv`
y las salidas con posiciones de `resultados/` se quedan en local: llevan trazas
GPS en torno al laboratorio. El dataset público, anonimizado, está en
`../reporte/datos/`. Cada carpeta conserva un `LEEME.md` que lo explica.

## Flujo completo

### 1. Recoger los datos

Copia los CSV de la microSD a `analisis/datos_sd/`. Un fichero por corrida, con
el nombre del `run_id`:

```
analisis/datos_sd/
├── 20260814-URBANO-A.csv
├── 20260814-URBANO-C.csv
├── 20260814-TERRAZA-A.csv
├── 20260814-TERRAZA-C.csv
├── 20260814-CERRO16-A.csv
├── 20260814-CERRO16-C.csv
├── 20260814-CERRO16-C-2.csv   (si esa corrida se abortó y se repitió)
└── downlinks.csv              (opcional, para la latencia)
```

**Cópialos todos, también los intentos abortados.** El sufijo `-2` lo pone el
propio firmware al detectar que ya existe un fichero de ese día y escenario; el
intento corto no es basura, sino la única prueba de qué se llegó a medir antes
de abortar.

Y descarga desde la **app de campo** el CSV de cada sesión (Sesiones → Descargar
CSV) a `analisis/datos_app/`, con el mismo nombre de corrida. Ese es el lado
**recibido**. El microservicio lo capturó **solo si estaba corriendo** durante la
prueba (lo está, desplegado en `campo.pi-caro.org`); lo que no capturó nadie no se
recupera, porque ChirpStack publica cada uplink por MQTT y se olvida.

### 2. Cruzar

```bash
python cruzar.py                 # usa ./datos_sd (enviado) y ./datos_app (recibido)
# equivale a: python cruzar.py --sd ./datos_sd --app ./datos_app
# alternativa contra el dashboard viejo: python cruzar.py --db ../dashboard/picaro_telemetry.db
```

Escribe en `./resultados/`:

| Fichero | Contenido |
|---|---|
| `<run_id>_cruzado.csv` | una fila por uplink **enviado**, con si llegó, su RSSI/SNR y la distancia al gateway |
| `resumen.csv` | una fila por corrida con todas las métricas |
| `resumen.txt` | lo mismo en texto, con el control de validez A vs C y, si los hay, el aviso de **intentos múltiples** |

Ambos CSV llevan una columna `intento` (1 si no hubo repetición). Sale del
`run_id`, no de un contador aparte.

### 3. Graficar

```bash
python graficas.py --resultados ./resultados
```

Escribe en `./resultados/figuras/`:

| Figura | Qué se lee en ella |
|---|---|
| `1_pdr.png` | PDR por escenario y clase, con los criterios de aceptación |
| `2_rssi_snr_dist.png` | degradación de RSSI y SNR con la distancia |
| `3_bateria.png` | descarga durante las corridas. **No** sirve para comparar autonomía A vs C (ver abajo) |
| `4_latencia.png` | latencia de downlink: donde la clase C debe ganar |
| `5_mapa.png` | cobertura geográfica, con los puntos perdidos marcados |

Las figuras que no tengan datos se omiten con un aviso, no fallan.

## Formatos esperados

### CSV del dispositivo

```
run_id,fcnt,utc,lat,lon,alt,sats,fix,temp_c,batt_mV,batt_mA,dr,sf,airtime_ms,tx_rc
```

`run_id` con formato `AAAAMMDD-ESCENARIO-CLASE[-INTENTO]`, p. ej.
`20260814-CERRO16-C` o `20260814-CERRO16-C-2`. Escenarios reconocidos:
`URBANO`, `TERRAZA`, `CERRO16` (también `CERRO`). `tx_rc` = 0 si el paquete salió
por la antena; distinto de 0 si falló la transmisión en el propio equipo.

El sufijo de intento aparece cuando una corrida se abortó con el botón y se
reanudó el mismo día sobre el mismo escenario y clase: el firmware sondea la
microSD y abre un fichero nuevo en vez de seguir escribiendo en el anterior. Sin
ese sufijo los dos intentos compartirían fichero y quedarían mezclados sin forma
de separarlos después. `parse_run_id()` lo devuelve como cuarto elemento; ojo al
tocarla, porque el número hay que recortarlo **antes** de leer la clase o
`...-C-2` daría clase `2`.

Dos columnas con matices que conviene conocer:

- **`batt_mV` está siempre**, en las seis corridas. No así en el uplink: el
  payload es de longitud variable y en `CERRO16` (DR0/SF10) solo caben 11 bytes
  por el *dwell time* de 400 ms, así que ahí va **sin** la extensión de batería.
  Cualquier análisis de batería tiene que salir de este CSV, no del servidor.
- **`batt_mA` va vacía siempre.** El AXP2101 del T-Beam Supreme no mide
  corriente de batería, solo tensión y porcentaje. La columna se conserva por
  formato. La autonomía se mide **en banco**, no en campo: en 35 minutos la
  diferencia de consumo entre clase A y C queda por debajo del ruido.

### downlinks.csv (opcional)

```
run_id,seq,utc_enviado,utc_recibido
```

La latencia es `utc_recibido − utc_enviado`. `utc_enviado` lo anota quien lanza
el ping desde el `mosquitto_pub`; `utc_recibido` lo registra la sonda.

## Cómo se calculan las métricas

**PDR = recibidos / enviados_al_aire.** El denominador excluye los uplinks que
fallaron en el propio equipo (`tx_rc ≠ 0`): esos nunca salieron por la antena y
mezclarlos confundiría un fallo del dispositivo con pérdida por propagación. El
resumen incluye también `pdr_bruto` con todos los intentos, y la diferencia
entre `env` y `aire` mide la fiabilidad del equipo.

**Criterios de aceptación**, fijados **antes** de tomar datos:

| Escenario | PDR mínimo |
|---|---|
| URBANO | ≥ 80 % |
| TERRAZA | ≥ 80 % |
| CERRO16 | ≥ 50 % |

**Control de validez A vs C.** La clase describe el receptor: no puede afectar
al enlace de subida. Si el PDR difiere entre A y C en el **mismo** escenario, el
problema está en el método, no en el hallazgo.

Se exigen **las dos condiciones** para dar la alarma:

```
p < 0,05  (chi-cuadrado)   Y   |Δ| > 5 puntos porcentuales
```

Con estos tamaños de muestra el chi-cuadrado marca como significativas
diferencias de pocos puntos sin ninguna relevancia práctica. Pedir ambas evita
descartar corridas buenas por significancia estadística vacía.

**Intentos múltiples.** Los intentos de una misma combinación escenario × clase
se tratan como **corridas distintas**, nunca se concatenan. Todos aparecen en
`resumen.csv` y todos tienen su `_cruzado.csv`, pero el control de validez A vs C
y las figuras usan el **más completo** de cada celda —el de más uplinks
enviados— y avisan por pantalla de cuáles quedaron fuera.

El porqué: si se abortó, fue por algo. Fundir un intento de 20 uplinks con uno de
300 promediaría condiciones que no son comparables, y además:

- comparar A contra C usando un intento abortado daría una diferencia que es del
  **método**, no del enlace: justo lo que el control de validez busca detectar
- la pendiente de batería se mide sobre el tiempo transcurrido **dentro** de una
  corrida; pegar dos intentos la falsea
- el mapa dibujaría un salto ficticio al volver del final de un intento al
  principio del siguiente

Sumar después dos corridas separadas es trivial; separar dos corridas ya
fundidas, no. Por eso el descarte se avisa y nunca es silencioso: un descarte
callado se leería como «solo hubo una corrida», que es exactamente el error que
el sufijo de intento vino a evitar.

**Tamaño de muestra.** 300 uplinks por corrida, fijado antes de tomar datos. Con
*p* = 0,8 el error estándar del PDR es √(0,8·0,2/300) ≈ **2,3 %**: suficiente
para comparar escenarios sin alargar las corridas de campo más de la cuenta.

## Avisos que conviene mirar

| Mensaje | Qué significa |
|---|---|
| `PARCIAL` en el resumen | la corrida no llegó a 300 uplinks. Se conserva, pero solo entran las completas en el análisis principal |
| `paquetes en el servidor sin correspondencia` | llegaron uplinks que no constan en el log del dispositivo. Suele ser ventana temporal mal acotada o dos corridas mezcladas. Prueba a subir `--tolerancia-s` |
| `REVISAR` en el control de validez | diferencia A/C significativa **y** relevante: revisa qué cambió entre esas dos corridas antes de interpretar nada |

## Por qué la batería no mide autonomía aquí

`3_bateria.png` documenta que la batería aguantó la corrida, y nada más.

En ~35 minutos el consumo extra de la clase C (~6 mA continuos por tener el
receptor siempre abierto) supone unos 3,5 mAh sobre una celda de ~3000 mAh:
alrededor de **1,4 mV** de caída adicional, frente a **5–20 mV** de ruido en la
lectura del PMU bajo los pulsos de transmisión. La señal buscada es un orden de
magnitud menor que el ruido.

Por eso la hipótesis de autonomía sale de la campaña de campo y se mide en banco
con un medidor de corriente en línea. Está documentado en la Adenda 1 de
[`../docs/EXPERIMENTO.md`](../docs/EXPERIMENTO.md).

## Verificación

Ambos scripts se probaron con datos sintéticos de las 6 corridas: el cruce, el
cálculo de PDR, la distancia por haversine (16,36 km al cerro, coincidente con
la geometría real), el control de validez y las cinco figuras.

## Corridas VUELO (D-64)

La corrida VUELO (fPort 17, solo Clase A) manda tres paquetes de 11 bytes por minuto
durante 55 minutos, desde un punto fijo. `cruzar.py` la reconoce (`AAAAMMDD-VUELO-A`),
cruza paquete a paquete y la deja fuera del control A vs C. Los CSV de la microSD
llevan dos columnas nuevas al final, `tipo` (1–3) y `rafaga`, y hay un segundo fichero,
`<run_id>_lecturas.csv`, con la lectura completa de cada minuto.

```bash
python vuelo.py      # resultados/vuelo/{resumen.txt, puntos.csv, figuras/margen_vs_distancia.png}
```

Cada corrida es **un punto** en la gráfica distancia → margen de SNR, que se compara con
la curva del cerro del 2026-09-27: `margen = 12,8 − 20·log10(d / 15,27 km)`. El PDR sale
de la microSD si está en `datos_sd/`; si no, de los huecos de fCnt. Los datos de banco
van en `datos_app/banco/`, que `vuelo.py` no lee.

