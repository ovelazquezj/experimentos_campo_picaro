/**
 * ============================================================================
 *  sensores_config.h  -  Perifericos de la T3 v1.6.1
 * ============================================================================
 *
 *  La T3 no lleva sensores: GPS, BME280 y magnetometro se SIMULAN (ver
 *  simulacion.h y telemetry.c). Fisicamente solo hay pantalla, microSD y la
 *  lectura de bateria por ADC, que va siempre.
 * ============================================================================
 */
#pragma once

#define USE_OLED        1   /* SSD1306 0,96" @0x3C                    */
#define USE_SDCARD      1   /* log CSV por corrida (denominador del PDR) */
