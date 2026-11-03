# experimentos_campo_picaro

Campaña de pruebas de terreno de la radiosonda PICARO sobre LoRaWAN: mide
**cobertura**, **latencia de downlink** y **autonomía** comparando **Clase A
frente a Clase C** en tres escenarios de propagación.

Repositorio **privado**. Contiene los datos reales del despliegue, pero **no las
credenciales**: esas van fuera del control de versiones (ver más abajo).

---

## El experimento en una tabla

| Escenario | Emplazamiento | DR / SF | Intervalo | Distancia | fPort A / C |
|---|---|---|---|---|---|
| `URBANO` | vehículo a 30–40 km/h | DR1 / SF9 | 8 s | hasta 5 km | 11 / 12 |
| `TERRAZA` | terraza del piso 5, exterior | DR3 / SF7 | 8 s | 2,74 km | 13 / 14 |
| `CERRO16` | cima del Cerro del Muerto | DR0 / SF10 | 8 s | **15,27 km** ¹ | 15 / 16 |

¹ Medida con las coordenadas reales el 2026-08-29 (antes se manejaban 16,35 km,
de un punto de cima aproximado). El nombre del escenario y los `fPort` no cambian.

Seis corridas (3 escenarios × 2 clases), **300 uplinks cada una** (~40 min), del 14 al 16
de agosto de 2026. ADR desactivado y DR fijo en todas.

El `fPort` identifica la corrida, así que cada paquete queda autoetiquetado sin
gastar un solo byte de payload.

**Cómo se opera.** La corrida se elige **una sola vez, en la app**, y esa acción fija a
la vez las dos mitades: el device profile del servidor (por internet, vía el
microservicio) y la sonda (por **Bluetooth**). Con eso el desajuste entre lo que mide la
sonda y lo que espera el servidor deja de poder originarse en un error humano de
selección. El **botón de la sonda se conserva como respaldo completo**: sin app, sin
teléfono y sin cobertura se navega, se arranca y se aborta igual que siempre.

---

## Por dónde empezar

| Documento | Para qué |
|---|---|
| [`docs/MANUAL-DE-CAMPO.md`](docs/MANUAL-DE-CAMPO.md) | **El manual operativo: lo que se lleva al cerro.** Cómo se opera la sonda —desde la app o con el botón—, cómo se empareja el móvil y qué debe verse en pantalla en cada momento. Autosuficiente: no hace falta consultar nada más para ejecutar una corrida |
| [`docs/APP-CAMPO.md`](docs/APP-CAMPO.md) | Guía de la app de campo: las pantallas, la sesión de captura y el enlace con la sonda |
| [`docs/PRUEBA-RF-BANCO.md`](docs/PRUEBA-RF-BANCO.md) | Diagnóstico de RF del 2026-08-29: **el equipo está sano** (PDR 97-100 % en las cuatro pruebas) y el enlace al cerro sale viable. Incluye el procedimiento de medida por si hay que repetirlo |
| [`docs/EXPERIMENTO.md`](docs/EXPERIMENTO.md) | Protocolo formal: hipótesis, variables, diseño y plan de análisis. Base de la memoria técnica |
| [`docs/GUIA-LABORATORIO.md`](docs/GUIA-LABORATORIO.md) | Guía práctica de campo, paso a paso |
| [`docs/CUESTIONARIO-PREVIO.md`](docs/CUESTIONARIO-PREVIO.md) | Datos del emplazamiento y decisiones cerradas |
| [`BITACORA.md`](BITACORA.md) | Qué se decidió, qué se descartó y **por qué** |

---

## Estructura

```
firmware/     ESP-IDF v5.x + RadioLib para T-Beam Supreme (ESP32-S3 + SX1262).
              Un solo binario cubre las 6 corridas: se eligen desde la app por
              BLE, o con el botón como respaldo. Ver main/escenarios.h y
              main/ble_control.h
firmware_lora32/ segunda sonda: LILYGO T3 v1.6.1 (ESP32 + SX1276). Solo
              VUELO-A, con GPS y sensores simulados; misma app y mismo
              microservicio (sonda lora32). Ver su README
app/          app de campo (Flutter, APK): sesión de captura en el servidor y
              control de la sonda por BLE, con una sola selección
microservicio/ FastAPI junto a ChirpStack: ingesta MQTT, sesiones, perfil y pings
mapa-publico/ mapa en vivo de la red en https://pi-caro.org: datos y señal de
              los nodos del tenant con tag publico=true. Ver su README
dashboard/    consola de escritorio (tkinter) que consume los uplinks por MQTT
              y los guarda en SQLite
analisis/     cruzar.py une el log del dispositivo con el del servidor por fCnt
              y calcula PDR; graficas.py produce las figuras
campo/        hoja-de-campo.html — registro de campo para el móvil, offline
servidor/     pinger.py — lanza los downlinks de latencia desde el servidor
datos/        resultados de las corridas (ver abajo)
docs/         manual de campo, protocolo, guía y cuestionario
```

