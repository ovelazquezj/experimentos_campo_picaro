# Manual de campo — Radiosonda PICARO

Cómo se opera la sonda en terreno y qué debe verse en la pantalla en cada momento.

Este manual es **autosuficiente**: no hace falta consultar el protocolo ni el código
para ejecutar una corrida. Si algo no coincide con lo que describe aquí, para y
averigua por qué antes de tomar datos — una corrida mal arrancada no se nota hasta el
análisis, y para entonces ya bajaste del cerro.

Cubre **los dos caminos**: operar desde la app por Bluetooth (lo normal desde la v2) y
operar con el botón de la sonda (el respaldo, que sigue siendo completo). El detalle de
las pantallas de la app está en [`APP-CAMPO.md`](APP-CAMPO.md); aquí está lo que hay
que hacer, en orden, con la sonda delante.

> **La regla de oro:** el device profile del servidor se ajusta **antes** de arrancar
> la corrida. La sonda no puede cambiarlo, ni avisar de que está mal. Es el único
> error de esta campaña que produce datos con aspecto perfectamente normal.
>
> *Desde la v2 la app lo pone sola al arrancar, y desde el 2026-08-29 el servidor
> además lo verifica y rechaza la sesión si no cuadra (D-60). La regla se mantiene
> porque con el botón sigue siendo tuya.*

> ### 📍 Subida al cerro del 2026-08-30 → ve al **§14**
>
> Lleva la secuencia de las cuatro corridas, qué esperar en la cima, los dos
> cambios de clase, cómo colocar la sonda (cambió tras la Serie 1) y la lista de
> antes de salir. Lee el §14 **antes** de subir; el resto del manual es la
> referencia completa.

---

## 1. Dos formas de operar la sonda, y cuál usar

Desde la **v2** hay dos caminos, y los dos hacen exactamente lo mismo en la sonda.

**Camino normal — desde la app, por Bluetooth.** Eliges la corrida **una sola vez, en
la app**, y esa única acción fija **las dos mitades del sistema**: la app pone el
device profile del servidor y abre la sesión de captura, y acto seguido ordena a la
sonda por Bluetooth que arranque ese mismo escenario y esa misma clase. Es el camino
que hay que usar, porque **elimina por construcción** el error de elegir una cosa en la
app y otra en la sonda — el error que produce datos con aspecto normal y que sólo se
descubre al analizar.

**Camino de respaldo — con el botón de la sonda.** El botón **sigue haciendo
absolutamente todo lo que hacía en la v1**: navegar el menú, arrancar, abortar y volver
al menú, sin depender de la app, del teléfono ni de la cobertura. No es un modo
degradado ni una reliquia: es el que se usa si el móvil se queda sin batería, si se
cae, o si simplemente prefieres no sacarlo. Con este camino **el device profile hay que
ponerlo tú** (§4), porque la sonda no puede tocarlo.

> **La regla:** si usas la app, elige **sólo** en la app. Si usas el botón, elige
> **sólo** en la sonda y acuérdate del perfil. Lo que no se hace nunca es elegir en los
> dos sitios y confiar en que coincidan — eso es exactamente lo que la v2 vino a
> eliminar.

---

## 2. La secuencia completa

```
   1. Encender la sonda                            → operable en segundos; busca enlace por detrás
   2. (opcional) esperar a "Enlace: OK"            → o arranca ya: esperará el enlace sola
   3. Emparejar la sonda con el móvil              → SOLO la primera vez
   4. Elegir la corrida y ARRANCAR, en la app      → una sola acción
   5. Ejecutar hasta FINALIZADO                    → 300 uplinks, ~40 min
```

Con el botón, como respaldo, los pasos 3 y 4 se sustituyen por:

```
   3'. Ajustar el device profile en el servidor    ← desde el móvil o el portátil
   4'. Elegir la corrida en el menú                → pulsaciones cortas
   5'. Arrancar                                    → doble pulsación
```

Elegir **no** es arrancar. Se puede navegar el menú entero sin transmitir nada: la
radio no se reconfigura y los contadores no se mueven hasta que confirmas. Eso es
deliberado — antes bastaba cambiar de escenario para que empezara a transmitir en el
acto, y el principio de cada corrida se llenaba de uplinks tomados mientras aún
estabas colocando la antena.

Por Bluetooth ocurre lo mismo en un solo mensaje: la app no manda «mueve el cursor»,
manda «arranca **esta**». Seleccionar por BLE **es** arrancar, igual que la doble
pulsación.

---

## 3. Antes de salir

| | Comprobación |
|---|---|
| ☐ | Batería por encima del 80 % (una corrida son ~40 min) |
| ☐ | microSD insertada — **sin ella la corrida no es analizable** |
| ☐ | Antena atornillada. Transmitir sin antena daña el SX1262 |
| ☐ | El gateway aparece conectado en la consola del servidor |
| ☐ | Sabes qué corrida vas a hacer y con qué clase |
| ☐ | Portátil o móvil con acceso al servidor, para el perfil (§4) |
| ☐ | **El móvil ya está emparejado con la sonda** — compruébalo en casa, no en el cerro (§6) |
| ☐ | **Bluetooth encendido** en el móvil, y batería del móvil suficiente |

Las dos últimas son nuevas de la v2 y merecen un aviso: **emparejar exige tener la
sonda delante y pulsarle el botón** (§6). Descubrir en la cima que el móvil no está
emparejado significa emparejarlo allí, con la sonda ya montada y con sol en la
pantalla. Se comprueba antes de salir, encendiendo la sonda y viendo que el indicador
de Bluetooth de la app se pone en verde.

La microSD no es opcional ni un respaldo. Es el **denominador del PDR**: el servidor
solo ve lo que llegó, y sin el registro de lo que se envió no hay forma de distinguir
«no se transmitió» de «se perdió en el aire». Una corrida sin microSD hay que
repetirla entera.

---

## 4. El device profile

> **Si operas desde la app, esta sección es informativa: el perfil lo pone ella.** Al
> pulsar **Arrancar**, la app conmuta el device profile a `terreno-a` o `terreno-c`
> según la clase que elegiste, **antes** de ordenar a la sonda que transmita. Ése es
> justamente el orden correcto y por eso se hace así: si el Bluetooth fallara, quedaría
> una sesión vacía —visible al instante y reversible—, y no una sonda transmitiendo
> contra un perfil equivocado, que es el fallo invisible que contamina el dato.
>
> **Si operas con el botón, esto es lo primero de todo y sigue siendo obligatorio.**

**Siempre primero, antes de tocar la sonda.**

```bash
# desde pruebas_terreno/servidor/
python perfil.py terreno-a     # para una corrida en Clase A
python perfil.py terreno-c     # para una corrida en Clase C
python perfil.py               # sin argumentos: dice cuál está activo
```

### Por qué esto importa tanto

