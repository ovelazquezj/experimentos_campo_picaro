# Guía de laboratorio — Pruebas de terreno de la radiosonda PICARO

> **Documento interno.** Contiene los datos reales del servidor. No se publica en el
> repositorio `radiosonda_PIcaro` ni en la wiki.

> **En una frase:** medir hasta dónde llega la radiosonda y cuánto cuesta escuchar
> siempre, con datos suficientes para defender las conclusiones después.

Esta guía cubre el **método**: qué medimos, cómo lo medimos y cómo sabemos que la
medida vale. El montaje del firmware está en `firmware/README.md`; el protocolo
formal, en [`EXPERIMENTO.md`](EXPERIMENTO.md).

> **Para operar la sonda en terreno, el documento es
> [`MANUAL-DE-CAMPO.md`](MANUAL-DE-CAMPO.md).** Es autosuficiente y es el que se
> lleva al cerro: gestos del botón, pantallas y qué hacer ante cada síntoma. Esta
> guía explica *por qué* el procedimiento es como es; el manual explica *cómo* se
> ejecuta. Si alguna vez se contradicen, manda el manual: describe el firmware que
> está flasheado.

---

## 1. Qué vamos a averiguar

Tres preguntas, en lenguaje llano:

**¿Hasta dónde llega?** Queremos saber qué porcentaje de los paquetes que envía la
sonda llegan realmente al servidor, y cómo se degrada eso con la distancia y con los
obstáculos. En terreno urbano desde un vehículo, desde una terraza con línea de vista
a 2,74 km, y desde un cerro a **16,35 km**.

**¿Cuánto cuesta escuchar siempre?** En clase A la radio duerme casi todo el tiempo;
en clase C el receptor no se apaga nunca. La clase C permite que un comando de corte
llegue al instante, pero se paga en batería. Queremos el número, no la intuición.

**¿Cuánto tarda en llegar una orden?** Si mandamos el comando de corte, ¿cuántos
segundos pasan hasta que la sonda lo ejecuta? En clase A hay que esperar al siguiente
uplink; en clase C debería ser casi inmediato.

Hay una cuarta pregunta, silenciosa pero importante: **¿es fiable nuestro método?**
La clase A o C no debería cambiar el alcance —la subida es idéntica en ambas—, así
que si el PDR sale distinto entre clases en el mismo escenario, el problema está en
cómo medimos, no en la radio. Esa comparación es nuestro control de calidad.

---

## 2. Fundamento

### Spreading Factor y alcance

El *spreading factor* (SF) es cuánto se "estira" cada bit en el aire. A mayor SF, cada
símbolo dura más, el receptor puede extraerlo de más ruido, y el alcance crece. El
precio es tiempo: un paquete a SF10 tarda unas seis veces más que a SF7.

| SF | Data Rate (US915) | Airtime con 11 B | Airtime real en la corrida | Sensibilidad relativa |
|---|---|---|---|---|
| SF7 | DR3 | ~62 ms | ~72 ms (14 B) | referencia |
| SF9 | DR1 | ~185 ms | ~226 ms (14 B) | ~+6 dB |
| SF10 | DR0 | ~371 ms | ~371 ms (11 B) | ~+9 dB |

La columna del medio compara los SF con la misma carga; la de la derecha es lo que
realmente se transmite en cada escenario, que lleva 3 bytes más de batería cuando el
data rate lo permite.

Esos +9 dB de SF10 sobre SF7 son margen frente a obstrucción y desvanecimiento.

> **Matiz importante, y algo contraintuitivo.** Al calcular el presupuesto de enlace
> real de nuestro trayecto al cerro salen **43,6 dB de margen en SF10** — y **36,6 dB
> en SF7**. Con línea de vista limpia, ese enlace de 16 km funcionaría *incluso en
> SF7*. Lo que ponemos a prueba en el escenario del cerro no es la sensibilidad del
> SF, sino **si el terreno deja pasar la señal**. Elegimos SF10 por margen, no por
> necesidad de alcance.

### Por qué SF10 y no SF12

En US915 **los canales de subida solo admiten DR0–DR3**, es decir SF10, SF9, SF8 y
SF7. SF11 y SF12 no existen para uplink en esta banda: son exclusivos de bajada
(DR8–DR13, en los canales de 500 kHz). No es una limitación del hardware ni del
firmware, sino de los *Regional Parameters* de LoRaWAN para US915.

Consecuencia práctica: **SF10 es nuestro techo de alcance**, y por eso el escenario del
cerro va a DR0.

### Por qué el payload cabe en 11 bytes y no en 19

US915 impone un límite de *dwell time* de 400 ms por transmisión. A SF10, 11 bytes de
aplicación más la cabecera LoRaWAN ya ocupan ~371 ms: estamos al borde. Por eso la
especificación fija el máximo de aplicación en **11 bytes para DR0**.

En DR1 (SF9) el límite sube a 53 bytes y en DR3 (SF7) a 242. De ahí que el payload de
la sonda sea de longitud variable: 11 bytes siempre, y 3 bytes extra de batería cuando
el data rate lo permite.

| DR | SF | Máx. aplicación | Payload que enviamos |
|---|---|---|---|
| DR0 | SF10 | 11 B | 11 B (sin batería) |
| DR1 | SF9 | 53 B | 14 B (con batería) |
| DR3 | SF7 | 242 B | 14 B (con batería) |

### Clase A y clase C

En **clase A** el dispositivo transmite y luego abre dos ventanas cortas de recepción
(RX1 y RX2). Fuera de esas ventanas la radio está apagada. Es el modo de mínimo
consumo, y el precio es que **un downlink tiene que esperar al siguiente uplink**.

