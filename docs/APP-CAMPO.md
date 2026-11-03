# App de campo PiCARO — guía del sistema app + microservicio

Cómo se usa la app de campo para **operar y vigilar** una corrida desde el teléfono, y
qué hace por detrás el microservicio que corre junto a ChirpStack.

Este documento es el compañero del [manual de campo](MANUAL-DE-CAMPO.md): aquél explica
la **sonda** (lo físico, el botón, el OLED); éste explica la **app** (lo online, la
sesión, las métricas). Los dos se leen juntos, porque la operación de campo es
justamente **sincronizar** las dos mitades. La especificación técnica completa —
endpoints, modelos de datos, variables de entorno — vive en
[CONTRATO-CAMPO.md](CONTRATO-CAMPO.md); aquí se cuenta **para qué sirve** cada cosa y
**cómo se opera**, no cómo se implementa.

> **La idea en una frase.** Desde la v2 la app hace **las dos cosas con una sola
> acción**: abre la sesión de captura en el servidor **y** arranca la sonda por
> Bluetooth. El botón de la sonda se conserva íntegro como respaldo.

---

## 1. Qué es, y qué NO es

Léelo despacio, porque aquí estaba el malentendido más caro del sistema — y porque la
**v2 cambió la respuesta**.

### Lo que cambió en la v2

**Hasta la v1, la app no podía arrancar la radio.** La sonda se arrancaba
**físicamente** —menú en el OLED, pulsaciones cortas, doble pulsación— y la app se
limitaba a abrir una sesión de captura en el servidor. Eran **dos actos humanos
independientes** que había que coordinar a mano, y podían divergir: elegir CERRO16-C en
la app y CERRO16-**A** en la sonda producía datos con aspecto perfectamente normal.

**Desde la v2 la selección ocurre en un solo sitio.** Eliges la corrida en el Panel y
pulsas **Arrancar**, y esa única acción se propaga a **las dos mitades**:

1. por **internet**, al microservicio: cambia el device profile a `terreno-a`/`terreno-c`,
   calcula el `expected_fport` (11–17) y abre la fila de sesión;
2. por **Bluetooth**, a la sonda: le ordena arrancar **ese mismo** escenario y clase.

Con eso el desajuste entre app y sonda **deja de poder originarse en un error humano de
selección**: no hay dos elecciones que puedan discrepar, hay una sola.

### Lo que NO cambió

- **La radio no se controla por la red.** El canal nuevo es Bluetooth, **local**: exige
  estar a unos metros de la sonda, y la sonda sólo obedece a un móvil que alguien
  emparejó estando delante de ella, con el dedo en el botón. Controlar la radio por
  internet sigue descartado, y por las mismas razones de siempre: en Clase A los
  downlinks esperan a la ventana RX, y en el cerro la cobertura de datos va y viene.
- **El botón sigue siendo un respaldo completo.** Navegar, arrancar, abortar y volver al
  menú, sin app, sin teléfono y sin cobertura. No es un modo degradado.
- **La corrida es autónoma.** Si el Bluetooth se cae a mitad de una corrida, **la corrida
  sigue**. El enlace es control, no soporte: la app reconecta sola y vuelve a leer el
  estado.
- **La sonda sigue sin hablar con ChirpStack.** Sólo habla LoRa. El perfil lo pone el
  microservicio, exactamente como en la v1.
- **El aviso de desajuste de fPort se conserva** (§3.1). Ya no debería poder dispararse
  por una selección humana, pero sigue siendo la red que cazaría cualquier otra causa.

| | La sonda (física) | La app |
|---|---|---|
| Qué arranca | la **radio**: transmite de verdad | **las dos cosas**: la sesión en el servidor y la sonda por BLE |
| Con qué | botón: menú + doble pulsación (respaldo) | selector + botón grande **Arrancar** |
| Registro de verdad | **microSD** (todo lo que se envió) | SQLite del servidor (lo que llegó) |
| Si falta | no hay datos: nadie transmite | se opera con el botón, como en la v1 |

---

## 2. Las dos mitades del sistema

```
   ┌──────────────┐   uplinks    ┌────────────┐   MQTT/TLS   ┌───────────────┐
   │    SONDA     │─────────────►│ ChirpStack │─────────────►│ microservicio │
   │ (T-Beam)     │   (radio)    │  (nube)    │              │  picaro-campo │
   └──────────────┘              └────────────┘◄──── REST ───│  (FastAPI)    │
      ▲       ▲                      perfil/ping             └───────┬───────┘
      │       │ botón físico (respaldo)                              │ REST + WS (TLS)
      │    (tú, en el cerro)                                         ▼
      │                                                      ┌───────────────┐
      └──────────────────────────────────────────────────────│  APP (Flutter)│
              BLE — orden de modo y estado (v2)              │  tu teléfono  │
              enlace cifrado y autenticado                   └───────────────┘
```

Fíjate en que la app tiene **dos interlocutores independientes**: el microservicio por
internet (arriba) y la sonda por Bluetooth (abajo). Son dos caminos que no se tocan y
que pueden fallar por separado — de ahí que la app distinga siempre «no hay red» de «no
hay sonda».

- **El microservicio** (`microservicio/`, contenedor `picaro-campo`) se suscribe al MQTT
  de ChirpStack, reconoce los uplinks de nuestro device, los guarda en SQLite ligados a
  la sesión activa y calcula las métricas en vivo. Además llama a la **API REST** de
  ChirpStack para las dos operaciones que antes hacíamos a mano: **cambiar el device
  profile** y **encolar los pings de latencia** (fPort 98). No toca nada más del
  servidor — la regla dura sigue en pie: la configuración global de ChirpStack **no se
  toca** (ver el incidente I-01 de la bitácora).
- **La app** (`app/`, Flutter, APK de instalación local) habla con el microservicio por
  **REST** (las órdenes: arrancar, abortar, finalizar, pedir CSV) y por **WebSocket**
  (el flujo en vivo: cada uplink, las métricas cada pocos segundos, los avisos). Todo por
  **TLS**, contra `https://campo.pi-caro.org`.

