# Cuestionario previo — datos que faltan antes de salir a campo

Rellena esto con tu equipo. Las respuestas cierran las cuestiones abiertas
`A-01` a `A-04` de la [bitácora](../BITACORA.md) y se incorporan a
[`EXPERIMENTO.md`](EXPERIMENTO.md).

> **Las secciones 4 y 5 hay que cerrarlas ANTES de la primera corrida.** Fijar un
> umbral de aceptación después de ver los datos invalida el análisis: siempre se
> encuentra un criterio que hace que los resultados "salgan bien".

> ⚠️ **Documento histórico: sus cifras son las de julio de 2026.** Dos se
> midieron después y quedaron corregidas — la distancia al cerro es **15,27 km**
> (no 16,35) y la altitud del gateway **1914 msnm** (no 2000). No se reescriben
> aquí a propósito: este documento registra con qué datos se tomaron las
> decisiones. Las cifras vigentes están en la [bitácora](../BITACORA.md)
> (entrada del 2026-08-29, cierre de A-03 y A-05).

---

## 0. Decisiones ya cerradas (2026-07-19)

| Tema | Decisión |
|---|---|
| Selección de escenario | **Botón físico, en un menú**: pulsación corta cicla las 6 opciones (escenario × clase), doble pulsación **confirma y arranca**, larga vuelve al menú abortando lo que hubiera. Se guarda en NVS al confirmar. **Seleccionar no es arrancar**: navegar el menú no transmite ni reconfigura la radio, así que el arranque se sincroniza con el momento real de la prueba en vez de llenarse de uplinks tomados mientras se coloca la antena |
| OLED | **Sí, permanentemente encendido.** No hay apagado automático: el menú tiene que verse parpadear y la pantalla de `FINALIZADO` tiene que ser legible al llegar a la sonda. Consume ~20–30 mA, pero es una carga idéntica en las seis corridas y **no sesga la comparación A/C**; sí infla el consumo absoluto por encima de la diferencia A/C (~5–10 mA), y por eso la autonomía se mide en banco (Adenda 1) y no en campo |
| Réplicas | **1 por combinación → 6 corridas** |
| **Intervalo de uplink** | **7 s** (esc. 1 y 2) · **8 s** (esc. 3). **No son elegibles:** salen del `rx1_delay = 5 s` del servidor, que no se modifica. El ciclo mínimo en Clase A es ~6,5 s |
| Duración de corrida | **Por número de uplinks: 300** (40 min por corrida, con intervalo de 8 s). Mismo *n* para comparar PDR entre escenarios. Con 600 la campaña serían 7 h de campo |
| **Payload** | **11 bytes** little-endian, **14 con batería** cuando el DR lo permite. DR0/SF10 solo admite 11 B (dwell time de 400 ms), y el escenario del cerro usa DR0 por ser el máximo alcance de US915 |
| **Device y perfiles** | Se **reutiliza** el device `0011223344550001` del ej.09. Se crean **dos device profiles nuevos** (Clase A y Clase C) y se **conmuta** el del device según lo que se ejecute, devolviéndolo al del ej.09 al terminar |
| PDR "cobertura útil" (esc. 1 y 2) | **≥ 80 %** |
| PDR de éxito en el cerro | **≥ 50 %** |
| Control de validez A vs C | **Prueba estadística formal** (chi-cuadrado, α = 0,05) **y además** diferencia > 5 puntos. Se exigen las dos: con *n* = 300 el test detecta como significativas diferencias de 3–4 puntos sin relevancia práctica |
| Fallo de join | **Reintento con backoff** indefinido, registrando el hueco en el log |
| Escenario 1 | **En vehículo a 30–40 km/h** (≈ un punto cada 50 m) |
| Corrida cortada | **Marcar como parcial y repetir**. El firmware guarda el intento cortado en su propio fichero (`...-C-2.csv`) en vez de mezclarlo con la repetición; el análisis los trata como corridas distintas y compara con el más completo |
| Autonomía en Clase C | **Sin umbral de aceptación**: se mide y se reporta, la decisión se toma según la misión |
| Mecanismo de corte | **No existe hardware**: la placa va soldada y no se le añade nada. El firmware no conmuta ningún GPIO; solo se mide la latencia del comando de downlink |

> ⛔ **Regla que manda sobre todo lo demás: la configuración global del servidor
> no se modifica.** Regiones, `rx1_delay`, temporizadores: intactos. Los comparte
> el ejercicio 09 y los equipos del curso. Si un parámetro del experimento no cabe,
> **se ajusta el experimento**. Añadir objetos nuevos (device profiles) sí es
> admisible, porque no altera lo existente.

Decidido sin consulta por ser evidente, corregible si discrepas:

- **Se registran también los uplinks que fallan al transmitir.** Sin ellos el
  denominador del PDR está mal.