En **clase C** el receptor queda encendido de forma continua salvo mientras transmite.
Un downlink puede entregarse en cualquier momento. El precio es el consumo: el
receptor del SX1262 tira del orden de miliamperios de forma permanente, frente a
microamperios en reposo.

Ojo con una consecuencia que sorprende: **la clase C no acelera los uplinks**. Después
de cada transmisión sigue habiendo que atender RX1, así que el ciclo mínimo entre
uplinks es el mismo en ambas clases:

```
ciclo mínimo ≈ airtime + RX1Delay + 1 s (RX2) + margen
```

Con `RX1Delay = 5 s` —el valor de nuestro servidor, que **no se toca**— el ciclo mínimo
ronda los **6,5 s**. De ahí salen los intervalos de 7 y 8 s de las corridas: menos no
cabe.

Y no es algo que se arregle en el firmware. Si le pides 3 s, el stack lo retrasa
igualmente y el intervalo real deja de coincidir con el declarado — lo que estropearía
el cálculo del ciclo de trabajo sin que nada avise. Más vale ir despacio y saberlo.

### PDR — Packet Delivery Ratio

Es la métrica principal de cobertura:

```
PDR = paquetes recibidos por el servidor / paquetes enviados por la sonda
```

El detalle que lo hace no trivial: **el servidor solo ve lo que llegó**. Si un paquete
se pierde, para el servidor sencillamente no existe, y no puede distinguir "no se
envió" de "se envió y se perdió". Por eso la sonda lleva su propio registro en microSD
con todo lo que transmite. El PDR sale de cruzar ambos registros por `fCnt`.

Sin el registro del dispositivo, no hay PDR: solo hay un recuento de paquetes
recibidos, que no dice nada por sí solo.

### Presupuesto de enlace y zona de Fresnel

El *presupuesto de enlace* es la contabilidad de decibelios entre lo que sale del
transmisor y lo que necesita el receptor. Ganancia de antenas y sensibilidad suman;
distancia y obstáculos restan. Subir de SF7 a SF10 aporta unos +9 dB de margen.

La **zona de Fresnel** es el volumen elipsoidal alrededor de la línea recta entre
antenas que debe estar despejado para que valga la aproximación de espacio libre. No
basta con "verse": si el terreno o un edificio invaden esa zona, hay pérdidas aunque
haya línea de vista óptica.

En nuestro trayecto al cerro (16,35 km, 915 MHz) el radio de la primera zona de
Fresnel en el punto medio es de **36,6 m**, y hay que dejar libre el 60 %, es decir
**22 m**. Sumando el abombamiento terrestre, sale una regla concreta: **a 8,2 km del
gateway el terreno debe quedar por debajo de 2183 m**.

Ojo con un malentendido frecuente: esos 36,6 m son un **radio perpendicular a la línea
entre antenas**, no una altura de antena. Y el cono se estrecha hacia los extremos: a
500 m del gateway el despeje necesario es de solo 7,6 m.

| km desde el gateway | Terreno máximo admisible |
|---|---|
| 0,5 | 2019 m |
| 1 | 2027 m |
| 2 | 2046 m |
| 4 | 2088 m |
| 6 | 2132 m |
| **8,2** *(punto medio)* | **2183 m** |
| 10 | 2226 m |
| 12 | 2276 m |
| 14 | 2329 m |

**Verifica esta tabla antes de subir al cerro.** En Google Earth, traza el perfil de
elevación entre `21.92, -102.27` (gateway) y
`21.8741637679742, -102.42482836119612` (cerro) y compáralo con la columna de la
derecha. Diez minutos de escritorio pueden ahorrarte un viaje inútil.

En la práctica: cuenta más subir el gateway o despejar el trayecto que cambiar de SF.

---

## 3. Antes de salir a campo

Marca todo esto **antes** de subirte al coche. Volver por un cable cuesta media
jornada.

### Material

- [ ] Sonda T-Beam Supreme con **antena conectada** (nunca alimentar sin antena)
- [ ] Antena de 915 MHz de repuesto
- [ ] microSD insertada, formateada FAT32 y **vacía** (o con los datos anteriores ya
      descargados)
- [ ] Batería cargada al 100 % y **verificada con el mismo criterio en todas las
      corridas** (ver §5)
- [ ] Cable USB-C y powerbank para el portátil
- [ ] Portátil con el dashboard funcionando y el proyecto clonado
- [ ] **Móvil del asistente con `campo/hoja-de-campo.html` ya abierto** (funciona sin
      conexión, pero cópialo al teléfono **antes** de salir)
- [ ] Hoja de campo impresa como respaldo — un móvil se queda sin batería
- [ ] Cinta métrica o telémetro para medir altura de antena
- [ ] **Device profile correcto asignado** al device `0011223344550001`: el de Clase A
      o el de Clase C según la corrida (`servidor/perfil.py terreno-a` / `terreno-c`,
      o desde la consola). Se ajusta **antes** de cada corrida, no una vez al salir
- [ ] Portátil o móvil con acceso al servidor **también en campo**, porque el perfil
      hay que cambiarlo cada vez que se alterna de clase
- [ ] *(No aplica: no hay mecanismo de corte fisico. Ver la nota de seguridad)*

### Verificación previa (en el laboratorio, no en campo)

```bash
# desde pruebas_terreno/dashboard/
py -3 dashboard.py --mode mqtt
```

**Salida esperada** en la barra de estado:

```
MQTT OK · application/<APP_ID>/device/+/event/up
```

Comprueba también que el gateway está en línea:

