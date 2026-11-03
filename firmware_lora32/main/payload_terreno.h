/**
 * ============================================================================
 *  payload_terreno.h  -  Payload binario de 11/14 bytes (pruebas de terreno)
 * ============================================================================
 *
 *  Sustituye al payload de 19 bytes del ejercicio 09. Debe coincidir BYTE A
 *  BYTE con el codec ../decoder.js, ya verificado con vectores de prueba.
 *
 *      [0..3]   int32  lat   grados * 1e7      \
 *      [4..7]   int32  lon   grados * 1e7       |  11 bytes: cabe en DR0/SF10
 *      [8..9]   int16  alt   metros             |
 *      [10]     int8   temp  grados C * 2      /
 *      [11..12] uint16 batt  milivoltios       \  +3 bytes: solo si el DR
 *      [13]     uint8  batt  porcentaje        /  lo admite (SF9 / SF7)
 *
 *  LITTLE-ENDIAN, al reves que el codec del ej.09. No es un capricho: la
 *  struct se envia en crudo y el ESP32 es little-endian.
 *
 *  POR QUE 11 BYTES: en US915, DR0/SF10 —el maximo alcance que permite la
 *  region— limita el payload de aplicacion a 11 bytes por el dwell time de
 *  400 ms. Con 14 bytes el airtime sube a ~412 ms y lo excede. Por eso en el
 *  escenario del cerro la bateria no viaja por aire y se queda en el log de la
 *  microSD.
 * ============================================================================
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Construye el payload en buf.
 *   fix        false -> lat/lon van a cero y el codec marca gps_fix=false
 *   extendido  true  -> anade bateria (14 bytes); false -> 11 bytes
 * Devuelve el numero de bytes escritos, o 0 si buf es demasiado pequeno. */
size_t payload_terreno_build(uint8_t *buf, size_t bufsz,
                             bool fix, double lat, double lon,
                             float alt_m, float temp_c,
                             bool extendido, uint16_t batt_mv, uint8_t batt_pct);

/* --- VUELO (D-64): una lectura repartida en 3 paquetes de 11 bytes ---------
 * Formato completo y sentinelas en docs/VUELO-ESPEC.md; el codec (decoder.js,
 * fPort 17) lo sigue byte a byte. Byte 0 = tipo << 6 | (rafaga & 0x3F). */
#define VUELO_PAYLOAD_LEN   11u
#define VUELO_P_POSICION    1u
#define VUELO_P_AMBIENTE    2u
#define VUELO_P_NAVEGACION  3u

typedef struct {
    bool     fix;       double lat, lon; float alt_m;
    uint8_t  sats;      float hdop, speed_kmh;
    bool     gps_active;
    bool     bme_ok;    float temp_c, press_hpa, hum_pct;
    uint16_t batt_mv;   uint8_t batt_pct; bool usb, charging;
    bool     mag_ok;    float heading_deg;
    bool     vspeed_ok; float vspeed_ms;   /* dAlt/dt entre rafagas */
    uint32_t uptime_s;
} vuelo_lectura_t;

/* Construye el paquete `tipo` (VUELO_P_*) de la rafaga `rafaga`. Devuelve 11, o
 * 0 si buf es pequeno o el tipo no existe. */
size_t payload_vuelo_build(uint8_t *buf, size_t bufsz, uint8_t tipo,
                           uint8_t rafaga, const vuelo_lectura_t *l);

/* Airtime LoRa en milisegundos, calculado analiticamente.
 * Se calcula en vez de leerlo del modem para no depender del estado en que
 * sendReceive() lo haya dejado, y para poder registrarlo aunque el TX falle. */
uint32_t payload_terreno_airtime_ms(uint8_t sf, size_t payload_len);

#ifdef __cplusplus
}
#endif