El firmware decide si **él** se comporta como Clase A o C, pero el que decide si el
servidor **encola un downlink inmediato** es el device profile de ChirpStack. Si eliges
Clase C en el menú y el servidor sigue en el perfil de Clase A, ocurre esto:

- los uplinks salen y llegan con normalidad
- el PDR sale bien
- el fPort dice `16`, o sea «CERRO16 Clase C»
- pero los pings de latencia esperan a la ventana RX del siguiente uplink

…y el resultado se lee como **«la Clase C no aporta nada»**, que es justo la conclusión
opuesta a la que el experimento debería alcanzar. No hay ningún mensaje de error. La
única defensa es verificarlo antes.

Por eso el menú muestra en pantalla el perfil que hace falta:

```
Perfil: terreno-c
```

Esa línea no es informativa: es una **lista de tareas**. Si dice `terreno-c` y no
ejecutaste `perfil.py terreno-c`, la corrida no sirve.

---

## 5. Encender: la sonda queda operable de inmediato

Enciende la sonda. Verás un instante:

```
┌─────────────────────┐
│PICARO TERRENO       │
│Arrancando...        │
└─────────────────────┘
```

y **en segundos** cae en el menú, **operable desde ya**. No se queda colgada buscando
red: el enlace LoRa se adquiere **por detrás** mientras tú navegas, emparejas o eliges
la corrida.

```
┌─────────────────────┐
│ELIGE CORRIDA        │
│Enlace: uniendo...   │  ←── el enlace se adquiere solo, por detrás
│> CERRO16 Clase C    │  ←── PARPADEA (ya puedes navegar)
│SF10/DR0 fPort 16    │
│8.0s x 300 uplinks   │
│Perfil: terreno-c    │
│corto = cambiar      │
│doble = ARRANCAR     │
└─────────────────────┘
```

**El indicador de enlace** es la forma de saber si ya hay red, y cambia solo:

| En el menú | Significa |
|---|---|
| `Enlace: uniendo...` | Todavía sin gateway; la sonda reintenta por detrás. **El menú funciona igual** |
| `Enlace: OK` | Ya hay enlace. Al arrancar, el primer uplink sale en el acto |

Antes (v1) la sonda **se quedaba colgada en `JOIN #n...`** hasta cerrar el enlace, y con
ella todo el control: sin gateway no había menú, ni botón, ni emparejamiento. Eso se
acabó — ahora nada de eso espera al enlace.

> **Salvo la primera vez, va directa a emparejar.** Si la sonda no tiene **ningún móvil
> emparejado** —está recién reflasheada, o se le borraron los emparejamientos— al
> arrancar va a la **pantalla de emparejado** (§6), **sin esperar al enlace**. Se
> reconoce al instante porque pone `EMPAREJA LA APP` y el LED está apagado. Una
> **pulsación corta** te lleva al menú y la sonda funciona con el botón como siempre.
> Que se pueda emparejar **sin enlace LoRa** es justo lo que la v1 no permitía: una
> sonda nueva fuera de cobertura no había forma de emparejarla.

**Puedes arrancar aunque el enlace aún diga `uniendo...`.** No hace falta esperar a
`Enlace: OK`: si arrancas antes, la sonda entra en **ESPERANDO ENLACE** (§7.3) y la
corrida empieza sola en cuanto une. Si prefieres el primer uplink en el acto, espera a
`Enlace: OK` antes de la doble pulsación.

> La sonda hace un **join real en cada arranque** — no reutiliza la sesión anterior. Es
> deliberado: así `Enlace: OK` garantiza que hay un gateway escuchando de verdad, en
> lugar de dejarte transmitir al vacío y descubrirlo al analizar. **Si en el cerro el
> enlace no llega a `OK`, no es un fallo del equipo: es el resultado.** Significa que
> desde ahí no hay enlace, y eso se anota en la hoja de campo como un dato, no como una
> avería. La diferencia con la v1 es que ahora la sonda **sigue operable** mientras
> tanto: puedes emparejar, navegar y hasta dejar una corrida esperando el enlace.

---

## 6. Emparejar la sonda con el móvil

**Esto se hace una sola vez por teléfono.** Después, cada vez que la app y la sonda se
encuentran, el enlace se restablece **solo, en menos de un segundo, sin diálogo y sin
código**. No hay peaje diario.

La sonda entra en la pantalla de emparejado en dos situaciones, y sólo en esas dos:

- **Al arrancar, si no tiene ningún móvil emparejado — sin esperar al enlace.** Es lo
  que pasa con una sonda recién reflasheada o recién borrada. No hace falta que haya red:
  se empareja aunque el enlace LoRa aún esté `uniendo...`.
- **Cuando se lo pides: pulsación LARGA desde el menú.** Es la única forma de abrir la
  ventana de emparejamiento con la sonda ya en marcha.

Fuera de esa pantalla **la sonda rechaza cualquier intento de emparejarse**, corte la
conexión y no enseña ningún número. Eso es deliberado y es lo que protege el equipo:
nadie puede emparejar un móvil nuevo con esta sonda sin **estar delante de ella y
pulsarle el botón**. También significa que si intentas emparejar sin haber hecho la
pulsación larga, fallará — y fallará de forma poco explicativa.

---

### 6.1 ⚠️ EL CÓDIGO APARECE *DURANTE* EL EMPAREJAMIENTO, NO ANTES

> **Léelo dos veces, porque en pruebas reales esto se interpretó como una avería y
> costó un buen rato.**
>
> **Al entrar en la pantalla de emparejado NO hay ningún número. Eso es CORRECTO.**
> La pantalla muestra tres renglones y ni una cifra. El código de 6 dígitos **no
> existe todavía**: lo genera la sonda **en el instante en que un teléfono pide
> emparejarse**, y aparece **a la vez que el diálogo de Android**.
>
> Si ves la pantalla sin número, **no está rota, no se colgó y no le falta nada**:
> está esperando a que conectes desde la app. **Conecta desde la app y el número
> saldrá.**

**La secuencia exacta, paso a paso, y qué se ve en cada uno:**

**Paso 1 — Pon la sonda en modo emparejar.**
Con la sonda en el menú (la línea de selección parpadeando, el LED parpadeando),
**pulsación larga** (≥ 2 s). Si la sonda acaba de arrancar sin ningún móvil
emparejado, ya está aquí sola y este paso no hace falta.

En la pantalla verás esto — **y ningún número**:

```
┌─────────────────────┐
│EMPAREJA LA APP      │
│                     │
│                     │
│Conecta desde la app │   ←── NO hay código todavía. Es lo correcto.
│                     │
│                     │
│                     │
│corto = saltar       │
└─────────────────────┘
```

**El LED está apagado**, como mientras la sonda busca enlace. La regla del LED no
cambia: parpadea ⇔ estás en el menú, y esto no es el menú.