- **Modo banco sin fix de GPS** para probar en interiores: envía coordenadas a
  cero y marca `gps_fix = false`. Cuesta poco y evita depender del cielo.

---

## 1. Emplazamiento del gateway (cierra A-01)

El gateway es el extremo bajo del enlace, así que es donde más se pierde.

| # | Pregunta | Respuesta |
|---|---|---|
| 1.1 | Coordenadas exactas del gateway (lat, lon en decimal) | **`21.92, -102.27`** |
| 1.2 | Altitud del terreno en ese punto (msnm) | **2000 m** ⚠️ leído de curva de nivel, **pendiente de verificar** (A-05) |
| 1.3 | Altura de la antena **sobre el suelo** (m) | **15,5 m** |
| 1.4 | ¿Está en azotea, mástil, interior? | Azotea de casa de dos plantas (8 m) + base de tinaco (1,5 m) + mástil (6 m) |
| 1.5 | Modelo y **ganancia** de la antena (dBi) | **Raigen de fibra de vidrio, 5,8 dBi** |
| 1.6 | Longitud y tipo de cable hasta la antena | Coaxial de **90 cm** (~0,3 dB, despreciable) |
| 1.7 | ¿Hay obstáculos en los primeros 500 m hacia el cerro? ¿De qué altura? | *pendiente* |
| 1.8 | ¿Se puede subir la antena si hace falta? ¿Cuánto? | *pendiente* |

> **Por qué 1.6:** a 915 MHz un coaxial fino y largo se come varios dB. Perder
> 3 dB en cable anula un tercio de lo que ganas pasando de SF7 a SF10.

---

## 2. Emplazamiento del cerro (cierra A-03)

| # | Pregunta | Respuesta |
|---|---|---|
| 2.1 | Coordenadas exactas del punto en el cerro | **`21.8741637679742, -102.42482836119612`** (Cerro del Muerto) |
| 2.2 | Altitud del terreno (msnm) | **2400 m** |
| 2.3 | Altura a la que irá la sonda sobre el suelo | **~1,5 m** |
| 2.4 | Distancia real al gateway (km) | **16,35 km** (haversine) |
| 2.5 | ¿Hay vista directa a simple vista? ¿Se ve la ciudad? | *pendiente de confirmar en sitio* |
| 2.6 | Antena de la sonda: ¿la de fábrica o alguna otra? Ganancia | De serie del T-Beam Supreme, ~2 dBi (valor asumido) |

Con 1.1, 1.2, 2.1 y 2.2 calculo el **despeje real de Fresnel** tramo a tramo y te
digo si hace falta subir el gateway y cuánto.

**Ya calculado** con esos datos: el radio de la primera zona de Fresnel es de
**36,6 m en el punto medio** (hay que dejar libre el 60 %, o sea **22,0 m**), pero
solo **7,6 m a 500 m del gateway**. No es altura de antena: es despeje
perpendicular a la línea que une ambos extremos. La tabla completa de altitud
máxima admisible del terreno está en `EXPERIMENTO.md` §9.5.

Queda **A-03**: contrastar esa tabla con el perfil de elevación real en Google
Earth, que a su vez depende de resolver la altitud del gateway (1.2).

---

## 3. Los otros dos escenarios

| # | Pregunta | Respuesta |
|---|---|---|
| 3.1 | Escenario 1 (urbano): ¿ruta fija o recorrido libre? ¿A pie o en vehículo? | **En vehículo** |
| 3.2 | Si es en vehículo, ¿velocidad aproximada? | **30–40 km/h** |
| 3.3 | ¿Radio máximo de alejamiento previsto desde el gateway? | **5 km** en el escenario urbano; después hasta el cerro (16,35 km) |
| 3.4 | Escenario 2: ¿en qué edificio? ¿Coordenadas y altura de la azotea? | **`21.93, -102.30`**, terreno < 1900 m, **terraza del piso 5** (~15 m sobre el suelo), exterior. A 2,74 km del gateway, rumbo 118° (ESE) |
| 3.5 | Escenario 2: ¿estático o moviéndose por la azotea? | **Estático** |

> **Por qué 3.2:** la velocidad afecta al *fading* y al número de muestras por
> unidad de distancia. A 40 km/h con uplinks cada 8 s tienes un punto cada ~89 m.
>
> **Por qué se descartó el piso 7 tras una ventana:** el vidrio introduce una
> atenuación desconocida de entre 3 y 25 dB que contaminaría la comparación de
> RSSI entre escenarios. La terraza del piso 5 cuesta 6 m de altura —irrelevantes
> con 52 dB de margen a 2,74 km— y elimina esa incógnita.

---

## 4. Diseño de las corridas (cierra A-02) — CERRAR ANTES DE EMPEZAR