---

## Credenciales

**No están en el repositorio**, ni siendo privado: lo que entra al historial de
git se queda para siempre y un repo privado puede ganar colaboradores.

```bash
cp firmware/credentials.example.json firmware/credentials.json
cp dashboard/config.example.json     dashboard/config.json
cp firmware/main/credenciales_lorawan.example.h firmware/main/credenciales_lorawan.h
cp firmware_lora32/main/credenciales_lora32.example.h firmware_lora32/main/credenciales_lora32.h
cp analisis/sitios_privados.example.json analisis/sitios_privados.json
# y rellena los valores reales
```

Todos están en `.gitignore`. Los valores reales viven en el servidor y en la
documentación interna de infraestructura, fuera de este repositorio.

---

## Datos de las corridas

Los datos de cada corrida tienen **dos mitades**, que se cruzan para obtener el
PDR (recibidos ÷ enviados). Viven bajo `analisis/`, que es de donde los leen los
scripts:

```
analisis/datos_sd/    CSV de la microSD  → lo ENVIADO (el denominador del PDR)
analisis/datos_app/   CSV descargados de la app → lo RECIBIDO (RSSI/SNR/gateway)
analisis/resultados/  salida de cruzar.py y graficas.py (cruces, resumen, figuras)
```

`cruzar.py` cruza ambas mitades por fPort + ventana temporal; sin la de la
microSD el PDR es solo estimado (ver `analisis/README.md`).

**Los crudos no se publican.** Llevan trazas GPS en torno al laboratorio y EUIs
reales, así que se quedan en local (están en `.gitignore`; cada carpeta conserva
un `LEEME.md`). El dataset público, anonimizado, está en `reporte/datos/`. Los
scripts leen la posición del laboratorio de `analisis/sitios_privados.json`
(fuera de git; plantilla en `analisis/sitios_privados.example.json`).

Convención de nombres: `<FECHA>-<ESCENARIO>-<CLASE>[-<INTENTO>]`, por ejemplo
`20260814-CERRO16-C.csv`. Si una corrida se aborta con el botón y se repite el
mismo día, el firmware abre `20260814-CERRO16-C-2.csv` en vez de reutilizar el
fichero: los intentos son corridas distintas y no deben mezclarse.

---

## Estado

- [x] Servidor ChirpStack, device profile con Clase C y codec desplegados
- [x] Documentación del experimento y guía de campo
- [x] Firmware sobre la base del ejercicio 09 — **compilado y validado en placa**
- [x] Análisis verificado con datos sintéticos de las 6 corridas
- [x] App de campo + microservicio desplegados y probados en campo (A-07)
- [x] **v2 — control de la sonda por BLE desde la app**, probado en hardware:
      emparejamiento autenticado, coexistencia BLE+LoRa sin jitter y selección
      end-to-end (app → sonda → fPort correcto)
- [x] **Perfil de elevación al cerro contra Fresnel** (A-03) — despejado en todo
      el trayecto; margen mínimo +23 m en el km 0,34. `analisis/perfil_elevacion.csv`
- [x] **Altitud real del gateway** (A-05) — 1914 msnm medidos, no los 2000 de la
      curva de nivel
- [x] **Serie 1 ejecutada y cruzada** (16–21 ago) — ninguna corrida alcanza el
      PDR objetivo; el diagnóstico de RF posterior descarta avería del equipo
      (`docs/PRUEBA-RF-BANCO.md`)
- [x] Botón, CSV en microSD y Clase C: verificados en campo
- [x] **Mapa público** de la red en https://pi-caro.org (D-66), `mapa-publico/`
- [ ] Dashboard web para operar desde el móvil (A-07)
- [ ] Ensayo de autonomía en banco (no es medible en las corridas de campo, ver Adenda 1)