**Paso 2 — Conecta desde la app.**
En la app: menú `≡` → **Dispositivo (BLE)** → **Buscar sonda** → toca `PICARO-CAMPO`.
La app conecta y **pide el emparejamiento**. Hasta aquí la pantalla de la sonda sigue
sin número, y sigue estando bien.

**Paso 3 — Ahora sí: aparece el número, y a la vez el diálogo de Android.**
En el mismo momento en que Android saca su diálogo pidiendo un código, la pantalla de
la sonda cambia a esto:

```
┌─────────────────────┐
│EMPAREJA LA APP      │
│                     │
│                     │
│CODIGO  012345       │   ←── AHORA aparece. Seis dígitos, siempre.
│                     │
│                     │
│                     │
│teclealo en el movil │
└─────────────────────┘
```

**Paso 4 — Teclea ese número en el diálogo de Android y acepta.**
Son **siempre seis dígitos**, con los ceros de delante incluidos: si la pantalla dice
`012345`, se teclean **`012345`**, seis caracteres, no `12345`. El diálogo es del
sistema, sale **encima de la app** y al aceptarlo vuelves a la app sin más pasos: no
hay que entrar en los Ajustes de Android para nada.

**Paso 5 — Listo.**
La sonda sale sola al menú (línea parpadeando, LED parpadeando otra vez) y en la app el
indicador de Bluetooth de la barra superior se pone **verde** y dice `sonda`. A partir
de aquí el selector de corridas se desbloquea.

**El número cambia en cada emparejamiento y no se guarda en ningún sitio.** No hay que
apuntarlo ni recordarlo: se usa una vez y se tira. Las llaves las guarda Android por su
lado y la sonda por el suyo; la app no custodia ningún secreto, y por eso **reinstalar
la app o reiniciar la sonda no obliga a emparejar de nuevo**.

**Si te equivocas al teclear**, la pantalla lo dice con todas las letras y vuelve sola
al paso 1 a los 3 segundos:

```
┌─────────────────────┐
│EMPAREJA LA APP      │
│                     │
│                     │
│FALLO DE EMPAREJADO  │
│codigo mal tecleado  │   ←── o `st=NNNN` si fue cualquier otra cosa
│                     │
│                     │
│corto = saltar       │
└─────────────────────┘
```

Si en vez de `codigo mal tecleado` aparece `st=` y un número, no fue un error de tecleo:
anótalo, es lo que sirve para diagnosticarlo después.

---

### 6.2 ⚠️ PARA REEMPAREJAR HAY QUE BORRAR POR LOS DOS LADOS

> **El emparejamiento tiene dos mitades y cada una vive en un sitio distinto:** una
> llave en el teléfono y otra en la sonda. **«Olvidar el dispositivo» en Android borra
> sólo la del teléfono; la de la sonda sigue ahí.** Y al revés: borrar en la sonda no
> toca la del teléfono.
>
> **Si borras sólo un lado, el emparejamiento falla de formas confusas** — a veces sin
> mensaje, a veces con un fallo que parece de tecleo y no lo es. Cuando algo raro pase
> con el emparejamiento, la causa casi siempre es ésta.

**El procedimiento completo para volver a emparejar, entero y en orden:**

1. **En el móvil:** Ajustes de Android → Bluetooth → `PICARO-CAMPO` → **Olvidar este
   dispositivo**. (No sirve hacerlo desde la app: la app no gestiona las llaves, las
   gestiona el sistema.)
2. **En la sonda:** ponla en modo emparejar con una **pulsación LARGA desde el menú**, y
   ahí dentro haz una **DOBLE pulsación**. Eso olvida **todos** los móviles emparejados.
   La sonda se queda en la misma pantalla, sin número, lista para emparejar de nuevo.
3. **Vuelve a emparejar** siguiendo §6.1 desde el paso 2.

**No te saltes la pulsación larga del punto 2.** La ventana de emparejamiento **sólo se
abre con ese gesto**. Sin él la sonda rechaza cualquier intento de emparejarse, y el
síntoma que verás en la app es que «no se pudo emparejar», sin más pistas.

**Cuándo hay que borrar los dos lados y cuándo no:**

| Situación | Qué hacer |
|---|---|
| Quieres quitar un móvil que **todavía tienes** | «Olvidar dispositivo» en Android y ya. La llave que queda en la sonda es inservible sin la otra |
| **Perdiste el móvil** y quieres revocarlo de verdad | Larga desde el menú + **DOBLE pulsación** en la sonda. Es el único modo: a los Ajustes de ese teléfono ya no puedes entrar |
| Olvidaste en Android pero la sonda no se enteró | Larga en la sonda y vuelve a emparejar; la sonda rehace su lado sola |
| Borraste en la sonda pero el móvil no | **Hay que olvidar también en Android**, o el móvil intentará usar una llave que ya no existe |
| Quieres **añadir** un móvil de repuesto sin perder el que funciona | Sólo larga + emparejar el nuevo. **No hagas la doble**: caben hasta tres móviles a la vez |

---

### 6.3 Los dos gestos de la pantalla de emparejado

**Pulsación CORTA — salir sin la app.** Vuelve al menú y deja la sonda operable con el
botón, sin haber emparejado nada. Es el seguro contra quedarse encerrado en esta
pantalla: si el móvil está muerto, se ha quedado en casa o no tiene la app instalada,
una pulsación corta devuelve la sonda al menú y la salida de campo **no se pierde**.
Por eso está anunciado en la propia pantalla (`corto = saltar`). La **larga** hace lo
mismo, porque la regla de campo no tiene excepciones: **larga = ir al menú, siempre**.

**DOBLE pulsación — borra TODOS los emparejamientos.** Es la acción destructiva de esta
pantalla: la sonda olvida todos los móviles y hay que emparejarlos otra vez, uno por
uno. La sonda **no sale** de la pantalla al hacerlo: se queda ahí, sin número, para que
puedas emparejar de nuevo en el acto.

> **Este gesto NO está escrito en la pantalla, a propósito**, para que nadie lo pruebe
> «a ver qué hace» y desemparejé el móvil que estaba funcionando en mitad de una
> campaña. Eso significa que **este manual es el único sitio donde ese gesto existe**.
> Si el manual se pierde, se pierde el gesto con él.

Es el mismo vocabulario de siempre, sin reglas nuevas que aprender: la **doble** es, en
todo el firmware, «el acto deliberado e irreversible de esta pantalla» — en el menú
arranca una corrida; aquí olvida los teléfonos.

---

### 6.4 Un móvil a la vez

La sonda admite **una sola conexión**. Mientras un teléfono la tiene, **deja de
anunciarse**: un segundo móvil ni siquiera la encontrará al escanear. No es un fallo, y
tiene una consecuencia práctica que conviene conocer:

**Si vas a emparejar un móvil nuevo, el que ya está emparejado estorba.** Al entrar en
modo emparejar, la sonda corta ella misma la conexión activa para dejar sitio; y la app
del móvil viejo, si ve que la sonda está en modo emparejar, **se aparta sola y deja de
reconectar** hasta que se lo pidas. Verás en ella el aviso de que se ha desconectado
para dejar sitio. Es lo correcto: si no se apartara, el móvil que llevas en el bolsillo
bloquearía el emparejamiento del nuevo y no habría forma de adivinar por qué.

---

## 7. Elegir la corrida y arrancar

### 7.1 Desde la app (camino normal)

Elige la corrida en el **selector del Panel** y pulsa el botón grande **Arrancar**. Con
esa única acción la app, en este orden: conmuta el device profile del servidor, abre la
sesión de captura, y ordena a la sonda que arranque ese escenario y esa clase.

En la sonda **no hay que tocar nada**. La verás dejar de parpadear y pasar a la
pantalla de corrida ella sola, igual que si hubieras hecho la doble pulsación — es
literalmente lo mismo, sólo que dicho desde el móvil. Si aún no hay enlace LoRa
(`Enlace: uniendo...`), no arranca en el acto: pasa a **ESPERANDO ENLACE** y empieza sola
al unir (§7.3).

**Si el selector está en gris y no deja elegir**, es que la sonda no está lista **por
Bluetooth** — el gate es el enlace BLE, **no** el LoRa. La app dice por qué justo debajo
del selector: la lees y actúas. Lo más frecuente es que la sonda esté apagada, fuera de
alcance o aún emparejándose. **Que la sonda no tenga enlace LoRa NO cierra el gate**: se
puede arrancar sin él y la corrida queda esperando (§7.3); el enlace LoRa aparece como
indicador aparte, no como bloqueo. El botón **Abortar**, en cambio, **está siempre
disponible**, con Bluetooth o sin él: una sesión abierta en el servidor tiene que poder
cerrarse aunque el enlace se haya caído.

Anota en la hoja de campo el momento de arrancar: hora UTC de inicio, corrida y carga
de batería.

### 7.2 Con el botón (respaldo)

Idéntico a la v1, sin un solo cambio:

```
┌─────────────────────┐
│ELIGE CORRIDA        │
│Enlace: OK           │  ←── "uniendo..." hasta que hay red
│> CERRO16 Clase C    │  ←── PARPADEA
│SF10/DR0 fPort 16    │
│8.0s x 300 uplinks   │
│Perfil: terreno-c    │
│corto = cambiar      │
│doble = ARRANCAR     │
└─────────────────────┘
```

**La línea que parpadea es la selección.** El resto se queda fijo para que puedas
verificar, sin prisa, exactamente qué vas a lanzar: el spreading factor, el fPort que
va a etiquetar la corrida, la duración y el perfil que necesita el servidor.

> 💡 **El LED de la placa parpadea mientras estás en el menú.** Es la confirmación de
> que estás **configurando y no midiendo**, y se ve de lejos y de reojo, sin acercarte
> a leer la pantalla. En cuanto arranca la corrida, el LED se apaga. Regla única:
> **LED parpadeando ⇔ estás en el menú**.

Cada **pulsación corta** avanza a la siguiente de las seis opciones, en este orden:

```
URBANO Clase A  →  URBANO Clase C  →  TERRAZA Clase A
      ↑                                      ↓
CERRO16 Clase C  ←  CERRO16 Clase A  ←  TERRAZA Clase C
```

> **El menú responde con un retardo de ~0,4 s.** No es un fallo. Para saber que una
> pulsación no es la primera de una doble hay que esperar a que venza la ventana de la
> doble pulsación. Es el precio de tener dos gestos en un solo botón. Pulsa y espera a
> ver el cambio; no insistas, o saltarás dos opciones.

Comprueba las tres cosas antes de arrancar:

1. **el escenario y la clase** son los que vas a medir
2. **el fPort** coincide con la tabla (11/12 urbano, 13/14 terraza, 15/16 cerro)
3. **el perfil** de la línea 5 es el que dejaste puesto en §4

Y para arrancar: **doble pulsación**. La línea deja de parpadear, la selección se
guarda y la corrida empieza de inmediato. Ése es el momento que hay que anotar en la
hoja de campo: hora UTC de inicio, corrida y carga de batería.

> **Ojo con mezclar los dos caminos.** Si arrancaste la sesión en la app y luego
> arrancas la sonda a mano con una corrida distinta, vuelves a tener las dos mitades
> descoordinadas — que es exactamente lo que la v2 elimina cuando se usa un solo
> camino. La app lo cazará (verás una banda de aviso), pero el rato que tardes en verla
> es un rato de datos perdidos.

### 7.3 Si arrancas sin enlace: ESPERANDO ENLACE

Si arrancas —por la app o con la doble pulsación— cuando el indicador aún dice
`Enlace: uniendo...`, la corrida **no se pierde ni se rechaza**: la sonda la deja
**agendada** y entra en esta pantalla:

```
┌─────────────────────┐
│ESPERANDO ENLACE     │
│                     │
│CERRO16 Clase C      │  ←── la corrida que arrancará
│fPort 16             │
│                     │
│sin enlace aun: 12s  │  ←── segundos esperando
│                     │
│larga = abortar      │
└─────────────────────┘
```

La corrida **arranca sola** en cuanto la sonda une: pasa directa a la pantalla de
corrida y empieza a transmitir, sin que toques nada. Mientras esperas:

- **Larga = abortar.** Cancela la espera y vuelve al menú. Es la misma regla de siempre
  (larga = ir al menú), y significa que **nunca te quedas encerrado** esperando un
  enlace que no llega.
- **Desde la app**, el botón grande queda en **Abortar** y la app muestra «esperando
  enlace» (ver [`APP-CAMPO.md`](APP-CAMPO.md)). Abortar sigue disponible siempre.

Antes de la v2 esto no existía: sin enlace, la sonda se colgaba en `JOIN` y no había
forma de dejar una corrida lista para arrancar en cuanto entrara la red. Es útil en el
cerro: montas, arrancas, y la corrida empieza en el segundo en que aparece el gateway.

---

### 7.4 Si cambias de clase (A↔C): la app reconfigura la sonda sola

> **Esto es nuevo y conviene saberlo antes de que ocurra en el cerro:** el servidor
> LoRaWAN **congela** la clase de la sonda en el momento del último join y no la
> actualiza aunque cambies el device profile. Si arrancas una corrida de la clase
> contraria a la del último join, el servidor lo detecta y hace falta un join nuevo
> para ponerlo al día. **La app lo resuelve sola.**

**Qué vas a ver.** Al pulsar **Arrancar** con una clase distinta de la del último join,
la app puede mostrar brevemente un aviso de que está **reconfigurando la clase de la
sonda**. Por detrás, le está pidiendo a la sonda por Bluetooth que **rehaga el join**
—descarta la sesión LoRaWAN y vuelve a unirse, igual que al encender, sin que la sonda
se apague ni se reinicie—. En la pantalla de la sonda puede verse un instante `Enlace:
uniendo...` (la misma pantalla de §5), y en cuanto el join nuevo cierra, **la app
reintenta el arranque sola** y la corrida empieza. Tarda lo que tarde un join —normal,
unos segundos; si no hay gateway al alcance, lo que tarde en aparecer uno—, y durante
la espera la sonda **sigue siendo operable** (§5): no hace falta tocar nada.

