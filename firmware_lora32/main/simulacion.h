/**
 * ============================================================================
 *  simulacion.h  -  Sensores SIMULADOS de la sonda T3 (LoRa32)
 * ============================================================================
 *
 *  La T3 no tiene GPS, BME280 ni magnetometro. Para que la corrida VUELO
 *  transmita lo mismo que la T-Beam (P1 posicion, P2 ambiente, P3 navegacion,
 *  11 bytes cada uno, docs/VUELO-ESPEC.md), telemetry_collect() rellena esas
 *  magnitudes con los valores de aqui. La bateria y el uptime SI son reales.
 *
 *  POSICION: es la del punto de prueba, fija. El microservicio calcula con
 *  ella la distancia a SU gateway (GW_LAT/GW_LON del servidor), asi que pon
 *  aqui las coordenadas reales del sitio donde se coloca la sonda.
 *
 *  Ambiente: oscila suavemente con el tiempo (periodo de unos minutos) para
 *  que en la app se vea cambiar de una rafaga a otra; no representa nada.
 * ============================================================================
 */
#pragma once

/* --- Posicion fija del punto de prueba ----------------------------------- */
/* Por defecto: Pabellon de Arteaga, Ags. (aproximado, centro del municipio).
 * CAMBIAR por el punto real antes de la prueba. */
#define SIM_LAT            22.14780
#define SIM_LON          (-102.27660)
#define SIM_ALT_M        2010.0f
#define SIM_SATS            9
#define SIM_HDOP            0.9f

/* --- Ambiente (valor central y amplitud de la oscilacion) --------------- */
#define SIM_TEMP_C         25.0f
#define SIM_TEMP_AMP        1.5f
#define SIM_PRES_HPA      800.0f
#define SIM_PRES_AMP        0.8f
#define SIM_HUM_PCT        50.0f
#define SIM_HUM_AMP         5.0f

/* --- Navegacion ----------------------------------------------------------- */
#define SIM_RUMBO_DEG       0.0f   /* sonda quieta: rumbo y velocidad fijos */
#define SIM_VEL_KMH         0.0f

/* Periodo de la oscilacion del ambiente, en segundos. */
#define SIM_PERIODO_S     300.0f