```bash
ssh -i <ruta-a-tu-clave-ssh> root@lns.pi-caro.org
cd /opt/picaro-chirpstack && ./scripts/status.sh
```

**Salida esperada:** el SenseCap M2 con `lastSeenAt` de hace segundos y estado
`ONLINE`. Si aparece `NEVER_SEEN`, no salgas a campo: no hay nada que medir.

> 📶 **En la cima del Cerro del Muerto hay cobertura de datos**, así que puedes consultar
> el dashboard en vivo y abortar la corrida (pulsación larga) si algo va mal, en lugar
> de descubrirlo al bajar — y reanudarla allí mismo, que para eso el firmware numera
> los intentos. Aun así, **no dependas de ella**: puede fallar, y el procedimiento tiene que
> funcionar sin conexión. Todo lo que necesites verificar en remoto, verifícalo **antes
> de salir**. El OLED y el registro de la microSD deben bastar por sí solos.

> ℹ️ **No hay mecanismo de corte físico.** La T-Beam Supreme va en una placa
> soldada a la que no se añade hardware, así que **ningún actuador recibe el
> comando** y el firmware no conmuta ningún GPIO (`CORTE_HABILITAR_GPIO = 0`).
>
> Lo que se mide es la **latencia del comando de downlink**: el instante en que
> llega a la sonda, cruzado con el instante en que el servidor lo envió. El
> mecanismo de corte se conserva en el protocolo y en el firmware porque es el
> caso de uso que justifica la Clase C —una orden de liberación que llega tarde
> no sirve— y porque en el futuro podría montarse de verdad.
>
> ⚠️ Lo que sí sigue siendo crítico: **nunca alimentes la placa sin antena**, o
> el amplificador puede dañarse.

---

## 4. Montaje

### Compilar y flashear (una sola vez)

**Un único binario cubre las seis corridas.** No hay que recompilar entre ellas: eso
significa no subir al cerro con portátil ni toolchain, y garantiza además que el
firmware es idéntico en todas, lo que elimina una fuente de error.

```bash
# desde pruebas_terreno/firmware/
idf.py build
idf.py -p COM7 flash monitor
```

Ajusta el puerto (`COM7` en Windows, `/dev/ttyACM0` en Linux/WSL).

### Seleccionar la corrida con el botón

La sonda tiene un solo botón y cuatro estados. El bucle es siempre el mismo:

```
arranque → JOIN → MENÚ → CORRIDA → FIN → MENÚ → …
```

**Elegir no es arrancar**, y esa separación es el cambio de diseño más importante
del firmware. Antes bastaba cambiar de escenario para que la corrida empezara en el
acto: el principio de cada medida se llenaba de uplinks tomados mientras el operador
aún colocaba la antena, y no había forma de sincronizar el arranque con el momento
real de la prueba. Ahora navegar el menú **no transmite, no reconfigura la radio y
no toca los contadores**: solo mueve un cursor. Nada ocurre hasta que se confirma.

| Gesto | En el MENÚ | En CORRIDA | En FIN |
|---|---|---|---|
| **Corta** | siguiente opción | *ignorado* | *ignorado* |
| **Doble** | **confirma y ARRANCA** | *ignorado* | *ignorado* |
| **Larga** (≥ 2 s) | — | abortar → menú | → menú |

Una sola regla que recordar en campo: **larga = ir al menú, siempre**.

Que en corrida se ignoren la pulsación corta y la doble es deliberado: un roce del
botón dentro de la mochila no puede alterar una medida de 40 minutos. La única
entrada al menú es un gesto largo e inequívoco.

#### El menú

```
┌─────────────────────┐
│ELIGE CORRIDA        │
│                     │
│> CERRO16 Clase C    │  ←── PARPADEA
│SF10/DR0 fPort 16    │
│8.0s x 300 uplinks   │
│Perfil: terreno-c    │
│corto = cambiar      │
│doble = ARRANCAR     │
└─────────────────────┘
```

La línea que parpadea es la selección; el resto queda fijo para poder verificar sin
prisa qué se va a lanzar. Cada **pulsación corta** avanza a la siguiente de las seis
opciones, en ciclo:

```
URBANO Clase A  →  URBANO Clase C  →  TERRAZA Clase A
      ↑                                      ↓
CERRO16 Clase C  ←  CERRO16 Clase A  ←  TERRAZA Clase C
```

> **El menú responde con ~0,4 s de retardo.** No es un fallo ni hay nada que
> optimizar: para saber que una pulsación **no** es la primera de una doble hay que
> esperar a que venza la ventana de la doble pulsación. Es el precio de meter dos
> gestos en un solo botón. Pulsa y espera a ver el cambio; si insistes, saltas dos
> opciones.

La línea `Perfil: terreno-c` recuerda qué device profile debe estar puesto en
ChirpStack **antes** de arrancar. El firmware no puede cambiarlo ni comprobarlo: es
la única defensa contra el error de la clase C sin perfil de clase C (§5).

La **doble pulsación** confirma: la línea deja de parpadear, la selección se
persiste en NVS —así que **sobrevive al reinicio y a quedarse sin batería**—, los
contadores se ponen a cero, la radio se reconfigura con el DR y la clase del
escenario, y la corrida empieza de inmediato. Ese es el instante que se anota en la
hoja de campo.

#### Durante la corrida y al terminar

```
┌─────────────────────┐
│CERRO16 SF10/DR0 C   │  escenario · SF/DR · clase
│fPort 16   8.0s      │  etiqueta de corrida · intervalo
│TX OK                │  resultado del último envío
│TX 42/300 OK 41      │  intentos / objetivo · sin error
│GPS FIX s:9          │  fix y satélites
│Bat 87% 4012mV       │  carga restante y tensión
│DL ping #12 186s     │  último downlink y hace cuánto
│larga = abortar      │
└─────────────────────┘
```