El microservicio es una **herramienta online**: es cómodo, enseña lo que está pasando
mientras pasa y permite abortar a tiempo si algo va mal. Pero **no es el registro de
verdad** — eso es la microSD (ver §4).

---

## 3. La secuencia de operación en campo, de principio a fin

Es la coreografía de las dos mitades. El orden importa.

```
   0. Enciende la sonda (queda operable en segundos). Comprueba que el indicador
      BLE de la barra superior está en VERDE («sonda»). El enlace LoRa se muestra
      aparte y NO bloquea: puedes arrancar aunque aún esté uniéndose (§3.3)
   1. En la app: elige la corrida en el Panel y pulsa ARRANCAR
        ├─ el servidor pone el device profile (terreno-a / terreno-c) y abre la sesión
        └─ la sonda recibe la orden por BLE y empieza a transmitir esa misma corrida
   2. Comprueba el ACK: en «Sonda (BLE)» debe verse CORRIENDO con la corrida elegida
   3. Vigila: TX n/300, RSSI/SNR, GPS, batería, último downlink
   4. Al llegar a 300 → FINALIZADO (la sonda deja de transmitir; la sesión se cierra)
   5. En Sesiones: descarga el CSV de la sesión
```

> **El orden interno del paso 1 no es arbitrario: servidor primero, sonda después.** Si
> falla el servidor, no se toca la sonda y no pasa nada. Si se hiciera al revés y fallara
> el servidor, la sonda estaría **transmitiendo** contra un perfil que puede ser el
> equivocado — una corrida de Clase C contra un perfil de Clase A produce una medida
> **silenciosamente falsa** que se lee como «la Clase C no aporta nada». Entre un fallo
> visible y reversible (una sesión vacía, que la app cierra sola) y uno invisible que
> contamina un dato, se elige siempre el primero.

Cada corrida son **300 uplinks**, unos **40 minutos** (VUELO: **165**, 55 min — §5.1). Al terminar, para la siguiente:
elige la corrida y pulsa **Arrancar** otra vez — desde `FINALIZADO` la sonda arranca
directamente, sin pasar por su menú. Si cambias de clase, la app vuelve a poner el
perfil correcto; no hace falta tocar `perfil.py` ni la sonda.