**Tú no tienes que hacer nada.** No hay que apagar la sonda, no hay que tocar
`perfil.py` a mano, no hay que reintentar el Arrancar. Es exactamente el mismo
principio que ya rige el resto de la v2: eliges una vez, en la app, y las dos mitades
del sistema se ponen de acuerdo solas.

**El respaldo, si la app avisa de que no puede.** Dos casos concretos:

- **La app dice que el firmware de esta sonda no soporta re-join.** Es una sonda con un
  firmware anterior a esta función. **Apaga y enciende la sonda** antes de arrancar la
  corrida de la otra clase — un join nuevo al encender logra exactamente lo mismo que
  el re-join automático, solo que a mano.
- **Estás operando con el botón (§7.2), sin la app.** El botón no tiene un gesto para
  esto — el respaldo es el mismo: **apaga y enciende la sonda** antes de arrancar la
  corrida de la clase contraria a la del último join, y no olvides el device profile
  (§4).

> **Por qué existe este paso.** El servidor congela la clase con la que unió la última
> vez y un cambio de perfil por sí solo no la actualiza. La sonda hace su único join al
> encender (§5), casi siempre **antes** de que elijas la corrida en la app — así que sin
> este remedio, el servidor seguiría operando con la clase de la corrida anterior y una
> Clase A podría quedarse sin recibir ningún downlink, con aspecto de corrida
> perfectamente normal. Detalle técnico completo: decisión D-62 de la bitácora del
> proyecto.

---

## 8. Durante la corrida

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

La pantalla se refresca **una vez por ciclo**, cada ~8 s. Que los segundos de la
línea 7 avancen a saltos es normal.

**El LED está apagado.** Si lo ves parpadear, no estás midiendo: estás en el menú.

### Qué mirar

**`TX 42/300 OK 41`** — el primer número son los intentos y el segundo los que salieron
sin error. Si empiezan a separarse, el problema es del equipo, no del enlace: el
paquete ni siquiera llegó a la antena. Esos fallos también se registran, porque son
parte del denominador.

**`GPS FIX s:9`** — sin fix, `lat` y `lon` van vacías y la fecha del nombre de fichero
sale como `00000000`. La corrida sigue siendo válida para el PDR, pero pierdes la
posición. Espera al fix antes de arrancar siempre que puedas.

**`DL ping #12 186s`** — la única confirmación visual de que llegó un downlink. No hay
LED ni actuador. El número es la secuencia que puso el servidor, así que se puede
cotejar contra los downlinks enviados que registra la sesión (D-61) sin
descargar la microSD. Pasados 600 s muestra
`+10m` en vez de los segundos.

**`Bat 87%`** — es la carga **restante** (100 = llena), estimada por el chip de
alimentación. Sirve para decidir si aguantas la corrida, no como medida experimental:
avanza en pasos de 1 % y en 40 minutos apenas se mueve.

> **Si el medidor de batería falla**, la pantalla muestra `Bat --` (no un porcentaje
> inventado) y el servidor recibe la batería como «desconocida», no como 100 %. Los
> milivoltios de al lado son lectura directa del ADC y siguen siendo fiables aunque el
> porcentaje no esté disponible.

### Durante la corrida el botón casi no hace nada

Las pulsaciones cortas y dobles **se ignoran a propósito**. Un roce del botón en la
mochila no puede alterar una medida de 40 minutos. Lo único que responde es la
pulsación larga.

---

## 9. Abortar una corrida

**Desde la app:** botón grande **Abortar**. La sonda vuelve al menú y la sesión de
captura se cierra en el servidor, las dos cosas con una sola pulsación.

**Desde la sonda:** **pulsación larga (≥ 2 s)**. Aparece `ABORTADA` un segundo y medio
y vuelve al menú.

> **Abortar en la app funciona siempre, con Bluetooth o sin él.** Es la única acción
> que no depende del enlace, y es deliberado: si el Bluetooth se cae con una corrida en
> marcha, tienes que poder cerrar igualmente la sesión del servidor. Lo que la app hace
> es intentar parar la sonda por Bluetooth y, haya podido o no, cerrar la sesión.
>
> **Consecuencia que hay que conocer:** si abortas en la app sin enlace, la **sesión se
> cierra pero la sonda sigue transmitiendo**. Hay que ir a pararla con la pulsación
> larga. Y al revés: si abortas con el botón teniendo una sesión abierta, la app te lo
> avisará con una banda —«la sonda ya no está corriendo pero la sesión sigue
> abierta»— y te ofrecerá cerrarla ahí mismo. Esa banda no se descarta: mientras esté,
> hay una sesión grabando nada y falseando su propia duración, que es la ventana con la
> que después se cruza la microSD.

Abortar es una operación normal y limpia. Lo ya registrado **no se pierde ni se
mezcla**: cuando reanudes el mismo escenario y clase el mismo día, el firmware detecta
el fichero anterior y crea uno nuevo con número de intento:

```
20260814-CERRO16-C.csv      primer intento (abortado a los 20 uplinks)
20260814-CERRO16-C-2.csv    segundo intento (el bueno)
```

Los scripts de análisis tratan los intentos como **corridas distintas**: todos aparecen
en `resumen.csv`, pero para comparar Clase A contra Clase C y para las figuras se usa
el más completo, y avisan por pantalla de cuáles no usaron. Si abortaste fue por algo,
y fundir un intento de 20 uplinks con uno de 300 mezclaría condiciones que no son
comparables.

Anota en la hoja de campo **por qué** abortaste. En el análisis, un intento corto sin
explicación es un agujero.

---

## 10. Al terminar

Al llegar a los 300 uplinks:

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

La sonda **se queda ahí y deja de transmitir**. No arranca la siguiente sola: hacerlo
mezclaría dos corridas, y quien llegue a la sonda tiene que poder ver de un vistazo
que ésta terminó bien y que no hay nada corriendo.

Sigue escuchando downlinks: un ping tardío de la corrida que acaba de cerrar todavía
es un dato de latencia válido.

Anota la hora UTC de fin y los contadores finales. Para la siguiente corrida:

- **Desde la app:** elige la siguiente corrida y pulsa **Arrancar**. Desde
  `FINALIZADO` la sonda arranca directamente, **sin pasar por el menú**, y la app
  vuelve a poner el perfil que toque. No hay que tocar la sonda — **si la siguiente
  corrida cambia de clase (A↔C)**, la app puede tardar un poco más mientras reconfigura
  la sonda sola (§7.4); sigue sin haber que tocar nada.