Al alcanzar los 300 uplinks la pantalla se queda en **FINALIZADO** y la sonda
**deja de transmitir**:

```
┌─────────────────────┐
│CERRO16 SF10/DR0 C   │
│fPort 16   8.0s      │
│FINALIZADO           │  ←── ya no transmite
│TX 300/300 OK 297    │
│GPS FIX s:9          │
│Bat 84% 3908mV       │
│DL ping #30 42s      │
│larga = menu         │
└─────────────────────┘
```

No arranca la siguiente sola, y tampoco vuelve al menú por su cuenta: lo primero
mezclaría dos corridas en una, y lo segundo borraría el aviso de que ésta terminó
bien. Quien llegue a la sonda tiene que poder ver de un vistazo que acabó y que no
hay nada corriendo. Sigue escuchando downlinks, eso sí: un ping tardío de la corrida
recién cerrada sigue siendo una medida de latencia válida.

> **La pantalla permanece encendida.** No hay apagado automático: el firmware envía
> el único `0xAE` (*display off*) en la secuencia de inicialización del SH1106, antes
> de encenderla, y nunca más. Y ahora sería contraproducente: el menú se lee **porque
> parpadea** —una pantalla en negro no distingue "esperando a que elijas" de "placa
> colgada"— y la pantalla de `FINALIZADO` tiene que seguir siendo legible cuando
> alguien llegue a la sonda diez minutos después de que acabara.
>
> El coste en batería es real (una pantalla encendida son del orden de decenas de
> mA), pero **no invalida la comparación A contra C**: el OLED está encendido igual
> en las seis corridas, así que es un desplazamiento constante que afecta a los dos
> brazos por igual. Lo que medimos es la **diferencia** de pendiente entre clases, y
> una carga idéntica en ambas se cancela en esa resta. Lo que sí queda inflado es el
> consumo **absoluto**: no extrapoles de aquí la autonomía de un despliegue real, que
> no llevaría pantalla.

### Comprobar el join

**El join ocurre antes del menú, no después de elegir.** Es deliberado: puede tardar
y reintentar, así que conviene que pase mientras se monta el equipo. Cuando el
operador confirma la corrida, el primer uplink sale en el acto, y no tras una espera
de duración imprevisible que se comería el principio de la medida.

Mientras busca red, el OLED muestra el número de intento:

```
┌─────────────────────┐
│CERRO16 SF10/DR0 C   │   ← la última corrida usada, aún sin confirmar
│fPort 16   8.0s      │
│JOIN #1...           │   ← número de intento
│TX 0/300 OK 0        │
│                     │   ← GPS y batería aún vacíos
│                     │
│DL --                │
│                     │
└─────────────────────┘
```

Las dos primeras líneas son la selección **guardada**, todavía sin confirmar: no
significan que esa corrida esté en marcha. `JOIN #n` sube cada 15 s mientras no haya
red; una pantalla en negro sí sería señal de placa muerta, ésta no.

**Salida esperada** en el monitor serie:

```
I (2345) picaro: JOIN intento #1 ...
I (8901) LORAWAN: JOIN OK  devAddr=01a2b3c4  rx1Delay=5s
W (9100) picaro: === MENU: corto = cambiar · doble = ARRANCAR ===
W (31200) picaro: === ARRANCA 20260814-CERRO16-C ===
I (31201) picaro:   DR0/SF10 · 8.0 s · 300 uplinks · fPort 16 · Clase C
I (31202) picaro:   el device profile del servidor debe ser: terreno-c
I (31500) picaro: ---- 20260814-CERRO16-C  TX 1/300 ----
I (31501) picaro:   payload 11B fPort 16 DR0/SF10 airtime ~371 ms | HEX 0ac1f2...
```

Fíjate en que el `run_id` no existe hasta que se confirma: se compone en ese momento
con la fecha UTC del GPS y el escenario elegido, y solo entonces se abre el fichero
de la microSD.

Tres cosas que deben cuadrar antes de moverte:

1. `escenario` y `clase` del log de `ARRANCA` son los que elegiste en el menú, y su
   `fPort` es el de la matriz de §5
2. `rx1Delay=5s` — es el valor del servidor y **no se cambia**. Si aparece otro, la
   sesión guardada en NVS es vieja: fuerza un join nuevo
3. `JOIN OK` — sin join no hay corrida. Si `JOIN #n` pasa de 10, no hay gateway al
   alcance o el servidor no responde: no arranques

Y en el dashboard debe aparecer el uplink con el `fPort` correcto según la matriz.

> Si el GNSS marca `fix=NO`, espera. En arranque en frío el L76K tarda entre 30 s y
> varios minutos, y necesita cielo despejado. **No confirmes la corrida sin fix**: sin
> posición no hay distancia, y sin distancia los datos de cobertura no sirven. Aquí se
> nota la ventaja de separar elegir de arrancar: puedes quedarte en el menú el tiempo
> que haga falta esperando al fix sin haber gastado ni un uplink.

---

## 5. Las 6 corridas