> **Si cambias de clase (A↔C) respecto al último join, puede tardar un poco más.**
> ChirpStack congela la clase efectiva del device en el momento del join y un cambio de
> perfil no la actualiza (D-60/issue #360). Si `start` detecta el desajuste, responde
> **409** con el perfil ya corregido; la app entonces pide a la sonda por Bluetooth que
> **rehaga el join** (D-62) y reintenta el arranque sola cuando termina — se puede ver
> un aviso breve de «reconfigurando la sonda» y la sonda pasando por `Enlace:
> uniendo...`. No hace falta ninguna acción manual. El respaldo, si la sonda avisa de
> que su firmware no soporta re-join, o si se opera con el botón: apagar y encender la
> sonda antes de arrancar la corrida de la otra clase (manual de campo, §7.4).

**Sin Bluetooth**, la secuencia de la v1 sigue siendo válida y es el respaldo: Arrancar
en la app, y luego elegir la misma corrida en la sonda y doble-pulsar. Es lo que se hace
si el móvil no está emparejado o el enlace no se establece. Coordina tú las dos mitades
y comprueba el aviso de desajuste, exactamente como antes.

### 3.1 El aviso de desajuste de fPort — léelo entero

> ⚠️ **EL ERROR MÁS PELIGROSO DE LA CAMPAÑA ES SILENCIOSO. LA APP EXISTE, EN BUENA
> PARTE, PARA CAZARLO.**

Recuerda el fallo de fondo que describe el manual: si la sonda dice una cosa y el
servidor otra —típicamente **la sonda en Clase C pero el servidor en el perfil de Clase
A**— los uplinks llegan con normalidad, el PDR sale bien, el `fPort` dice «Clase C»… y
sin embargo los pings de latencia esperan a la ventana RX del siguiente uplink. El
resultado se lee como «la Clase C no aporta nada», que es la conclusión **opuesta** a la
que el experimento debería alcanzar. No hay ningún mensaje de error. Es un dato con
aspecto perfectamente normal, y no te enteras hasta el análisis, cuando ya bajaste del
cerro.

**Cómo lo caza la app.** La sesión sabe qué corrida elegiste **en la app** (y de ahí
deduce el `expected_fport`: 11–17). Cada uplink que llega trae **el fPort que puso la
sonda**, que depende de lo que elegiste **en la sonda**. Si los dos extremos no coinciden
—elegiste corridas distintas en la app y en la sonda— el fPort no cuadra, y entonces:

- el uplink **no se guarda** en esta sesión (no contamina la corrida);
- salta un **aviso de desajuste** (banda roja en el Panel) con lo que esperaba y lo que
  llegó (`esperaba 16, llegó 15`);
- como no se guarda nada, la sesión **no avanza** (`TX 0/300`) y el aviso se repite en
  cada uplink. Es imposible no verlo.

Y aquí está la parte elegante: como la app **pone el perfil según la corrida que elegiste
en ella**, y a la vez **comprueba que la sonda transmite esa misma corrida**, encadena
las tres cosas —perfil del servidor, clase de la sonda, clase esperada— de forma que ya
no pueden quedar descoordinadas sin que la app lo grite. El punto ciego del manual queda
cubierto.

**Qué hacer si aparece el aviso:** para. No sigas tomando datos. Comprueba que la corrida
elegida en la sonda (escenario **y** clase) es exactamente la que elegiste en la app.
Corrige donde toque y vuelve a empezar la corrida. Un aviso de desajuste ignorado es una
corrida perdida que parecerá buena.

**Qué cambia con la v2.** Cuando se opera por Bluetooth, este aviso **ya no debería
poder dispararse por una selección humana**: no hay dos elecciones que puedan discrepar.
No se retira por eso: sigue vigilando el resto de causas posibles (haber arrancado la
sonda a mano con otra corrida, un firmware que no coincide, un uplink rezagado de una
corrida anterior). Una red de seguridad se quita cuando estorba, no cuando deja de
saltar.

### 3.2 Los dos avisos que añade la v2

Con el enlace Bluetooth, la app ve el estado de la sonda **en el acto**, y con eso caza
dos desajustes que antes sólo se descubrían por el camino largo del servidor —o no se
descubrían—. Los dos aparecen como banda en el Panel, **encima** del aviso de fPort
porque llegan antes, y ninguno de los dos es descartable a mano: mientras están, hay un
problema real.

**① Desajuste sonda↔sesión.** La sonda dice que está corriendo una corrida distinta de
la que abriste en la app. Es el mismo problema que el aviso de fPort, visto desde el
otro lado y **antes** de que llegue un solo uplink. Dice qué corre la sonda y qué
esperaba la sesión, y qué hacer: abortar y volver a arrancar.

**② La sonda se paró y la sesión sigue abierta.** Es el caso que faltaba: abortaste con
el botón, o la corrida terminó, y en el servidor quedó una **sesión abierta grabando
nada**. Pasa siempre que se aborta con el botón, con Bluetooth o sin él, y hasta la v2
no se veía en ninguna parte. Importa por dos motivos: reintroduce justo la divergencia
que la v2 elimina, y **falsea la duración de la sesión**, que es la ventana temporal con
la que después se cruza la microSD.

El aviso trae su propio botón **Cerrar sesión**, con confirmación. **La app no la cierra
sola a propósito:** cerrar una sesión no se deshace, y un estado leído mal mataría una
captura viva. Y sólo avisa si esa sesión **llegó a verse corriendo** — si no, lo que hay
es un arranque en curso, no una parada.

### 3.3 Arrancar sin enlace LoRa: «esperando enlace»

Desde la corrección del arranque en segundo plano, **la sonda es operable en cuanto
enciende**: ya no se cuelga esperando a unirse a la red, sino que adquiere el enlace LoRa
**por detrás**. Eso tiene una consecuencia directa en la app.

**Puedes pulsar Arrancar aunque la sonda todavía no tenga enlace LoRa.** La app abre la
sesión y ordena la corrida igual; la sonda la deja **agendada** y entra en el estado
`ESPERANDO_ENLACE`, que la app muestra como **«esperando enlace»** en el bloque Sonda
(BLE). La corrida **arranca sola** en cuanto la sonda une, y sólo entonces la sonda
publica `CORRIENDO` — que sigue siendo el acuse fiable de «hay corrida real
transmitiendo». En el caso normal (la sonda ya unió mientras montabas el equipo) no ves
esta espera: al arrancar pasa directa a `CORRIENDO` y el primer uplink sale en el acto.

Mientras dura la espera:

- El botón grande queda en **Abortar**, siempre disponible: cancela la sesión y, si
  puede, la espera en la sonda.
- La app **no reenvía** la orden: la sonda ya la aceptó. Espera a ver `CORRIENDO`.

El enlace LoRa vive ahora como **indicador aparte** («uniendo…» / «unida»), no como un
bloqueo del selector. La razón es la que arregló el bug: bloquear el arranque hasta tener
enlace era justo lo que dejaba la sonda inservible fuera de cobertura; separar «puedo
operar» de «hay enlace» elimina esa dependencia (ver D-54 y D-57 de la bitácora).

---

### 3.4 La sonda T3 (`PICARO-LORA32`): solo VUELO y distancia por el GPS del teléfono

La campaña tiene dos sondas, que se operan con **la misma app, el mismo servidor y
el mismo token**, una sesión a la vez (D-65). La app sabe cuál tiene conectada por
su nombre BLE:

| | T-Beam (`PICARO-CAMPO`) | T3 (`PICARO-LORA32`) |
|---|---|---|
| Corridas que ofrece el selector | las 7 | solo **VUELO A** |
| Sensores | reales | **simulados** por la placa (batería real) |
| Distancia al gateway | de su GPS | del **GPS del teléfono** |
| Botón de respaldo | sí | no: solo app |

Con la T3, al arrancar la sesión la app **pide permiso de ubicación** (la primera
vez) y, mientras captura, manda la posición del teléfono al servidor cada 30 s.
**Lleva el teléfono junto a la sonda y con la app abierta en pantalla.** La app no
usa un servicio en segundo plano, y con la pantalla apagada Android puede pausar el
GPS. Mientras tanto, los paquetes se miden igual, pero sin distancia. En el Panel aparece el bloque **«Distancia
· GPS del teléfono»**:

- **la distancia al gateway que recibió el último paquete**;
- la máxima de la sesión;
- el gateway;
- la posición del teléfono y su precisión.

El servidor la calcula y la guarda con la sesión: en el CSV de uplinks (columnas
`tel_*`, `gw_*`, `dist_gw_km`) y en `<run_label>_pos.csv`. El panel de VUELO
muestra los valores simulados de la placa; su posición no se usa para la distancia.

## 4. El PDR de la app es ESTIMADO — la microSD es la verdad

La app te enseña un **PDR estimado** (`pdr_est`, siempre etiquetado «est.»). Es útil en
vivo, pero **no es el PDR definitivo**, y conviene tener claro por qué:

- El PDR es `paquetes recibidos ÷ paquetes enviados`. El servidor **solo ve lo que
  llegó**: conoce el numerador, pero no el denominador real. Para estimarlo, la app usa
  los números de secuencia (`fCnt`): `pdr_est = recibidos ÷ (fCnt_último − fCnt_primero +
  1)`. Eso supone que entre el primer y el último uplink capturados no falta ninguno «por
  los bordes», lo cual no siempre es cierto.
- El **denominador de verdad** está en la **microSD**: la sonda registra *todos* los
  uplinks que envió, **incluidos los que fallaron antes de salir por la antena** (que son
  parte del denominador). Ese registro no viaja por radio; solo se lee al volver.
- El **PDR definitivo** sale de cruzar las dos fuentes con `analisis/cruzar.py`, que une
  el log de la microSD con el del servidor por `fCnt` (ver §13 del manual). Hasta
  entonces, cualquier PDR es una estimación.

> **Regla mental:** la app es una **herramienta online** para operar y vigilar; la
> **microSD es el registro de verdad**. Si la app y la microSD no coinciden, gana la
> microSD. Y una corrida sin microSD hay que repetirla entera, tenga la app los números
> que tenga.

Lo mismo vale para el **CSV que descargas de la app**: contiene lo que **llegó al
servidor** para esa sesión, que es un subconjunto de lo que la sonda envió. Es cómodo
para una ojeada rápida, pero el análisis formal parte de los CSV de la microSD.

---

## 5. Las pantallas, una por una

La app tiene tres pantallas de uso continuo (barra inferior), tres de consulta (menú `≡`
arriba a la izquierda) y una de ayuda (botón `?` arriba a la derecha). Antes de todas
ellas está la pantalla de configuración.

**En la barra superior hay dos indicadores**, y conviene no confundirlos porque
responden a preguntas distintas:

| Indicador | Qué mira | Estados |
|---|---|---|
| **Bluetooth** (izquierda del de red) | El enlace con **la sonda** | **verde `sonda`** = enlace listo · **ámbar `...`** = conectado pero aún no seguro (emparejando o preparándose) · **gris `sin sonda`** = no hay enlace |
| **Red** (`wifi`) | El WebSocket con **el servidor** | conectado / desconectado |

El indicador de Bluetooth **es tocable**: lleva directamente a la pantalla de
Dispositivo. El estado **ámbar** importa más de lo que parece: es justo el momento en
que el selector de corridas sigue bloqueado y todo parece averiado sin estarlo.

**Pantalla de configuración** (la primera vez, y desde ajustes). Pides dos cosas: la
**URL base** (`https://campo.pi-caro.org`) y el **token**. Se guardan en el teléfono. Sin
una configuración válida, la app te lleva aquí y no deja pasar: sin token no hay puerta
(ver §7).

### ① Panel — la pantalla donde vives durante la corrida

Es el equivalente en la app del OLED de la sonda. Contiene:

- El **selector de corridas** (las mismas opciones que el menú del device: URBANO /
  TERRAZA / CERRO16, cada una en Clase A o C, y desde la app 2.1 **VUELO**, sólo en
  Clase A — ver §5.1). Una fila por escenario; VUELO ocupa su fila entera.
- El **botón circular grande**, que cambia de color y de función según el estado de la
  sesión:
  - **verde — Arrancar** cuando no hay sesión activa (pone el perfil, abre la sesión
    **y arranca la sonda por Bluetooth**);
  - **rojo — Abortar** mientras se captura (para la sonda por Bluetooth si puede, y
    cierra la sesión como ABORTADA; lo capturado se conserva);
  - **azul — Finalizado** cuando la corrida llegó a su fin.
- Debajo del botón grande, **sólo mientras se captura**, un segundo botón de texto:
  **Marcar finalizada**. No es un sinónimo de Abortar — cierra la corrida **dando por
  buenos los datos capturados**, y de paso resuelve el caso en el que la sonda ya
  terminó sola pero el servidor no llegó a enterarse (ver más abajo).
- El bloque **Sonda (BLE)**: qué dice la sonda de sí misma —situación (`SIN_ENLACE`,
  `CONFIG`, `ESPERANDO_ENLACE`, `CORRIENDO`, `FINALIZADA`, `ABORTADA`, `EMPAREJADO`),
  corrida, resultado del último comando y su dirección— y su **enlace LoRa** como
  indicador aparte («uniendo…» / «unida»). Es el **acuse de recibo**: no dice «mandé la
  orden», dice «la sonda está corriendo lo que pediste». *(El antiguo `UNIENDO` se
  retiró: la sonda ya no se cuelga uniéndose — ver §3.3.)*
- Los **datos en vivo** que también enseña el OLED: progreso **TX n/300**, **RSSI**,
  **SNR**, **GPS/satélites**, **batería** (con `--` si es desconocida, nunca un 100
  inventado — ver A-08 de la bitácora) y el **último downlink** (`DL ping #n`).
- Las **bandas de aviso**: desajuste sonda↔sesión y sonda parada (§3.2), desajuste de
  fPort (§3.1) y los avisos de enlace.

El estado de la sesión se actualiza por **WebSocket**; el de la sonda, por **Bluetooth**.
Son dos flujos independientes: la app puede quedarse sin red y seguir viendo la sonda, o
al revés. (El microservicio expone además el envío de pings de latencia; su control vive
en el Panel, junto al último downlink.)

#### El gate: sin sonda no se elige, pero Abortar siempre se puede

**El selector de corridas y el botón Arrancar están deshabilitados si la sonda no está
lista por Bluetooth.** No es una molestia: es la regla que hace que la v2 funcione. Las
dos mitades se fijan **juntas o ninguna** — si se pudiera elegir sin la sonda, volvería
a existir la posibilidad de que la app y la sonda corran cosas distintas, que es
precisamente lo que se eliminó.

> **El gate es el enlace *Bluetooth*, no el LoRa.** Desde la corrección del arranque en
> segundo plano, tener o no enlace LoRa **ya no bloquea el selector**: se puede arrancar
> con la sonda aún uniéndose, y la corrida quedará **esperando enlace** (§3.3). El enlace
> LoRa se muestra como **indicador aparte** en el bloque Sonda (BLE) —«uniendo…» /
> «unida»—, no como un candado. Lo que sí gatea, como siempre, es que exista **enlace BLE
> seguro** con la sonda: sin él no se fijan las dos mitades juntas.

**Cuando el gate está cerrado, la app dice por qué**, justo debajo del selector: que la
sonda no está conectada, que está emparejándose, que está en modo emparejar, o que el
firmware BLE no es compatible. Un control en gris **sin explicación**, en campo, se
interpreta como que la app está rota — y entonces el operador reinicia cosas que
funcionaban.

> ⚠️ **El botón Abortar NO depende del Bluetooth. Nunca.** Está disponible siempre,
> incluso con el Bluetooth del teléfono apagado. La razón es dura: si el enlace se cae
> con una corrida en marcha, **tiene que poder cerrarse la sesión de captura del
> servidor**. Lo contrario dejaría sesiones abiertas sin forma de cerrarlas desde el
> cerro. Cuando se pulsa Abortar sin enlace, la app lo advierte: se cerrará la sesión en
> el servidor, y la sonda hay que pararla a mano con la pulsación larga.

También hay un aviso **previo** al arranque que no cierra el gate pero evita sorpresas:
si la sonda ya está corriendo otra cosa, la app lo dice antes de que pulses —arrancar se
rechazaría: hay que abortar primero—. Y si la sonda aún no tiene enlace LoRa, te avisa de
que la corrida quedará **esperando enlace** en vez de arrancar en el acto — no es un
error, es lo previsto (§3.3).

#### Si el Bluetooth se cae con una corrida en marcha

Sale un aviso que dice, literalmente, que **la corrida sigue en la sonda**. Es
importante que lo diga con esas palabras: la sonda es autónoma y no se ha parado, sólo
se ha perdido el control remoto. La app reconecta sola —con reintentos cada vez más
espaciados— y al recobrar el enlace **vuelve a leer el estado de la sonda; no reenvía
nada**. Nunca reenvía un comando pendiente: mientras el enlace estaba caído la corrida
siguió, y un comando repetido «por si acaso» podría abortar una corrida que iba bien o
arrancar dos veces la misma. La verdad está en la sonda; al reconectar, el trabajo de la
app es leerla.

#### Marcar finalizada: sonda primero, servidor siempre

Es el botón que hay que usar cuando la corrida **terminó** —completa o no— y no encaja
llamarlo un aborto. El caso típico: el PDR que ve el servidor es **estimado** (§4), y si
el real es más bajo, la sesión puede no llegar nunca a contar los 300 uplinks que hacen
falta para autofinalizarse aunque la sonda ya lleve un rato en `FINALIZADO`. También sirve
para cortar una corrida antes de los 300 uplinks porque ya hay dato suficiente.

Al pulsarlo, la app mira primero el estado BLE de la sonda:

- **Si la sonda ya terminó sola** (`FINALIZADA`), no hay nada que preguntar: se cierra la
  sesión sin mandarle ningún comando. Es el caso para el que nació el botón.
- **Si la sonda sigue `CORRIENDO` o `ESPERANDO_ENLACE`**, la app pregunta antes de tocar
  nada: *«La sonda sigue corriendo — Vas a dar la corrida por finalizada, pero la sonda
  todavía está transmitiendo. ¿Paro también la sonda?»*, con el botón **Parar y
  finalizar**. Si cancelas, no se cierra nada — ni la sonda ni la sesión.
- **Si confirmas**, la app aplica el mismo criterio que Abortar: **sonda primero, servidor
  siempre**. Manda por Bluetooth el mismo comando de parada que usa Abortar, y **sólo
  después** cierra la sesión como finalizada. Lo urgente es que la sonda deje de
  transmitir, y es lo único que se resuelve sin depender de la red.
- **Si la sonda no confirma la parada** (sin Bluetooth, o rechazo del comando), la sesión
  se cierra igual en el servidor, pero la app lo dice sin rodeos: *«Sesión finalizada,
  pero la sonda NO confirmó la parada… Párala con el botón: pulsación larga.»* Ve a
  pararla a mano.
- Si el cierre de la sesión falla **después** de haber parado la sonda con éxito, queda un
  aviso persistente de que la sesión sigue abierta en el servidor.

> **Hasta este cambio, el botón sólo cerraba la contabilidad del servidor** y confiaba en
> que la sonda se autofinalizara sola a los 300 uplinks. Con el PDR bajo del cerro eso
> falla más de lo que parece: si el servidor recibe menos uplinks de los que la sonda
> envía, nunca llega a contar los 300, así que la sonda se queda transmitiendo sin
> ninguna sesión que la capture — uplinks huérfanos, batería gastada y el `fCnt` de la
> corrida siguiente contaminado. De ahí el cambio (D-63 de la bitácora).

> **Ojo con lo que queda registrado.** Una corrida cerrada así antes de los 300 uplinks
> queda marcada como **finalizada** en el servidor igual que una corrida completa — es
> decir, es una corrida parcial con etiqueta de completa. El análisis la distingue igual,
> porque su recuento de uplinks se queda corto frente al objetivo, pero no basta con mirar
> el estado de la sesión: anótalo en la hoja de campo y trátala como una corrida
> incompleta (D-29 de la bitácora: márcala parcial y repítela).

#### 5.1 La corrida VUELO (app 2.1)

VUELO simula la telemetría de la cápsula durante **55 minutos** desde puntos fijos
(especificación completa en [VUELO-ESPEC.md](VUELO-ESPEC.md)). Es **sólo Clase A**
(perfil `terreno-a`), va por **fPort 17** a DR0/SF10 y es el **modo 6** del menú de la
sonda (0–5 no cambian). En vez de un paquete por minuto con todo, cada minuto la sonda
toma una lectura completa y la manda en una **ráfaga de 3 paquetes**, uno cada 20 s:
**P1** posición, **P2** ambiente y energía, **P3** navegación. La corrida termina con
**55 ráfagas = 165 uplinks**, así que el contador del Panel es **TX n/165**.

Consecuencia para la lectura de la app: **cada uplink trae sólo una parte** de la
lectura. La app muestra cada magnitud con el **último paquete que la trajo** y nunca
pinta un hueco como si fuera un dato (ni un punto en 0,0 en el mapa ni un 0 °C en la
gráfica):

- en el **Panel** aparece el bloque **«Vuelo · última lectura»**: la ráfaga en curso
  y el paquete que se acaba de oír (p. ej. `ráfaga 12/55 · P2`), las ráfagas
  completas/parciales/perdidas si el servidor las calcula (si no, un recuento local
  marcado «(app)»), y posición, altitud, temperatura, presión, humedad, velocidad
  vertical, rumbo, velocidad y HDOP. A la derecha de cada valor, el paquete y la ráfaga
  de los que viene (`P1 r12`): si se pierden todos los P1, se ve que la posición se ha
  quedado vieja. Lo que nunca llegó se muestra como `--`.
- el bloque OLED toma batería y GPS del último P2/P1 que los trajo (las métricas del
  servidor copian el último uplink, que dos de cada tres veces no los lleva).
- el **Mapa** sólo usa los P1 con fix; el último punto es la última posición conocida.
- **Gráficos** añade altitud (P1), temperatura, presión y humedad (P2) y velocidad
  vertical (P3), cada serie con sólo los paquetes que traen esa magnitud.

Los **pings** se mantienen (1/min, fPort 98): en VUELO miden si la cápsula **recibe
órdenes** a esa distancia. Un firmware de la sonda anterior a VUELO rechaza el modo 6, y
la app lo dice así («el firmware de la sonda no conoce la corrida VUELO»).

### ② Mapa

Los puntos GPS de la sesión (la activa, o la que elijas en Sesiones), con el **marcador
del gateway** para ver la geometría del enlace. Usa OpenStreetMap, **sin API key**. Si no
hay tiles descargados (en el cerro puede no haber datos), no se rompe: degrada a un lienzo
con los puntos y una escala. Recuerda que sin **fix de GPS** los puntos no tienen posición
(la corrida sigue siendo válida para el PDR, pero pierdes el track).

### ③ Gráficos

La evolución de la corrida: **PDR estimado**, **RSSI/SNR/batería** contra el tiempo, y un
resumen numérico. Para leer de un vistazo si el enlace se degrada, si la batería aguanta,
si el PDR se sostiene.

### ④ Sesiones (menú `≡`)

La lista de todas las sesiones, la más reciente primero, cada una con su resumen
(`run_label`, recibidos, PDR est., RSSI/SNR medios, distancia máxima al gateway,
duración, estado). Tocar una abre su **detalle**, desde donde puedes:

- **Descargar el CSV** (`GET /sessions/{id}/csv`), que se guarda o se comparte con el
  nombre de la corrida (`20260814-CERRO16-C.csv`).
- **Ver mapa** / **Ver gráficos** (*replay*): redibuja el mapa y las gráficas de esa
  sesión con los datos que tiene el servidor. Es una **foto fija** —no sigue en
  directo—, así que puedes revisar una corrida antigua mientras otra captura en
  segundo plano sin que se mezclen. El botón de refrescar vuelve a pedir los datos.
- **Descartar sesión**: la borra del **servidor** (uplinks y resumen), con un diálogo
  que avisa de que es **irreversible**. Sirve para no acumular sesiones de prueba. No
  se puede borrar una sesión en captura: primero se aborta. Las copias de CSV que ya
  descargaste al teléfono son ficheros tuyos aparte y no se tocan.

> **Dónde vive todo:** las sesiones están en el **servidor** (la SQLite del
> microservicio), no en el teléfono. Por eso las ves iguales desde cualquier móvil con
> el mismo token, y por eso *descartar* libera espacio del servidor.

### ⑤ Dispositivo (BLE) (menú `≡`) — **nueva en la v2**

Es la pantalla del **enlace con la sonda**. Se llega desde el menú `≡` → *Dispositivo
(BLE)*, o tocando el indicador de Bluetooth de la barra superior. Se usa poco: una vez
emparejado, el enlace se restablece solo y aquí no hay nada que hacer. Se entra cuando
algo no va, o para emparejar un móvil nuevo.

Contiene:

- **El estado del enlace**, en una línea que dice en qué punto está: *Sin conectar*,
  *Buscando la sonda…*, *Conectando…*, *Emparejando…*, *Preparando el enlace…*, *Enlace
  listo*, *Reconectando…*, *Firmware incompatible*, *Apartada: sonda emparejando* o *Sin
  enlace*. Que sean tantos estados es a propósito: «no funciona» no se puede arreglar,
  «está emparejándose» sí.
- **Detalles del enlace**: dirección de la sonda, si el enlace es **seguro** (cifrado y
  autenticado), la versión del protocolo que habla el firmware —y si es incompatible— y
  el número de reintentos de reconexión.
- **El estado de la sonda**: situación, corrida y resultado del último comando. Lo mismo
  que el bloque del Panel, para poder mirarlo sin salir de aquí.
- **Buscar sonda**, que escanea 10 s y lista lo que encuentre; **Reconectar** y
  **Desconectar**.
- **Instrucciones de emparejado**, incluida la advertencia de que el código lo muestra
  la sonda y se teclea en el diálogo de Android.

**Sólo aparecen los equipos que anuncian el servicio `PICARO-CAMPO`**: la app filtra por
servicio, no por nombre, así que no hay que bucear en una lista de cascos y relojes. Y
si **otro móvil está conectado a la sonda**, ésta deja de anunciarse y **no aparecerá en
el escaneo** — sólo admite una conexión a la vez. No es un fallo, y es la explicación
más frecuente de «no la encuentro».

#### El emparejamiento, desde la app

La app **no pide ni guarda ningún código**. Cuando conecta con una sonda con la que aún
no está emparejada, solicita el emparejamiento y aparece un bloque que dice qué hacer:
mirar la pantalla de la sonda, que muestra un código de 6 dígitos, y teclearlo en el
diálogo que abre **Android** encima de la app. No hay que entrar en los Ajustes de
Android en ningún momento, y al aceptar el diálogo se vuelve a la app sin pasos
adicionales.

> ⚠️ **El código de la sonda no existe hasta que la app pide emparejarse.** Al poner la
> sonda en modo emparejar no se ve ningún número, y eso es correcto. El número aparece a
> la vez que el diálogo de Android. Está explicado paso a paso, con las pantallas, en
> **§6.1 del [manual de campo](MANUAL-DE-CAMPO.md)** — que es también donde está el
> procedimiento para **reemparejar**, que exige borrar **por los dos lados**.

**Si el emparejamiento falla**, la app dice las dos causas posibles a la vez, porque
desde el teléfono se parecen: que la sonda no esté en modo emparejar (hace falta una
**pulsación larga desde su menú**) o que el número se tecleara mal. La que desambigua es
**la pantalla de la sonda**, que dice `codigo mal tecleado` cuando fue eso.

**Qué NO hay que hacer nunca:** guardar el código, apuntarlo o reutilizarlo. Cambia en
cada emparejamiento, se usa una vez y se tira. Las llaves las custodia **Android** por
un lado y **la sonda** por otro; la app no guarda ningún secreto. De ahí una propiedad
muy práctica: **reinstalar la app o reiniciar la sonda no obliga a emparejar de nuevo**.

### ⑥ Acerca de (menú `≡`)

«PiCARO — App de campo»: **herramienta open source** para las pruebas de campo del
proyecto radiosonda PiCARO (LoRaWAN Clase A vs C). Autoría **© 2026 Omar Velázquez —
Licencia MIT**, correo **ovelazquezj@gmail.com**, la versión de la app y el icono.
No es una campaña cerrada: es la herramienta con la que se hacen las pruebas.

### ⑦ Ayuda (botón `?`)

Los pasos de sincronización sonda↔app, resumidos de este documento y del manual:
1) el perfil lo pone Arrancar; 2) en la sonda, elige la misma corrida y doble-pulsa;
3) Arranca en la app; 4) comprueba que no hay aviso de desajuste. Es la chuleta para el
cerro, cuando no apetece leer más.