| # | Pregunta | Propuesta | Respuesta |
|---|---|---|---|
| 4.1 | Duración de cada corrida | 30 min | **Por uplinks: 300** → 35 / 35 / 40 min |
| 4.2 | ¿Réplicas por combinación escenario×clase? | 1 (6 corridas) o 2 (12) | **1 → 6 corridas** |
| 4.3 | Nº mínimo de pings de latencia por corrida | 30 | **30** |
| 4.4 | ¿Se alternan A y C el mismo día? | Sí, obligatorio | **Sí** |
| 4.5 | ¿Misma carga inicial de batería en cada corrida? | Sí, 100 % | **Sí, 100 %** |
| 4.6 | ¿Qué se hace si una corrida se corta a medias? | ¿Repetir o marcar parcial? | **Marcar parcial y repetir** |

> **Por qué 4.4 y 4.5 no son negociables:** si haces la clase A por la mañana y la
> C por la tarde, no puedes distinguir el efecto de la clase del efecto de la
> propagación. Y como la batería cayendo reduce la potencia de transmisión,
> arrancar con cargas distintas confunde autonomía con cobertura.

---

## 5. Criterios de aceptación (cierra A-04) — CERRAR ANTES DE EMPEZAR

| # | Pregunta | Propuesta | Respuesta |
|---|---|---|---|
| 5.1 | PDR mínimo para considerar "cobertura útil" | ≥ 80 % | **≥ 80 %** |
| 5.2 | Escenario 3: ¿qué PDR haría considerar el enlace de 16,35 km un éxito? | ≥ 50 % | **≥ 50 %** |
| 5.3 | Diferencia máxima de PDR entre clase A y C tolerable (control de validez) | ≤ 5 puntos | **χ² α=0,05 Y además Δ > 5 pp** (ambas condiciones) |
| 5.4 | ¿Qué mejora de latencia en clase C haría que valga su coste? | ¿Factor 10? | *pendiente* |
| 5.5 | Reducción de autonomía en clase C que se consideraría inaceptable | ¿> 50 %? | **Sin umbral**: se mide y se reporta |

> **Sobre 5.3:** es el control de validez. La clase no puede afectar físicamente
> al enlace de subida. Si el PDR difiere más de lo tolerado entre A y C en el
> mismo escenario, el problema está en el método, no en el hallazgo.

---

## 6. Logística y seguridad

| # | Pregunta | Respuesta |
|---|---|---|
| 6.1 | ¿Cuántas personas en campo? ¿Quién anota la hoja de registro? | **Dos**: operador y asistente. El **asistente** lleva el registro **desde el móvil** |
| 6.2 | ¿Hay cobertura de datos móviles en el cerro para verificar en vivo? | **Sí**, verificado en la cima del Cerro del Muerto. Aun así el procedimiento no depende de ella |
| 6.3 | ¿Cómo se alimenta la sonda? ¿Batería propia, powerbank? | **Batería** |
| 6.4 | ¿El mecanismo de corte estará montado o se prueba desarmado? | **No hay hardware de corte.** Solo se mide la latencia del comando |
| 6.5 | Fechas previstas de las corridas | **14–16 de agosto de 2026** |
| 6.6 | ¿Alguien vigila el dashboard desde casa durante las pruebas? | *pendiente* |

> **Por qué 6.2:** con conexión puedes abortar y ajustar en el sitio en vez de
> perder el viaje. Pero el procedimiento debe funcionar sin ella: la hoja de campo
> es offline y el OLED es la verificación de última instancia.
>
> **Sobre 6.4:** la placa va soldada y no se le añade hardware, así que ningún
> actuador recibe el comando y el firmware no conmuta ningún GPIO. El comando de
> corte se conserva en el diseño porque es el caso de uso que justifica la Clase C,
> y porque podría montarse hardware más adelante.

---

## 7. Alcance del firmware

| # | Pregunta | Respuesta |
|---|---|---|
| 7.1 | ¿La sonda lleva OLED? ¿Quieres estado en pantalla en campo? | **Sí**, permanentemente encendido (ver §0) |
| 7.2 | ¿El escenario se elige por `#define` y recompilando, o por botón? | **Por botón, en un menú con arranque explícito**, persistido en NVS |
| 7.3 | ¿Qué debe hacer si pierde el join? ¿Reintentar indefinidamente? | **Reintento con backoff** indefinido, registrando el hueco |
| 7.4 | ¿Registrar también los uplinks que fallan al transmitir? | **Sí** — son el denominador del PDR |
| 7.5 | ¿Hace falta modo simulador sin GPS para probar en interiores? | **Sí**, modo banco |

> **Por qué 7.2:** con `#define` hay que reflashear entre corridas, lo que en el
> cerro significa llevar portátil. Un menú manejado con el botón evita ese viaje,
> a cambio de algo más de firmware. El arranque va aparte de la selección
> (doble pulsación) porque elegir y arrancar en el mismo gesto obligaba a tener
> la sonda ya colocada al tocar el botón, y eso en campo no se cumple nunca.
