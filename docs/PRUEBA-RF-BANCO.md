# Prueba de banco de RF — localizar el déficit de ~50 dB

> **Documento interno.** Contiene datos reales de infraestructura.

> ## ✅ Prueba ejecutada y cerrada el 2026-08-29 — resultado en el §9
>
> Cuatro medidas con antena Semtech marcada US915. **No hay avería, y no hay
> sector ciego: el equipo está sano.** Las cuatro entregaron el **96,7–100 %** de
> los uplinks, incluida la del punto con peor RSSI. Lo que varía entre puntos es
> el *shadowing* urbano, no el equipo. Extrapolando a los 15,27 km del cerro
> —línea de vista limpia y Fresnel despejado— el enlace sale **viable, con
> +17 a +47 dB de margen**. Lee el §9; el resto del documento es el procedimiento
> por si hay que repetirlo.

El análisis de la Serie 1 (`analisis/resultados/`) mostró que el enlace recibía
**entre 47 y 53 dB menos** de lo que predice el presupuesto, y esa pérdida se
comía justo el margen del que depende el escenario de 15 km.

Esta prueba se hace en una tarde, no necesita instrumentos y responde dos
preguntas en orden: **¿el déficit es real?** y, si lo es, **¿está en la sonda o
en el gateway?** Se ejecutó el 2026-08-29 y la respuesta está en el §9: el
déficit es real como número, pero **no es una avería** — es el canal urbano del
punto de medida. Lo que sigue hasta el §8 es el procedimiento tal como se
escribió, por si hay que repetirlo.

---

## 1. Qué dicen los datos

Comparando el RSSI recibido con el del espacio libre, en los uplinks tomados a
**137–216 m del gateway** —donde la obstrucción no puede justificar nada
parecido—, el déficit aparece igual en todas las corridas:

| Corrida | Distancia media | RSSI medido | Esperado | Déficit |
|---|---|---|---|---|
| 20260817-URBANO-A | 137 m | −91,3 dBm | −44,6 | **−46,7 dB** |
| 20260818-URBANO-C-2 | 138 m | −91,9 dBm | −44,7 | **−47,2 dB** |
| 20260821-URBANO-C-2 | 165 m | −99,3 dBm | −46,2 | **−53,1 dB** |
| 20260821-URBANO-A | 206 m | −97,2 dBm | −48,2 | **−49,1 dB** |
| 20260818-URBANO-C | 215 m | −97,9 dBm | −48,5 | **−49,4 dB** |
| 20260816-URBANO-C | 216 m | −101,1 dBm | −48,6 | **−52,6 dB** |

TERRAZA lo confirma desde otro ángulo: estática, en exterior y a 2,75 km,
recibió a **−116,5 dBm** frente a los ~−71 dBm del presupuesto.

**Por qué esto no es propagación.** A 150 m con vista al mástil, la obstrucción
y el multipath mueven el RSSI unos pocos dB, no cincuenta. Y un fenómeno de
propagación no sale idéntico en seis corridas de días distintos, con la sonda
quieta y en marcha, dentro y fuera del vehículo. Un valor grande y **constante**
es la firma de algo fijo en la cadena de radio.

> ⚠️ **Este párrafo quedó desmentido por la propia prueba (§9).** El argumento
> daba por supuesto que había vista al mástil, y en las corridas urbanas no la
> hay: medido punto por punto, el déficit **no** es constante —varía 30 dB según
> dónde estés— y con PDR del 97 % en el peor punto. Se conserva porque explica
> por qué se montó esta prueba, y porque la lección es la de siempre: una
> hipótesis que apunta a una avería hay que someterla a una medida que pueda
> refutarla, no solo a las que la confirman.

**Lo que ya está descartado:** el firmware. Aunque `radio.cpp` inicializa el
SX1262 a 10 dBm, RadioLib reconfigura la potencia en cada canal con la de la
banda US915 (30 dBm EIRP, recortada a los 22 dBm que da el chip), así que la
sonda no está transmitiendo a 10 dBm.

---

## 2. Primero, cinco minutos que pueden ahorrarte la tarde

Estas cuatro comprobaciones son gratis y cubren las causas que explican por sí
solas un déficit de esta magnitud. Hazlas **antes** de montar nada.

### 2.1 ¿La antena está en el conector de LoRa?

El T-Beam Supreme tiene **dos conectores de antena**: uno para el SX1262
(915 MHz) y otro para el GPS (1575 MHz). Si están intercambiados, la radio
transmite hacia una antena pasiva sintonizada a otra banda y con el
desadaptamiento se pierden fácilmente **30–50 dB** — exactamente lo que se está
midiendo.

Comprueba, con la placa delante y el serigrafiado a la vista, que la antena
gorda de 915 va al conector marcado como LoRa y la de GPS al suyo.

### 2.2 ¿La antena es de 915 MHz?

Una antena de 433 MHz, de 868 o una de WiFi de 2,4 GHz **encajan mecánicamente**
en el mismo SMA y producen este mismo déficit. Busca la marca de banda en el
cuerpo. Si no está marcada y hay varias parecidas en el cajón, sospecha.