> ⚠️ **Pendiente:** esta pantalla **sigue describiendo el flujo de la v1**, en el que
> había que elegir la corrida también en la sonda. Sigue siendo correcta como respaldo
> —es literalmente lo que se hace sin Bluetooth—, pero no es ya el camino normal. Hasta
> que se actualice, el orden bueno es el de §3 de este documento.

---

## 6. Puesta en marcha (a alto nivel)

Los comandos exactos viven en los README de cada parte; aquí solo el mapa, para no
duplicar (y desincronizar) instrucciones.

**El microservicio y su despliegue.** Es un contenedor FastAPI que se une a la red Docker
`picaro` (la de ChirpStack) y escucha en un puerto **interno**, sin publicarlo al host.
Caddy —el mismo del stack de ChirpStack— gana un bloque para `campo.pi-caro.org` que hace
de pasarela (también para el WebSocket) y emite el certificado TLS él solo. **No se abre
ningún puerto nuevo** en el firewall del servidor en la nube (ver §7 y la decisión de despliegue
«Opción A»). La configuración va por variables de entorno (token, credenciales MQTT,
token de la API de ChirpStack, coordenadas del gateway…). Detalle y comandos:
[`microservicio/README.md`](../microservicio/README.md) y
[`despliegue-campo/README.md`](../despliegue-campo/README.md). El despliegue real lo hace
el coordinador por SSH, con autorización.