| # | Escenario | DR/SF | Payload | Intervalo | Duración | Clase | fPort |
|---|---|---|---|---|---|---|---|
| 1A | URBANO — vehículo 30–40 km/h | DR1 / SF9 | 14 B | 8 s | 40 min | A | 11 |
| 1C | URBANO — vehículo 30–40 km/h | DR1 / SF9 | 14 B | 8 s | 40 min | C | 12 |
| 2A | TERRAZA — piso 5, LoS, 2,74 km | DR3 / SF7 | 14 B | 8 s | 40 min | A | 13 |
| 2C | TERRAZA — piso 5, LoS, 2,74 km | DR3 / SF7 | 14 B | 8 s | 40 min | C | 14 |
| 3A | CERRO16 — LoS 16,35 km | DR0 / SF10 | 11 B | 8 s | 40 min | A | 15 |
| 3C | CERRO16 — LoS 16,35 km | DR0 / SF10 | 11 B | 8 s | 40 min | C | 16 |

Las duraciones no se programan: son **consecuencia** de que cada corrida termina al
llegar a **300 uplinks**. El OLED lleva la cuenta.

Y los intervalos tampoco se eligen: salen del `rx1_delay = 5 s` del servidor (§2). Con
600 uplinks a 7–8 s la campaña serían 7 horas de campo, así que se fijaron 300.

### Reglas que hacen válida la comparación

**Alterna A y C el mismo día y en el mismo sitio.** Si haces todas las corridas de
clase A el martes y las de clase C el jueves, no podrás distinguir el efecto de la
clase del efecto del clima, la hora o el tráfico. El orden recomendado por escenario
es: A, C, y si hay tiempo A otra vez, para detectar deriva.

**Misma carga inicial de batería en A y en C.** La comparación de autonomía no vale si
una corrida empieza al 100 % y otra al 70 %. Además, con la batería baja el PMU reduce
la potencia de transmisión, y eso contaminaría también las medidas de cobertura.

**Todas las corridas duran 300 uplinks, no un tiempo fijo.** Es deliberado: con 35
minutos fijos, los escenarios darían 300, 300 y 262 uplinks, y el del cerro no sería
comparable con los otros por tener distinta precisión estadística. Fijando el número de
paquetes, las seis corridas pesan lo mismo en el análisis. Además el firmware cuenta
paquetes, no minutos.

**Si una corrida se corta antes de los 300**, márcala como parcial y repítela. Los
datos parciales se conservan, pero solo las completas entran en el análisis principal.

Abortar (pulsación larga) es una operación normal y limpia, no un accidente. Lo ya
registrado no se pierde ni se mezcla con el nuevo intento: si reanudas el **mismo
escenario y clase el mismo día**, el firmware detecta el fichero anterior en la
microSD y añade al `run_id` un número de intento.

```
20260814-CERRO16-C.csv      primer intento (abortado a los 20 uplinks)
20260814-CERRO16-C-2.csv    segundo intento (el bueno)
```

Los scripts de análisis tratan los intentos como **corridas distintas**: aparecen
todos en `resumen.csv`, pero para la comparación A contra C y para las figuras se usa
el más completo, y avisan por pantalla de cuáles quedaron fuera. Fundir un intento de
20 uplinks con uno de 300 mezclaría condiciones que no son comparables — y si
abortaste, fue por algo. Anota en la hoja de campo **por qué**: un intento corto sin
explicación es un agujero en el análisis.

### Procedimiento de cada corrida

El orden importa. Los dos primeros pasos no son intercambiables con el resto.

1. **Ajusta el device profile en el servidor**, antes de tocar la sonda:
   `python perfil.py terreno-a` o `terreno-c` según la clase que vayas a medir
2. **Enciende la sonda** y espera a `JOIN OK` — puede tardar y reintenta solo
3. Espera también a `GPS FIX` mientras sigues en el menú: aún no has gastado nada
4. **Elige la corrida en el menú** con pulsaciones cortas. Antes de confirmar,
   verifica las tres cosas de la pantalla: escenario y clase, `fPort` según la matriz
   de arriba, y que la línea `Perfil:` coincide con lo que dejaste puesto en el paso 1
5. **Arranca con doble pulsación**, y anota en la hoja de campo la hora UTC de inicio,
   la corrida y la carga de batería. Ese es el instante de referencia de toda la medida
6. Confirma en el dashboard que llegan uplinks con el `fPort` correcto — **salvo en el
   cerro, donde puede no haber cobertura: allí el OLED es la única verificación**
7. **Durante la corrida**, dispara al menos **30 pings de latencia** (§ siguiente),
   espaciados y en momentos aleatorios
8. Anota los eventos relevantes conforme ocurren (§6)
9. Deja correr hasta que el OLED marque `FINALIZADO` y `TX 300/300`. Anota hora UTC de
   fin y carga final de batería
10. Para la siguiente corrida: **pulsación larga** para volver al menú, y **repite
    desde el paso 1**, incluido el device profile si cambias de clase
11. Al acabar la jornada, apaga, extrae la microSD y copia los CSV — también los de
    los intentos abortados

> **Por qué el device profile va primero y no se puede dejar para después.** Es el
> único error de esta campaña que produce datos con aspecto perfectamente normal: los
> uplinks salen, el PDR sale bien, el `fPort` dice «Clase C»… y los pings de latencia
> se comportan como Clase A porque el servidor nunca encoló el downlink inmediato. La
> conclusión que sale de ahí es exactamente la contraria a la correcta. No hay ningún
> mensaje de error, y por eso el menú te lo recuerda en pantalla: esa línea `Perfil:`
> no es informativa, es una lista de tareas.

### Medir la latencia de downlink

Hay dos comandos de bajada, deliberadamente separados:

| fPort | Payload | Efecto |
|---|---|---|
| **98** | cualquiera | **Ping de latencia**: enciende el LED y registra la marca de tiempo UTC. Inocuo |
| **99** | `0xA5` | **Corte real**: activa el GPIO de liberación. Cualquier otro byte se ignora y se registra |