- **Con el botón:** **pulsación larga** → vuelves al menú → y **repite desde §4**,
  incluido el device profile si cambias de clase. Si cambias de clase respecto al
  último join, **apaga y enciende la sonda** antes de arrancar (§7.4): con el botón no
  hay re-join automático.

> **La asimetría es a propósito.** El botón no sabe decir «arranca la 3», sólo navegar,
> así que desde `FINALIZADO` necesita pasar por el menú. El Bluetooth sí sabe decir
> cuál, y obligarle a dar el mismo rodeo no aportaría nada. El comportamiento del botón
> **no cambia** ni un ápice respecto a la v1.

### Si el servidor no se entera de que terminó: «Marcar finalizada» en la app

El PDR que ve el servidor es **estimado**, y en el cerro puede ser bastante más bajo que
el real. Si se pierden más uplinks de los que el servidor cree, la sesión puede no llegar
nunca a contar los 300 que hacen falta para autofinalizarse sola, aunque la sonda **ya**
esté en `FINALIZADO` en su propia pantalla. En ese caso la sesión queda abierta —
«capturando»— con la sonda ya parada, y hay que cerrarla a mano. También es el botón a
usar si decides cortar la corrida **antes** de los 300 uplinks porque ya tienes dato
suficiente, sin que cuente como un aborto.

**Desde la app**, en el Panel, debajo del botón grande mientras la corrida está en
marcha: **Marcar finalizada**.

- **Si la sonda ya terminó sola** (pantalla en `FINALIZADO`), la app lo ve por Bluetooth y
  cierra la sesión directamente: no pregunta nada ni le manda nada a la sonda.
- **Si la sonda todavía está transmitiendo** (o esperando enlace), la app pregunta antes
  de tocar nada: «La sonda sigue corriendo — Vas a dar la corrida por finalizada, pero la
  sonda todavía está transmitiendo. ¿Paro también la sonda?», con el botón **Parar y
  finalizar**. Si cancelas, no se cierra nada. Si confirmas, la app para la sonda por
  Bluetooth —el mismo comando que Abortar— y **después** cierra la sesión: sonda primero,
  servidor siempre, igual que al abortar (§9).
- **Si la app avisa que la sonda NO confirmó la parada** (sin Bluetooth, o la sonda
  rechazó el comando), la sesión se cierra igual en el servidor, pero la sonda sigue
  transmitiendo: ve a pararla con el respaldo de siempre, la **pulsación larga (≥ 2 s)**.

> **Ojo con lo que queda registrado.** Una corrida cortada así con «Marcar finalizada»
> queda marcada como **finalizada** en el servidor aunque no haya llegado a los 300
> uplinks — es decir, es una corrida **parcial con etiqueta de completa**. El análisis
> puede distinguirla igual, porque su recuento de uplinks se queda corto frente al
> objetivo, pero anótalo en la hoja de campo: el estado que muestra la app no basta por sí
> solo para saber si una corrida llegó a los 300. Sigue aplicando el criterio de siempre
> para una corrida incompleta: **márcala parcial y repítela** (D-29 de la bitácora).

---

## 11. Los gestos del botón

Tres gestos, y sólo tres. Todo lo que hacían en la v1 lo siguen haciendo igual; lo
único que gana la v2 son las dos columnas y media de la derecha.

| Gesto | En el MENÚ | En CORRIDA | En FINALIZADO | En EMPAREJADO |
|---|---|---|---|---|
| **Corta** | siguiente opción | — | — | **saltar → menú** |
| **Doble** | **ARRANCAR** | — | — | **borra TODOS los emparejamientos** |
| **Larga** (≥ 2 s) | **modo emparejar** | abortar → menú | → menú | → menú |

Una sola regla que recordar: **larga = ir al menú, siempre**. Sirva la corrida en
marcha o terminada, la pantalla de emparejado o la de **esperando enlace** (§7.3), donde
larga = abortar la espera y volver al menú. La única excepción aparente es el menú, donde
ya estás en el menú y por eso la larga quedaba libre: ahí es donde se ha colgado el gesto
de **abrir la ventana de emparejamiento** (§6).

Y la **doble** conserva su significado de siempre: *el acto deliberado e irreversible
de esta pantalla*. En el menú, arrancar una corrida. En la pantalla de emparejado,
olvidar todos los teléfonos. No es una regla nueva, es la misma aplicada donde toca.

> **La doble de la pantalla de emparejado no está escrita en la pantalla**, para que
> nadie la pruebe por curiosidad. **Este manual es el único sitio donde ese gesto
> existe.** Ver §6.3.

Y el LED confirma en cuál de los dos mundos estás, sin mirar la pantalla:

| LED | Significa |
|---|---|
| **Parpadeando** (1 Hz) | Estás en el **menú**. No se está midiendo nada |
| **Apagado** | Cualquier otra cosa: buscando red, emparejando, corrida en marcha, o `FINALIZADO` |

Es deliberadamente binario. Distinguir corrida de `FINALIZADO` es trabajo de la
pantalla, que ya lo dice con todas las letras; el LED responde a una sola pregunta,
que es la que se hace uno al acercarse a la sonda: *¿está midiendo o la estoy
configurando?*

> Con la sonda **apagada y cargando por USB**, el LED no indica el estado de carga: se
> queda con lo último que escribió el firmware. Para saber si cargó, mira la tensión
> de batería al encender.

La pulsación larga se registra al cumplirse los 2 s, sin esperar a que sueltes: en
cuanto la pantalla reaccione, puedes soltar.

---