**La app.** Es un proyecto Flutter que se entrega como **código fuente**; se compila con
`flutter pub get` + `flutter build apk` y se instala el APK en el teléfono. En el primer
arranque, la pantalla de configuración pide URL y token. Detalle, dependencias y pasos:
[`app/README.md`](../app/README.md).

---

## 7. Seguridad — el token es toda la puerta

El microservicio está **expuesto a internet** (por diseño: tiene que ser alcanzable desde
el cerro). Su única defensa es un **token Bearer** compartido, servido siempre **sobre
TLS**:

- Todas las rutas REST salvo `/health` exigen la cabecera `Authorization: Bearer <token>`;
  sin ella, **401**. El WebSocket lleva el token en la URL (`…/ws?token=…`), porque los
  clientes WS no siempre permiten cabeceras; sin token válido, se cierra al instante.
- **TLS no es opcional.** El token viaja en cada petición; sin cifrado iría en claro y
  cualquiera en la ruta podría leerlo y quedarse con la llave. Caddy termina el TLS con un
  certificado que emite y renueva solo.
- **Ese token es toda la puerta.** No hay usuarios ni contraseñas: un único secreto
  compartido, suficiente para un servicio de campaña operado por una persona, **siempre
  que no se comparta ni se suba al repositorio**. En la app se guarda en el teléfono
  (pantalla de configuración); en el servidor es la variable `CAMPO_TOKEN`. Si se
  filtrase, se rota: se cambia la variable, se reinicia el contenedor y se reconfigura la
  app.