Están separados por una razón práctica y una de seguridad. La práctica: para tener una
distribución de latencias necesitas decenas de medidas, y no puedes cortar la sonda
treinta veces. La de seguridad: un comando que libera algo físicamente no puede
dispararse con "un byte cualquiera" — de ahí el valor mágico `0xA5` en un puerto
propio.

Para lanzar un ping desde el portátil:

```bash
# desde pruebas_terreno/
mosquitto_pub -h mqtt.pi-caro.org -p 8883 --capath /etc/ssl/certs \
  -u picaro -P "$MQTT_PASSWORD" \
  -t "application/<APP_ID>/device/0011223344550001/command/down" \
  -m '{"devEui":"0011223344550001","confirmed":false,"fPort":98,"data":"AQ=="}'
```

**Salida esperada** en el monitor serie de la sonda:

```
I (123456) DOWNLINK: fport=98 len=1 utc=2026-07-19T18:42:07Z  -> PING (LED)
```

Anota en la hoja de campo la hora UTC en que lanzaste cada ping. El firmware registra
la hora de recepción; la diferencia es la latencia.

> En clase A espera latencias del orden de medio intervalo de uplink más `rx1_delay`,
> es decir unos 8–9 s. En clase C deberían caer a ~200 ms, dominadas por el viaje al
> servidor en la nube. Si en clase C ves latencias de segundos, lo más probable es que el device
> tenga asignado el **device profile de Clase A**: compruébalo con `python perfil.py`
> —sin argumentos dice cuál está activo— y corrígelo. La corrida hecha así **no mide
> la latencia de Clase C** y hay que repetirla entera; el PDR de esa corrida sí vale.

---

## 6. Registro en campo (a mano)

**Esta sección es la que decide si los datos servirán dentro de seis meses.**

El firmware registra lo que la sonda puede saber: posición, batería, SF, airtime. El
servidor registra RSSI, SNR y qué gateway oyó cada paquete. Pero hay cosas que **ningún
log captura** y sin las cuales los datos no se interpretan:

- Si el vehículo estaba parado o a 40 km/h cuando cayó el PDR
- Si había un edificio de por medio o la calle estaba despejada
- Si llovía
- A qué altura estaba la antena y en qué orientación
- Si alguien movió la sonda, la tapó con el cuerpo o la metió en el coche

Un hueco de dos minutos en los datos puede ser un túnel, un semáforo o un fallo del
firmware. Sin la nota manual, no hay forma de saberlo, y ese tramo se vuelve inútil.

### Cómo se registra

El **asistente** lleva el registro **desde el móvil**, con `campo/hoja-de-campo.html`.
Es una página autocontenida que funciona **sin conexión**, guarda en el almacenamiento
del navegador y exporta a CSV al volver. Aunque en el cerro sí hay cobertura, el
registro no debe depender de ella.

Cópiala al teléfono antes de salir y ábrela desde Archivos. La plantilla de papel de
abajo es el respaldo: úsala si el móvil falla o se queda sin batería.

### Plantilla de hoja de campo (respaldo en papel)

Imprime una por corrida.

```
╔══════════════════════════════════════════════════════════════════════╗
║ HOJA DE CAMPO — PRUEBAS DE TERRENO RADIOSONDA PICARO                 ║
╠══════════════════════════════════════════════════════════════════════╣
║ Corrida (1A/1C/2A/2C/3A/3C): ______   Fecha: ____________            ║
║ Operador: ______________________      run_id: _______________        ║
╠══════════════════════════════════════════════════════════════════════╣
║ INICIO                                FIN                            ║
║  Hora UTC:      __:__:__               Hora UTC:      __:__:__       ║
║  Batería (%):   ____                   Batería (%):   ____           ║
║  Batería (mV):  ____                   Batería (mV):  ____           ║
╠══════════════════════════════════════════════════════════════════════╣
║ EMPLAZAMIENTO                                                        ║
║  Punto de partida (lat, lon):    ______________________              ║
║  Altura antena sonda (m sobre suelo): ______                         ║
║  Orientación / polarización:     ______________________              ║
║  Distancia estimada al gateway:  ______ km                           ║
║  Línea de vista al gateway:  [ ] limpia  [ ] parcial  [ ] nula       ║
║  Obstáculos principales: _____________________________________       ║
╠══════════════════════════════════════════════════════════════════════╣
║ CONDICIONES                                                          ║
║  Meteorología:  [ ] despejado [ ] nublado [ ] lluvia [ ] niebla      ║
║  Temperatura aprox.: ____ °C     Viento: [ ] no [ ] sí               ║
║  Movimiento: [ ] estático  [ ] a pie  [ ] vehículo ____ km/h         ║
╠══════════════════════════════════════════════════════════════════════╣
║ PINGS DE LATENCIA (fPort 98)                                         ║
║  #  Hora UTC envío    Observación                                    ║
║  1  __:__:__          ______________________________                 ║
║  2  __:__:__          ______________________________                 ║
║  3  __:__:__          ______________________________                 ║
║  (continuar al dorso — mínimo 30 por corrida)                        ║
╠══════════════════════════════════════════════════════════════════════╣
║ BITÁCORA DE EVENTOS  (hora UTC + qué pasó)                           ║
║  __:__:__  ________________________________________________          ║
║  __:__:__  ________________________________________________          ║
║  __:__:__  ________________________________________________          ║
║  Ej.: "entramos en túnel", "paramos en semáforo", "empezó a llover", ║
║       "la sonda quedó a la sombra del edificio", "reinicié la placa" ║
╠══════════════════════════════════════════════════════════════════════╣
║ INCIDENCIAS / OBSERVACIONES                                          ║
║  ___________________________________________________________         ║
║  ___________________________________________________________         ║
╚══════════════════════════════════════════════════════════════════════╝
```