## 12. Qué hacer si…

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `Enlace: uniendo...` no pasa a `OK` | Sin gateway al alcance o servidor caído | La sonda **sigue operable**: empareja y navega igual. Si arrancas, queda en ESPERANDO ENLACE. Verifica el gateway en la consola |
| Se queda en `ESPERANDO ENLACE` | Arrancaste sin enlace y aún no une | Normal: arranca sola en cuanto une. Si no quieres esperar, **larga = abortar** (§7.3) |
| La pantalla no cambia nunca | La sonda se colgó | Apaga y enciende. Si se repite, anótalo y usa otra batería |
| `GPS --  s:0` persistente | Cielo obstruido o arranque en frío | Hasta 5 min a cielo abierto. Sin fix pierdes la posición, no la corrida |
| `TX FALLO` repetido | Antena floja o radio en mal estado | Para. Revisa la antena antes de gastar la batería |
| El menú salta dos opciones | Pulsaste antes de que respondiera | Pulsa y **espera** a ver el cambio (~0,4 s) |
| El LED parpadea y creías estar midiendo | Estás en el menú: la corrida no ha arrancado | Doble pulsación para arrancar |
| El LED no parpadea al volver al menú | El PMU no respondió al arrancar | La corrida sigue siendo válida; guíate por la pantalla y anótalo |
| Los pings tardan segundos en Clase C | **El device profile del servidor está en Clase A** | `python perfil.py terreno-c`. La corrida hecha así no mide latencia de Clase C |
| La app avisa «reconfigurando la sonda» al Arrancar, y tarda unos segundos más | Cambiaste de clase (A↔C) respecto al último join: la app está haciendo un **re-join automático** por Bluetooth (§7.4) | Normal. Espera: la app reintenta el arranque sola cuando la sonda vuelve a estar lista |
| La app avisa que el firmware no soporta re-join | Sonda con firmware anterior a esta función | **Apaga y enciende la sonda** antes de arrancar la corrida de la otra clase (§7.4) |
| `DL --` toda la corrida | No llega ningún downlink | Desde D-61 los pings los lanza el **microservicio** mientras la sesión captura, así que no hay ningún proceso que arrancar a mano. Si la sesión está abierta y aun así no llega ninguno, sospecha de la clase efectiva (§7.4) antes que de la radio |
| `Bat --` | El medidor de batería no respondió | El porcentaje no está disponible; usa los mV, que sí son fiables |
| Arrancó en `URBANO Clase A` sin haberlo elegido | Se acaba de reflashear y se perdió la selección | Inocuo: elige la corrida en el menú como siempre |
| Dos ficheros del mismo escenario en la microSD | Hubo un intento abortado | Es lo correcto. Los dos se conservan y el análisis usa el más completo |
| La sonda ya está en `FINALIZADO` pero la sesión de la app sigue «capturando» | El PDR real fue más bajo que el estimado por el servidor y nunca llegó a contar los 300 uplinks | Pulsa **Marcar finalizada** en el Panel. La app ve que la sonda ya terminó y cierra la sesión sin mandarle nada (§10) |
| La app avisa «la sonda NO confirmó la parada» al pulsar **Marcar finalizada** | Sin Bluetooth, o la sonda rechazó el comando de parada | La sesión ya se cerró en el servidor. Ve a la sonda y párala con el respaldo de siempre: **pulsación larga** (§10) |

### …algo va mal con el Bluetooth

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| **La pantalla de emparejado no muestra ningún número** | **Ninguna: es lo normal.** El código no existe hasta que un móvil pide emparejarse | **Conecta desde la app.** El número aparece a la vez que el diálogo de Android (§6.1) |
| La app no encuentra la sonda al escanear | Sonda apagada, fuera de alcance, o **con otro móvil ya conectado** | Sólo admite una conexión: mientras un móvil la tiene, deja de anunciarse. Desconecta el otro (§6.4). Verifica también que el Bluetooth del móvil está encendido |
| «No se pudo emparejar» sin más explicación | **Falta la pulsación larga**: la ventana de emparejamiento está cerrada y la sonda rechaza el intento | Larga desde el menú, comprueba que pone `EMPAREJA LA APP`, y reintenta (§6) |
| El emparejamiento falla una y otra vez, de formas distintas | **Se borró un solo lado**: Android olvidó y la sonda no, o al revés | Borra **los dos**: olvidar en Ajustes de Android **y** doble pulsación en la sonda. Luego empareja de cero (§6.2) |
| `FALLO DE EMPAREJADO / codigo mal tecleado` | Tecleaste mal, o de menos | Son **seis** dígitos, con los ceros de delante. `012345` se teclea entero. Vuelve a intentarlo (§6.1) |
| `FALLO DE EMPAREJADO / st=NNNN` | No fue un error de tecleo | Anota el número: es lo único que sirve para diagnosticarlo después |
| El selector de corridas está en gris | La sonda no está lista por Bluetooth (RF-7) | La app dice el motivo debajo del selector. **Abortar sigue disponible** aunque el selector no lo esté |
| El indicador de la barra está en ámbar y no pasa a verde | Conectado pero el enlace aún no es seguro (emparejando, o preparándose) | Espera unos segundos. Si se queda ahí, entra en *Dispositivo (BLE)* y mira qué dice |
| Aviso «Bluetooth caído» en mitad de una corrida | Se perdió el enlace | **La corrida NO se para**: la sonda es autónoma y sigue midiendo. La app reconecta sola. Abortar sigue disponible |
| La app dice que se ha desconectado «para dejar sitio» | La sonda está en modo emparejar y este móvil se apartó | Es lo correcto (§6.4). Cuando acabes de emparejar el otro, pulsa *Reconectar* |
| Aviso «la sonda ya no está corriendo pero la sesión sigue abierta» | Abortaste o terminaste en la sonda y la sesión del servidor quedó viva | Pulsa **Cerrar sesión** en el propio aviso. Si no, la sesión queda grabando nada y falsea su duración |
| «Hay que volver a emparejar» al mandar un comando | La sonda olvidó este móvil (doble pulsación, o desalojado por otro) | Olvida en Ajustes de Android y vuelve a emparejar (§6.2) |
| Emparejé un cuarto móvil y el primero dejó de funcionar | Caben **tres**; el cuarto desaloja al más antiguo | Es el comportamiento previsto. Vuelve a emparejar el que necesites |
| El Bluetooth no afecta a nada de la radio | — | Correcto y verificado: la cadencia de uplinks es la misma con el enlace conectado que sin él |

---

## 13. Al volver

1. **Apaga la sonda** antes de sacar la microSD
2. Copia **todos** los CSV, también los de intentos abortados
3. Transcribe la hoja de campo — en seis meses una foto en un móvil es ilegible
4. Cruza los datos:

```bash
# desde pruebas_terreno/analisis/
python cruzar.py --sd ./datos_sd --db ../dashboard/picaro_telemetry.db
python graficas.py
```

Lee el aviso de **INTENTOS MÚLTIPLES** del resumen si aparece: te dice qué corridas
quedaron fuera de la comparación y por qué.

---

## 14. La jornada del 2026-08-30 — Serie 2, con subida al cerro

Cuatro corridas, en este orden:

| # | Corrida | fPort | Dónde | Nombre esperado |
|---|---|---|---|---|
| 1 | **URBANO Clase C** | 12 | en la ciudad, antes de subir | `20260830-URBANO-C` |
| 2 | **CERRO16 Clase A** | 15 | en la cima | `20260830-CERRO16-A` |
| 3 | **CERRO16 Clase C** | 16 | en la cima | `20260830-CERRO16-C` |
| 4 | **URBANO Clase C** | 12 | al bajar | `20260830-URBANO-C-2` |

La cuarta repite escenario y clase de la primera, así que el firmware le pondrá
el sufijo `-2` solo (D-39). Son corridas distintas y no se mezclan en el
análisis: la 1 y la 4 acotan la jornada por los dos extremos, y si difieren
mucho entre sí, lo que cambió es el canal urbano, no el equipo.

### 14.1 Los dos cambios de clase ocurren en el cerro

Del paso 1 al 2 cambias de Clase C a Clase A, y del 2 al 3 de A a C. **La app lo
resuelve sola**: pide a la sonda un JOIN nuevo por Bluetooth y reintenta el
arranque (§7.4). Es la primera vez que ese mecanismo se usa en campo, así que
conviene saber qué esperar:

- Verás brevemente un aviso de que está reconfigurando la sonda, y luego arranca
  sola. Puede tardar lo que tarde un JOIN.
- **El JOIN se hace a SF10**, el mismo alcance que los uplinks de la corrida del
  cerro. Si la corrida transmite, el JOIN también llega: no es un punto débil
  añadido.
- **Si algo se atasca**, el respaldo de siempre: apaga y enciende la sonda, y
  vuelve a arrancar desde la app. Con la sonda recién encendida el JOIN se hace
  igualmente bajo el perfil correcto, porque la app ya lo dejó puesto.

### 14.2 Qué esperar en la cima

El trayecto está verificado: **15,27 km** con línea de vista y la primera zona de
Fresnel despejada.

| | |
|---|---|
| RSSI previsible | entre **−105 y −125 dBm** |
| Margen sobre la sensibilidad de SF10 | +17 a +47 dB |
| SNR | **puede salir negativo, y es normal** — SF10 trabaja hasta −15 dB |

Un SNR negativo en el cerro **no es un fallo**: es lo propio de un enlace largo a
SF10. Lo que sí sería mala señal es no recibir nada en el móvil: si el dashboard
no ve uplinks a los dos minutos, comprueba la antena y su verticalidad antes de
dar la corrida por buena — hay cobertura de datos en la cima para consultarlo.

### 14.3 Cómo se coloca la sonda (esto cambió tras la Serie 1)

En la Serie 1 el PDR quedó muy por debajo del objetivo, y el diagnóstico apunta
al **cómo**, no al equipo: a 300 m el mismo equipo entrega el 97 %.

- **Antena vertical siempre.** Tumbada pierde varios dB por polarización cruzada.
- **La sonda fuera del vehículo**, o al menos con la antena asomada. La carrocería
  cuesta fácilmente 10-20 dB, y en la Serie 1 las corridas URBANO iban dentro.
- **Apoyada, no en la mano ni pegada al cuerpo**, y al menos a un metro del suelo.
- En la cima, **con el cuerpo fuera de la línea hacia el gateway** (rumbo 74°
  desde el cerro, es decir mirando hacia la ciudad): una persona delante de la
  antena es un obstáculo de varios dB.

### 14.4 Anota las horas de cada corrida

**Esto no es burocracia: hace falta para el análisis.** El nombre que escribe la
sonda en la microSD y el que abre el servidor **pueden no coincidir** —cada uno
numera sus intentos por su cuenta— y el cruce de datos empareja por nombre. Ya
pasó en las pruebas de banco (A-10).

Apunta para cada una de las cuatro:

```
Corrida (escenario y clase):
Hora de inicio (UTC o local, pero di cuál):
Hora de fin:
Nombre que muestra la app:
RSSI típico que veías:
Incidencias (re-join, aborto, reintento):
```

Con la hora, el emparejamiento es inequívoco aunque los nombres bailen.

### 14.5 Antes de salir de casa

| | |
|---|---|
| ☐ | **APK v2.0.4 instalado** en el móvil (el del release `v2.0.4`) |
| ☐ | **Firmware de este release flasheado** en la sonda — sin él no hay re-join |
| ☐ | El móvil **ya emparejado** con la sonda, comprobado en casa |
| ☐ | Batería de sonda y móvil, y la microSD dentro |
| ☐ | Antena **bien apretada y en el conector de LoRa** |
| ☐ | Este manual accesible sin conexión |

---

## Anexo — Las seis corridas

| Corrida | Escenario | DR/SF | fPort A / C | Payload | Perfil requerido |
|---|---|---|---|---|---|
| 1 | `URBANO` — vehículo 30-40 km/h | DR1 / SF9 | 11 / 12 | 14 B | `terreno-a` / `terreno-c` |
| 2 | `TERRAZA` — piso 5, LoS 2,74 km | DR3 / SF7 | 13 / 14 | 14 B | `terreno-a` / `terreno-c` |
| 3 | `CERRO16` — LoS **15,27 km** ¹ | DR0 / SF10 | 15 / 16 | 11 B | `terreno-a` / `terreno-c` |

¹ Distancia medida con las coordenadas reales el 2026-08-29. La cifra anterior
(16,35 km) salía de un punto de cima aproximado. El nombre `CERRO16` y los
`fPort` se conservan: renombrarlos invalidaría el etiquetado de lo ya medido.

Las tres a **8,0 s** de intervalo y **300 uplinks** (~40 min cada una).

El intervalo no se elige: el servidor tiene `rx1_delay = 5 s` y no se toca, así que en
Clase A no se puede transmitir hasta cerrar RX1 y RX2 y el ciclo mínimo real ronda los
6,5 s. Pedir menos no acelera nada — el stack lo retrasa igual y el intervalo declarado
dejaría de ser el real.

`CERRO16` lleva 11 bytes en vez de 14 porque a SF10 los tres bytes de batería llevarían
el airtime a 412 ms, por encima del límite de 400 ms de US915. La batería de esa
corrida existe solo en la microSD.

## 15. Corrida VUELO (desde el 2026-09-28, D-64)

Simula lo que mandará la cápsula en vuelo. Se elige en la app como **VUELO A** (fila
propia en el selector; no tiene Clase C) o con el botón: es la **séptima** opción del
menú, detrás de CERRO16-C.

- **Qué hace la sonda:** cada minuto toma una lectura completa y la manda en **tres
  paquetes, uno cada 20 s**: P1 posición, P2 ambiente y energía, P3 navegación. La
  pantalla muestra `R12/55 P2 OK`: ráfaga 12 de 55, paquete P2.
- **Cuánto dura:** 55 ráfagas = **55 minutos** (165 uplinks). Termina sola.
- **Dónde:** desde un punto **fijo** (un cerro, una azotea alta), con la sonda quieta
  y la antena vertical. Anota en la hoja de campo el punto, la altura y la hora UTC de
  inicio y fin.
- **Qué mirar en la app:** el bloque «Vuelo · última lectura». Cada dato lleva el paquete
  y la ráfaga de donde salió (`P1 r12`): si un dato se queda viejo, es que ese paquete
  no está llegando. Las ráfagas completas / parciales / perdidas resumen el enlace.
- **Pings:** siguen saliendo uno por minuto. En VUELO indican si la cápsula **recibiría
  una orden** (como el corte) a esa distancia.
- **Sin GPS** (en interiores) P1 llega sin posición: es normal, no un fallo.
- **Al volver:** copia de la microSD `AAAAMMDD-VUELO-A.csv` y
  `AAAAMMDD-VUELO-A_lecturas.csv` a `analisis/datos_sd/`, descarga el CSV de la sesión a
  `analisis/datos_app/` y ejecuta `python vuelo.py` desde `analisis/`.