> **No metas el token en git.** Ni en el código de la app, ni en ficheros de ejemplo con
> el valor real. Lo que entra al historial se queda para siempre (misma regla que las
> credenciales del README raíz).

---

## 8. Qué hacer si…

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Arranqué la sesión y no llega nada (`TX 0/300`, sin aviso) | La sonda no está transmitiendo | Arranca la sonda: menú → elige la corrida → **doble pulsación**. La app no enciende la radio |
| **Banda roja: aviso de desajuste de fPort** | La sonda transmite una corrida **distinta** de la que arrancaste en la app | **Para.** Cuadra escenario **y** clase en sonda y app; reinicia la corrida (§3.1) |
| Todo llega pero los pings de Clase C tardan segundos | El perfil del servidor no es el de Clase C | Reabre la sesión con la clase correcta (Arrancar la fija); si persiste, revísalo. La corrida así **no** mide latencia de Clase C |
| «Sin conexión» / la app no actualiza | No hay cobertura de datos donde estás | Es esperable en algunos puntos. La sonda sigue midiendo y la **microSD** lo guarda todo; vigila cuando recuperes señal. La app es online, no imprescindible |
| **401 / token inválido** | Token mal escrito, caducado o rotado | Revisa el token en la pantalla de configuración; pídele al coordinador el vigente |
| El WebSocket se cae una y otra vez | Token del WS incorrecto, o red inestable | Verifica el token; si la red va y viene, la app reintenta sola al recuperar señal |
| **503** al Arrancar o al hacer ping | El MQTT o la API de ChirpStack no responden | El servidor no pudo poner el perfil o encolar el ping. Reintenta; si sigue, avisa al coordinador (puede ser el servidor) |
| 409 al Arrancar | Ya hay una sesión activa | Solo puede haber una a la vez. Finaliza o aborta la anterior antes de abrir otra |
| 409 «clase desajustada» al Arrancar | La clase pedida no coincide con la que ChirpStack tiene congelada del último join (D-60) | Normal si cambiaste de clase (A↔C): la app hace un re-join automático por Bluetooth y reintenta sola (D-62, §3). Si avisa que el firmware no soporta re-join, apaga y enciende la sonda |
| El PDR de la app no cuadra con el análisis | La app da un PDR **estimado**; el real sale de la microSD | Normal. Gana la microSD y `cruzar.py` (§4) |
| La batería sale como `--` | El medidor de la sonda no respondió | El porcentaje no está disponible; usa los mV. No es un fallo de la app (A-08) |
| El mapa sale vacío o sin fondo | Sin tiles descargados o sin fix de GPS | Sin datos, degrada a puntos sobre lienzo; sin fix, no hay posición. La corrida sigue siendo válida para el PDR |
| La sonda ya está `FINALIZADA` pero la sesión sigue `capturando` | El PDR real fue más bajo que el estimado por el servidor; nunca llegó a contar los 300 uplinks | Pulsa **Marcar finalizada** en el Panel. La app ve que la sonda ya terminó y cierra la sesión sin mandarle nada (§5, ① Panel) |
| «Sesión finalizada, pero la sonda NO confirmó la parada» | Pulsaste **Marcar finalizada** con la sonda corriendo, sin Bluetooth o con la sonda rechazando el comando | La sesión ya se cerró en el servidor. Ve a la sonda y párala con el respaldo de siempre: **pulsación larga** |