> Anota **conforme ocurre**, no al final. La memoria de "a qué hora entramos en el
> túnel" se degrada en minutos, y esa hora es justo la que necesitas para explicar el
> hueco en la gráfica.

---

## 7. Descarga y cruce de datos

Tres fuentes que hay que reunir después de cada jornada.

### a) Registro del dispositivo (microSD)

Es lo que la sonda **envió**. Copia el CSV a la carpeta de la corrida:

```bash
# desde pruebas_terreno/
mkdir -p analisis/datos/20260814-CERRO16-C
cp /d/20260814-CERRO16-C.csv analisis/datos/20260814-CERRO16-C/dispositivo.csv
```

Copia **todos** los ficheros, también los de intentos abortados (`…-C-2.csv`). Cada
intento es una carpeta propia, porque para el análisis son corridas distintas.

Columnas:

```
run_id,fcnt,utc,lat,lon,alt,sats,fix,temp_c,batt_mV,batt_mA,dr,sf,airtime_ms,tx_rc
```

### b) Registro del servidor (SQLite del dashboard)

Es lo que **llegó**, con `rssi`, `snr`, `gateway_id` y `fCnt`. Ya lo captura el
dashboard mientras corre; solo hay que copiar la base:

```bash
# desde pruebas_terreno/
cp dashboard/picaro_telemetry.db analisis/datos/20260814-CERRO16-C/servidor.db
```

> El dashboard tiene que estar **corriendo durante la corrida** para capturar. ChirpStack
> no guarda histórico de payloads: publica cada uplink por MQTT y se olvida. Si nadie
> escuchaba, esos datos no los recupera nadie.

### c) Hoja de campo

Transcribe la hoja de papel a `analisis/datos/<run_id>/campo.md`. Sin transcribir, en
seis meses es una foto ilegible en el móvil de alguien.

### Cruce

```bash
# desde pruebas_terreno/analisis/
py -3 cruzar.py --run 20260814-CERRO16-C
```

**Salida esperada:**

```
run_id      : 20260814-CERRO16-C
enviados    : 583   (registro del dispositivo)
recibidos   : 511   (registro del servidor)
PDR         : 87.6 %
huecos      : 12 tramos, mayor de 8 paquetes consecutivos
airtime tot : 216.3 s   (12.0 % del tiempo de corrida)
salida      : analisis/datos/20260814-CERRO16-C/cruzado.csv
```

La unión se hace por `fCnt`, que es el único identificador presente en ambos lados.
Cada fila del CSV cruzado lleva lo que se envió, si llegó, y con qué RSSI/SNR.

---

## 8. Análisis

```bash
# desde pruebas_terreno/analisis/
py -3 graficas.py --run 20260814-CERRO16-C
```

Cinco gráficas, y qué se lee en cada una:

### PDR frente a distancia

Puntos: distancia GPS al gateway (eje X) contra PDR en ventanas de 1 minuto (eje Y).

**Qué se lee:** el alcance útil. Busca el punto donde el PDR cae por debajo del 80 %:
ese es tu alcance práctico para ese SF. La caída no suele ser suave, sino un
acantilado — y su posición es el resultado principal del experimento.

### RSSI y SNR frente a distancia

**Qué se lee:** si la caída de PDR viene de falta de señal (RSSI bajando con la
distancia, lo esperable) o de interferencia (RSSI alto pero SNR malo). Son problemas
distintos con soluciones distintas: el primero se arregla con SF o antena, el segundo
no.

### Descarga de batería, A contra C

Tensión y corriente frente a tiempo, con las dos clases superpuestas.

**Qué se lee:** la pendiente de cada curva da el consumo medio. La diferencia entre
pendientes es **el coste real de la clase C**, y extrapolando sale la autonomía
estimada en horas para cada modo.

### Distribución de latencia de downlink

Histograma de latencias, separado por clase.

**Qué se lee:** en clase A, una distribución ancha centrada en torno a medio intervalo
de uplink. En clase C, una distribución estrecha en torno al RTT hacia el servidor en la nube
(~200 ms). El contraste entre ambos histogramas es el argumento visual más claro de
todo el experimento.

### Track GPS coloreado por RSSI

El recorrido sobre el mapa, con el color de cada punto según la señal recibida.

**Qué se lee:** dónde exactamente se pierde la cobertura. Aquí es donde la hoja de
campo se vuelve imprescindible: la gráfica te muestra un agujero, y la hoja te dice si
era un túnel o un edificio.

### Control de validez

Compara el PDR de las corridas A y C **del mismo escenario**. Deberían ser
estadísticamente indistinguibles. Si difieren de forma apreciable, no publiques
conclusiones sobre cobertura hasta entender por qué: lo más probable es que las
condiciones cambiaran entre corridas, no que la clase afecte al enlace de subida.

---

## 9. Preguntas de reflexión

No son retóricas: si no puedes responderlas, los datos no están entendidos.

1. **¿Por qué el PDR no debería cambiar entre clase A y clase C?** ¿Qué parte del
   protocolo es idéntica en ambas y cuál no?

2. **Si el PDR sí cambia entre A y C en el mismo escenario, ¿qué explicaciones son
   plausibles?** Ordénalas de más a menos probable. ¿Cuál descartarías primero y con
   qué dato?

3. **¿Por qué SF10 y no SF12, si SF12 llega más lejos?** ¿Es una limitación del
   hardware, del firmware o de otra cosa?