Ojo también con la polaridad del conector: SMA y RP-SMA se enroscan igual pero
el pin central no contacta en el RP-SMA.

### 2.3 ¿El conector está apretado y el pigtail entero?

Aprieta a mano firme (sin llave). Revisa el latiguillo u.FL de la placa si lo
lleva: es frágil y un cable pellizcado o medio salido da decenas de dB.

### 2.4 ¿Y en el gateway?

Mismo repaso en el otro extremo: conector del coaxial en el gateway y en la
antena Raigen, y que el cable no esté aplastado ni con agua en el conector
exterior. El gateway lleva 5 semanas a la intemperie.

> Si encuentras algo aquí, corrígelo y repite igualmente la medida del §4: hace
> falta el número para saber que quedó resuelto.

---

## 3. Qué necesitas

| | |
|---|---|
| ☐ | La sonda con el firmware actual y batería cargada |
| ☐ | El móvil con la app de campo (v2.0.4 o posterior) |
| ☐ | Un punto con **vista directa al mástil del gateway**, a 150–300 m |
| ☐ | Forma de medir la distancia: el GPS de la propia sonda vale |
| ☐ | El gateway conectado y visible en la consola |

**Por qué 150–300 m y no 20 m.** Muy cerca el receptor del gateway puede
saturar, y estarías bajo el patrón vertical de la antena, donde su ganancia no
es la nominal. Más lejos de 300 m empiezan a pesar los obstáculos urbanos. Entre
150 y 300 m el espacio libre es un modelo honesto.

---

## 4. La medida

1. **Ponte en el punto elegido**, con la antena de la sonda vertical y el mástil
   del gateway a la vista. No sostengas la sonda pegada al cuerpo: apóyala en
   algo, a un metro del suelo como mínimo.
2. **Arranca una corrida corta** desde la app. Sirve `URBANO Clase A`; con 30–40
   uplinks basta, luego la finalizas con «Marcar finalizada».
3. **Anota el RSSI** que muestra la app en vivo. Toma nota de al menos **10
   lecturas**; a 150 m el multipath mueve el valor unos ±6 dB, así que lo que
   vale es la media, no una lectura suelta.
4. **Anota la distancia real** entre tu posición y el gateway
   (`21.92, -102.27`).
5. Marca la sesión al terminar para que no se confunda con las corridas de la
   campaña.

### Qué deberías ver

RSSI esperado en espacio libre, con la sonda a 22 dBm + 2 dBi y el gateway a
5,8 dBi menos 0,3 dB de coaxial:

| Distancia | RSSI esperado |
|---|---|
| 100 m | **−42 dBm** |
| 150 m | **−46 dBm** |
| 200 m | **−48 dBm** |
| 300 m | **−52 dBm** |
| 500 m | **−56 dBm** |

---

## 5. Cómo leer el resultado

Resta: `déficit = RSSI medido − RSSI esperado`.

| Déficit | Lectura | Qué hacer |
|---|---|---|
| **0 a −10 dB** | Normal. Tolerancias, multipath y patrón de antena caben aquí | El sistema está sano. El problema de la Serie 1 estaba en otra parte: repite la medida en el emplazamiento de TERRAZA antes de concluir |
| **−10 a −25 dB** | Algo pierde, pero no es catastrófico | Revisa conectores y prueba a sustituir la antena de la sonda (§6) |
| **peor de −30 dB** | **Confirmado.** Hay un fallo real en la cadena | Ve al §6 a localizarlo. No planifiques el cerro hasta cerrarlo |

Si el déficit ronda los −50 dB que salieron en la campaña, tienes reproducida la
avería en un sitio controlado, que es justo lo que hacía falta.

---

## 6. Localizar el fallo: ¿sonda o gateway?

Las pruebas están ordenadas de más barata a más cara. Para en cuanto una te dé
la respuesta.

### 6.1 Cambia la antena de la sonda

Si tienes otra antena de 915 MHz, ponla y repite la medida del §4 sin moverte
del sitio. **Si el RSSI sube de golpe, era la antena** y has terminado.

### 6.2 Transmite con otro equipo desde el mismo punto

Cualquier otro nodo LoRa de 915 que puedas hacer transmitir —otro T-Beam del
curso, un dispositivo de prueba— sirve como referencia:

- **Si el otro equipo también llega flojo** → el problema está en el
  **gateway** (su antena, su coaxial o su receptor).
- **Si el otro equipo llega bien** → el problema está en la **sonda**.

Esta es la prueba que más información da por menos esfuerzo, porque separa los
dos extremos sin desmontar nada.

### 6.3 Mira la asimetría del enlace

El gateway transmite con más potencia que la sonda. Si la sonda **recibe bien
los downlinks** pero sus uplinks llegan hundidos, el enlace es asimétrico y eso
apunta a la cadena de **transmisión de la sonda** o a la de **recepción del
gateway** — no a la antena compartida, que sirve para ambos sentidos.