### …con el Bluetooth

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| **El selector de corridas está en gris** | La sonda no está lista por Bluetooth (el gate es el BLE, no el LoRa) | Lee el motivo que aparece debajo del selector y actúa. **Abortar sigue habilitado**: eso no es un fallo, es la regla |
| «Esperando enlace» tras pulsar Arrancar | Arrancaste sin enlace LoRa; la sonda lo adquiere por detrás | Normal (§3.3). La corrida arranca sola al unir. Abortar sigue disponible si no quieres esperar |
| El indicador de la barra está **ámbar** y no pasa a verde | Conectado pero el enlace aún no es seguro | Espera unos segundos. Si se queda ahí, entra en *Dispositivo (BLE)* y mira el estado del enlace |
| «No se encuentra la sonda» al escanear | Sonda apagada, fuera de alcance, o **otro móvil conectado a ella** | La sonda sólo admite una conexión y deja de anunciarse mientras la tiene otro. Desconecta el otro móvil |
| **La pantalla de la sonda no muestra ningún código** | **Ninguna: es normal.** El código no existe hasta que la app pide emparejarse | Conecta desde la app; el número sale a la vez que el diálogo de Android (§6.1 del manual) |
| «No se pudo emparejar» | Falta la pulsación larga en la sonda, **o** el código se tecleó mal | Comprueba que la sonda pone `EMPAREJA LA APP` y reintenta. La pantalla de la sonda dice cuál de las dos fue |
| El emparejamiento falla una y otra vez | Se borró **un solo lado** de las llaves | Borra los dos: «Olvidar dispositivo» en Ajustes de Android **y** doble pulsación en la sonda (§6.2 del manual) |
| «La sonda está en modo emparejar» y la app se desconecta | La sonda abrió su ventana de emparejamiento y este móvil se apartó para dejar sitio | Es correcto. Cuando acabes con el otro móvil, pulsa *Reconectar* |
| «Firmware BLE incompatible» | La app y el firmware hablan versiones distintas del protocolo | La app **no enviará ningún comando** a propósito. Actualiza el firmware o la app |
| «La sonda está corriendo …: abórtala primero» | Pediste arrancar con una corrida ya en marcha | Aborta y vuelve a arrancar. No se cambia de modo a mitad de corrida: mezclaría dos escenarios en el mismo fichero |
| «Hay que volver a emparejar» | La sonda olvidó este móvil (doble pulsación, o desalojado al emparejar un cuarto) | Olvida en Ajustes de Android y empareja de nuevo |
| **«Bluetooth caído» con una corrida en marcha** | Se perdió el enlace | **La corrida NO se para.** La app reconecta sola y vuelve a leer el estado; nunca reenvía el comando. Abortar sigue disponible |
| Aviso «la sonda ya no está corriendo pero la sesión sigue abierta» | Se abortó o terminó en la sonda y la sesión quedó viva | Pulsa **Cerrar sesión** en el propio aviso (§3.2) |
| ¿El Bluetooth interfiere con la radio LoRa? | — | **No.** Son chips distintos y está medido: la cadencia de uplinks es idéntica con el enlace conectado |
| Con la T3, el selector solo deja VUELO A | Es la única corrida de esa sonda (D-65) | Correcto. Para las demás, usa la T-Beam |
| «Sin permiso de ubicación» o «La ubicación del teléfono está apagada» | La T3 no tiene GPS y la distancia sale del teléfono | Activa la ubicación y concede el permiso a la app (Ajustes de Android → Apps → picaro_campo → Permisos). La corrida sigue igual; lo único que falta es la distancia |
| Distancia «--» con la ubicación activa | Aún no hay fix, o el último paquete está a más de 5 min de la última posición | Espera al primer fix al aire libre. Si persiste, revisa que el teléfono no esté ahorrando batería con la app en segundo plano |

---

## Apéndice — las corridas y sus fPort

| Escenario | Clase | fPort | Perfil que pone Arrancar | DR/SF |
|---|---|---|---|---|
| URBANO  | A | 11 | `terreno-a` | DR1/SF9  |
| URBANO  | C | 12 | `terreno-c` | DR1/SF9  |
| TERRAZA | A | 13 | `terreno-a` | DR3/SF7  |
| TERRAZA | C | 14 | `terreno-c` | DR3/SF7  |
| CERRO16 | A | 15 | `terreno-a` | DR0/SF10 |
| CERRO16 | C | 16 | `terreno-c` | DR0/SF10 |
| VUELO   | A | 17 | `terreno-a` | DR0/SF10 · ráfagas de 3, 165 uplinks |

El orden de la tabla es el **modo** del menú / BLE: 0 = URBANO-A … 5 = CERRO16-C,
**6 = VUELO-A**. VUELO no tiene Clase C.

Downlinks: **fPort 98** = ping de latencia. La app nunca envía el fPort 99 (corte).

Es la misma tabla que el menú de la sonda y que el anexo del manual de campo: si la app y
la sonda no coinciden en esta tabla, salta el aviso de desajuste.