4. **¿Por qué el payload está limitado a 11 bytes en el escenario del cerro y no en
   los otros dos?** ¿Qué pasaría si intentáramos enviar 14 bytes a DR0?

5. **Las corridas van a 7–8 s y no a los 2,5–5 s del diseño original.** ¿De dónde sale
   ese límite? ¿Cambiaría algo si usáramos clase C? ¿Y si bajásemos `rx1_delay` en el
   servidor — por qué no es una opción?

6. **¿Por qué medimos la latencia con `fPort 98` en lugar de usar el comando de corte
   real?** Da una razón práctica y una de seguridad.

7. **Si duplicamos la altura de la antena del gateway, ¿esperarías más mejora que
   pasando de SF7 a SF10?** ¿De qué depende la respuesta?

8. **El registro del dispositivo dice 583 enviados y el del servidor 511 recibidos.
   ¿Podríamos haber calculado el PDR solo con los datos del servidor?** ¿Por qué?

9. **Durante una corrida móvil el PDR cae al 40 % durante tres minutos y luego se
   recupera.** ¿Qué fuentes de datos consultarías, y en qué orden, para explicarlo?

10. **La batería baja del 30 % a mitad de la corrida del cerro.** ¿Por qué eso puede
    contaminar las conclusiones sobre cobertura, y no solo las de autonomía?

11. **El firmware separa «elegir» de «arrancar»: navegar el menú no transmite nada.**
    ¿Qué error concreto en los datos evita esa separación? ¿Se podría haber arreglado
    descartando los primeros uplinks en el análisis en vez de tocar el firmware?

12. **Un escenario abortado y reanudado el mismo día genera dos ficheros, no uno.**
    ¿Por qué no se concatenan? Piensa qué le pasaría al PDR y a la curva de batería si
    se fundieran un intento de 20 uplinks y otro de 300.

---

## 10. Si algo falla

| Síntoma | Causa probable | Arreglo |
|---|---|---|
| No aparece `JOIN OK` | Fuera de cobertura, o DevEUI/AppKey mal en `credentials.json` | Verifica el alta en `https://lns.pi-caro.org`; acércate al gateway para el primer join. El firmware reintenta con backoff, así que una pérdida pasajera no arruina la corrida |
| `JOIN OK` pero `rx1Delay` distinto de 5 s | Sesión vieja guardada en NVS | Fuerza un join nuevo. **No toques el servidor**: los intervalos del experimento se derivan de su valor, no al revés |
| `PACKET_TOO_LONG` al transmitir | Payload de 14 B a DR0 (SF10), donde el máximo son 11 B | Es un fallo de firmware: a DR0 debe omitir los bytes de batería |
| `fix=NO` de forma persistente | Cielo obstruido, o arranque en frío del L76K | Espera hasta 5 min a cielo abierto. Sin fix, no inicies la corrida |
| El dashboard conecta pero no llega nada | El dashboard no estaba corriendo, o `app_id` erróneo | ChirpStack no guarda histórico: lo no capturado se perdió. Verifica `config.json` |
| Uplinks en el dashboard con `fPort` inesperado | Confirmaste en el menú una opción distinta de la que creías | Mira el OLED: la línea 1 y 2 dan escenario, clase y `fPort` activos. Pulsación larga para abortar, y vuelve a elegir. No hay que recompilar |
| La pantalla está en negro y parece que la sonda murió | **No hay apagado automático**: si está en negro, la placa se colgó | Apaga y enciende. Si se repite, anótalo y prueba con otra batería |
| El menú salta dos opciones de golpe | Pulsaste otra vez antes de que respondiera | Pulsa y **espera** a ver el cambio (~0,4 s de latencia inherente al gesto doble) |
| El contador no está a `0/300` al empezar | No has confirmado todavía: sigues viendo el estado anterior | Los contadores se ponen a cero **al confirmar** en el menú. Si tras la doble pulsación no marca `TX 0/300`, la corrida no arrancó |
| Pulsar durante la corrida no hace nada | Correcto: corta y doble se ignoran a propósito | Para volver al menú, **pulsación larga** (≥ 2 s). Se registra al cumplirse los 2 s, sin esperar a que sueltes |
| Dos ficheros del mismo escenario en la microSD | Hubo un intento abortado y se reanudó el mismo día | Es lo correcto (`…-C.csv` y `…-C-2.csv`). Consérvalos los dos; el análisis usa el más completo |
| Latencias de segundos en clase C | El device tiene asignado el device profile de **Clase A** | Cámbialo al perfil de Clase C en la consola y **rehaz el join** |
| El gateway aparece `NEVER_SEEN` | El M2 no está conectado al servidor | `./scripts/status.sh` en el servidor; revisa los certificados del gateway |
| PDR del 100 % en todas las corridas | Estás demasiado cerca del gateway | No hay experimento: aléjate hasta ver degradación |
| Huecos en el CSV del dispositivo | Reinicio de la placa, o microSD llena o mal insertada | Revisa el log serie a esa hora UTC; formatea la tarjeta antes de cada jornada |
| El CSV del dispositivo y la base del servidor no cruzan | `fCnt` reiniciado por un rejoin a mitad de corrida | Trata cada tramo entre joins como una corrida independiente |

---

> 📄 Documento interno del equipo PICARO. Ver también
> [`MANUAL-DE-CAMPO.md`](MANUAL-DE-CAMPO.md) (operación en terreno, el que se lleva
> al cerro), [`EXPERIMENTO.md`](EXPERIMENTO.md) (protocolo formal) y
> [`../BITACORA.md`](../BITACORA.md) (decisiones de diseño).