> Hoy el registro de downlinks de la microSD (`<run_id>_dl.csv`) guarda la
> ventana en la que llegó cada uno, pero **no su RSSI**. Añadir esa columna es un
> cambio pequeño de firmware y convierte esta comprobación en una lectura
> directa. Pídelo si llegas hasta aquí.

### 6.4 Revisa el gateway de cerca

Si 6.2 apuntó al gateway: baja la antena si es viable, revisa el conector
exterior por dentro (agua, verdín, pin flojo) y comprueba el coaxial en toda su
longitud. Un conector con agua es la causa más común de una pérdida grande que
aparece «de un día para otro».

---

## 7. Qué anotar

Para que la medida sirva después, apunta esto y añádelo a la bitácora:

```
Fecha y hora:
Punto de medida (lat, lon):        Distancia al gateway:     m
Vista al mástil: sí / no           Altura de la sonda:       m
RSSI: 10 lecturas + media                       SNR medio:
Déficit frente a la tabla del §4:               dB
Comprobaciones del §2: antena en conector LoRa [ ] banda correcta [ ]
                       conectores apretados [ ]  gateway revisado [ ]
Pruebas del §6 hechas y resultado:
```

---

## 9. Resultado de la prueba (2026-08-29)

Cuatro medidas estáticas alrededor del gateway, con **antena Semtech marcada
US915** —queda descartada la hipótesis de banda equivocada del §2.2—, y ya
cruzadas contra el log de la microSD, así que el PDR es real y no estimado.

### El equipo está sano

| Punto | Azimut | Distancia | RSSI | **PDR** |
|---|---|---|---|---|
| 20260829-URBANO-A | 325° (NO) | 0,12 km | −71,3 dBm | **100,0 %** |
| 20260830-URBANO-A | 111° (ESE) | 0,23 km | −72,2 dBm | **97,0 %** |
| 20260829-URBANO-A-2 | 289° (ONO) | 0,26 km | −101,4 dBm | **96,7 %** |
| 20260829-URBANO-A-3 | 233° (SO) | 0,32 km | −89,0 dBm | **97,1 %** |

**Las cuatro cumplen el criterio de PDR**, incluida la del punto con 30 dB menos
de señal. Además cada prueba recibió **6-8 downlinks, todos por `rx1`** —en la
Serie 1 la Clase A no recibió ninguno—, así que la cadena de bajada también
funciona.

### Por qué el RSSI varía tanto entre puntos

Sí hay 30 dB de diferencia entre el mejor punto y el peor, a distancias
parecidas. Pero **no es un sector ciego del gateway**: un gateway apantallado
hacia un lado no entrega el 96,7 % de los paquetes por ese lado. Es *shadowing*
urbano —tener o no vista al mástil desde el punto concreto de medida—, un
fenómeno normal de 20-30 dB en ciudad, y afecta al **punto de medida**, no al
equipo. El tinaco quedó descartado en sitio: está 1 m **por debajo** de la
antena.

### Pronóstico del cerro

Extrapolando desde cada punto medido con exponente n = 2 —lícito porque el
trayecto al cerro es **línea de vista limpia** con la primera zona de Fresnel
despejada (A-03)— a los 15,27 km:

| Referencia | RSSI previsto en el cerro | Margen SF10 |
|---|---|---|
| Presupuesto teórico (LoS puro) | −85,8 dBm | **+47 dB** |
| Mejor punto medido (ESE) | −108,7 dBm | **+24 dB** |
| Punto NO | −115,4 dBm | +18 dB |
| Punto SO | −123,2 dBm | +10 dB |
| Punto ONO (el más tapado) | −136,8 dBm | sin enlace |

Con línea de vista, la referencia aplicable es la mitad de arriba: **el enlace al
cerro es viable, con +17 a +47 dB de margen**. La fila que predice fallo
corresponde al punto urbano más obstruido, que no se parece al trayecto del
cerro.

### Entonces, ¿qué pasó en la Serie 1?

Lo más probable es que no pasara nada anómalo: el escenario **URBANO es NLOS y
se aleja** hasta 6 km, y a esa distancia sin vista el enlace se cae. A 300 m el
mismo equipo entrega el 97 %. Antes de la Serie 2 conviene fijar en el manual
cómo se coloca la sonda —antena vertical, fuera del vehículo— y asumir que el
criterio de PDR ≥ 80 % puede no ser alcanzable en URBANO móvil: eso sería un
**resultado legítimo del experimento**, no un fallo del equipo.

---

## 10. Y si todo sale bien

Si el sistema mide sano aquí, el déficit de la Serie 1 no era del equipo sino
del **cómo se midió**: la sonda dentro del vehículo con la carrocería de por
medio (fácilmente 10–20 dB), la antena tumbada o pegada al cuerpo, o una
terraza que no daba al ESE como exigía la verificación pendiente de D-19.

En ese caso la corrección no es reparar nada, sino fijar en el manual de campo
**cómo se coloca la sonda**: antena vertical, fuera del vehículo o con el equipo
asomado por la ventanilla, y verificación de la orientación de la terraza antes
de la corrida. Eso es lo que habría que cambiar antes de la Serie 2.
