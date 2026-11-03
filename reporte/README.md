# Reporte de pruebas de terreno · radiosonda PiCARO

Proyecto PiCARO: <https://pi-caro.org>

Campaña de julio a octubre de 2026 del Instituto Tecnológico de Pabellón de Arteaga (ITPA): cobertura LoRaWAN (US915, sub-banda 2) y latencia de downlink en Clase A frente a Clase C, con dos radiosondas PiCARO y tres gateways.

**Empieza por aquí → [REPORTE-PRUEBAS-TERRENO.md](REPORTE-PRUEBAS-TERRENO.md)**

## Contenido

| Ruta | Qué es |
|---|---|
| [`REPORTE-PRUEBAS-TERRENO.md`](REPORTE-PRUEBAS-TERRENO.md) | Reporte final: resumen, diseño, equipos, resultados, lecciones, relación con SatLink 2026, limitaciones, datos y créditos |
| [`borradores/T1-resultados.md`](borradores/T1-resultados.md) | Análisis experimental y estadístico completo (PDR, enlace, downlinks, VUELO) |
| [`borradores/T2-lecciones-tecnicas.md`](borradores/T2-lecciones-tecnicas.md) | Nueve lecciones técnicas (contexto, síntoma, causa, solución, cómo evitarlo) |
| [`borradores/t1_cifras/`](borradores/t1_cifras/) | Tablas CSV con todas las cifras que citan T1 y el reporte |
| [`datos/`](datos/) | CSV anonimizados de entrada y su [diccionario](datos/DICCIONARIO.md) |
| [`scripts/t1_analisis.py`](scripts/t1_analisis.py) | Script de análisis: lee solo `datos/` y regenera figuras y tablas |
| [`figuras/`](figuras/) | Figuras PNG (150 dpi) |

## Figuras

| Archivo | Muestra |
|---|---|
| [`t1_pdr_escenario_clase.png`](figuras/t1_pdr_escenario_clase.png) | PDR por escenario y clase, con IC 95 % de Wilson |
| [`t1_rssi_snr_distancia.png`](figuras/t1_rssi_snr_distancia.png) | RSSI y SNR frente a la distancia, presupuesto y ajuste log-distancia descriptivo |
| [`t1_perfil_fresnel_cerro.png`](figuras/t1_perfil_fresnel_cerro.png) | Despeje de la 1.ª zona de Fresnel por kilómetro hasta el cerro (15,2 km) |
| [`t1_latencia_ping_clase_a.png`](figuras/t1_latencia_ping_clase_a.png) | Latencia estimada del comando en Clase A frente al modelo teórico |
| [`t1_vuelo_t3_sesiones.png`](figuras/t1_vuelo_t3_sesiones.png) | PDR y ráfagas completas de las corridas VUELO |

## Reproducir

Repositorio: <https://github.com/ovelazquezj/experimentos_campo_picaro/tree/main/reporte>

```bash
git clone https://github.com/ovelazquezj/experimentos_campo_picaro.git
cd experimentos_campo_picaro
python -I reporte/scripts/t1_analisis.py
```

Requiere Python 3 con numpy, pandas, scipy y matplotlib. El script es autocontenido: solo lee `datos/`.

Los datos originales de la campaña (sin anonimizar) no se publican porque contienen identificadores de dispositivos e infraestructura. Quien los necesite para investigación puede solicitarlos a través de <https://pi-caro.org>.

## Relacionado

- Reporte del evento SatLink 2026: [REPORTE-SATLINK-2026.md](https://github.com/ovelazquezj/radiosonda_PIcaro/blob/master/docs/reportes/satlink-2026/REPORTE-SATLINK-2026.md)
- Protocolo del experimento: [`../docs/EXPERIMENTO.md`](../docs/EXPERIMENTO.md)

## Licencia

Datos, figuras y textos: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.es). Cita: *Proyecto PiCARO, Instituto Tecnológico de Pabellón de Arteaga (2026). Pruebas de terreno de la radiosonda PiCARO sobre LoRaWAN (US915).*
