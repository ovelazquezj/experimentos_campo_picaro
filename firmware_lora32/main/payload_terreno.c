/**
 * ============================================================================
 *  payload_terreno.c  -  Empaquetado little-endian y calculo de airtime
 * ============================================================================
 */
#include "payload_terreno.h"

#include <math.h>
#include <string.h>

/* Escritura explicita byte a byte en vez de volcar una struct packed: deja el
 * orden de bytes a la vista y no depende del endianness del compilador, que es
 * justo lo que hay que garantizar para que el codec decodifique bien. */
static void put_i32le(uint8_t *p, int32_t v)
{
    p[0] = (uint8_t)(v      ); p[1] = (uint8_t)(v >>  8);
    p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}
static void put_i16le(uint8_t *p, int16_t v)
{
    p[0] = (uint8_t)(v); p[1] = (uint8_t)(v >> 8);
}
static void put_u16le(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v); p[1] = (uint8_t)(v >> 8);
}

/* Satura antes de convertir: una lectura absurda de un sensor no debe
 * envolverse y aparecer como un valor plausible pero falso en el analisis. */
static int32_t sat_i32(double v)
{
    if (v >  2147483647.0) return  2147483647;
    if (v < -2147483648.0) return -2147483648;
    return (int32_t)v;
}
static int16_t sat_i16(double v)
{
    if (v >  32767.0) return  32767;
    if (v < -32768.0) return -32768;
    return (int16_t)v;
}
static int8_t sat_i8(double v)
{
    if (v >  127.0) return  127;
    if (v < -128.0) return -128;
    return (int8_t)v;
}

size_t payload_terreno_build(uint8_t *buf, size_t bufsz,
                             bool fix, double lat, double lon,
                             float alt_m, float temp_c,
                             bool extendido, uint16_t batt_mv, uint8_t batt_pct)
{
    const size_t n = extendido ? 14u : 11u;
    if (!buf || bufsz < n) return 0;

    /* Sin fix, lat/lon van a cero: el codec lo detecta y las anula en vez de
     * dibujar un punto en el golfo de Guinea. */
    put_i32le(&buf[0], fix ? sat_i32(lat * 1e7) : 0);
    put_i32le(&buf[4], fix ? sat_i32(lon * 1e7) : 0);
    put_i16le(&buf[8], isfinite(alt_m) ? sat_i16(alt_m) : 0);
    buf[10] = (uint8_t)(isfinite(temp_c) ? sat_i8((double)temp_c * 2.0) : 0);

    if (extendido) {
        put_u16le(&buf[11], batt_mv);
        /* 0xFF = "desconocido". El PMU devuelve ese valor cuando falla la
         * lectura del gauge; se propaga tal cual en lugar de saturarlo a 100,
         * que mandaria un fallo de lectura disfrazado de "bateria llena" y sin
         * ningun aviso. El codec lo traduce a null. Los milivoltios (bytes
         * 11-12) son lectura directa del ADC y siguen siendo fiables. */
        buf[13] = (batt_pct > 100) ? 0xFF : batt_pct;
    }
    return n;
}

/* --- VUELO --------------------------------------------------------------- */

#define NA_I16  ((int16_t)0x7FFF)
#define NA_U16  ((uint16_t)0xFFFF)
#define NA_U8   ((uint8_t)0xFF)

/* Satura por debajo del sentinela: un valor real nunca debe confundirse con
 * "no disponible" (0x7FFF / 0xFFFF / 0xFF). */
static int16_t  q_i16(double v) { int16_t r = sat_i16(v); return r == NA_I16 ? NA_I16 - 1 : r; }
static uint16_t q_u16(double v)
{
    if (!(v > 0.0)) return 0;
    if (v >= 65534.0) return 65534;
    return (uint16_t)(v + 0.5);
}
static uint8_t  q_u8(double v)
{
    if (!(v > 0.0)) return 0;
    if (v >= 254.0) return 254;
    return (uint8_t)(v + 0.5);
}

size_t payload_vuelo_build(uint8_t *buf, size_t bufsz, uint8_t tipo,
                           uint8_t rafaga, const vuelo_lectura_t *l)
{
    if (!buf || !l || bufsz < VUELO_PAYLOAD_LEN) return 0;
    if (tipo < VUELO_P_POSICION || tipo > VUELO_P_NAVEGACION) return 0;

    memset(buf, 0, VUELO_PAYLOAD_LEN);
    buf[0] = (uint8_t)((tipo << 6) | (rafaga & 0x3F));

    switch (tipo) {
    case VUELO_P_POSICION:
        /* Altitud sin signo hasta 65 km: la capsula no baja del nivel del mar
         * y un int16 se quedaba en 32 km. Sin fix, todo a "no disponible". */
        put_i32le(&buf[1], l->fix ? sat_i32(l->lat * 1e7) : 0);
        put_i32le(&buf[5], l->fix ? sat_i32(l->lon * 1e7) : 0);
        put_u16le(&buf[9], (l->fix && isfinite(l->alt_m)) ? q_u16(l->alt_m) : NA_U16);
        break;

    case VUELO_P_AMBIENTE: {
        /* int16 x100 llega a -327 C: cubre de sobra los -60 C de la tropopausa,
         * que el int8 x2 del payload clasico (-64 C) rozaba. */
        bool bme = l->bme_ok;
        put_i16le(&buf[1], (bme && isfinite(l->temp_c)) ? q_i16((double)l->temp_c * 100.0) : NA_I16);
        put_u16le(&buf[3], (bme && isfinite(l->press_hpa)) ? q_u16((double)l->press_hpa * 10.0) : NA_U16);
        buf[5] = (bme && isfinite(l->hum_pct)) ? q_u8(l->hum_pct) : NA_U8;
        put_u16le(&buf[6], l->batt_mv);
        buf[8] = (l->batt_pct > 100) ? NA_U8 : l->batt_pct;   /* 0xFF = gauge ilegible */
        buf[9] = l->sats;
        buf[10] = (uint8_t)((l->fix        ? 0x01 : 0) | (l->usb    ? 0x02 : 0) |
                            (l->charging   ? 0x04 : 0) | (l->gps_active ? 0x08 : 0) |
                            (l->mag_ok     ? 0x10 : 0) | (bme       ? 0x20 : 0));
        break;
    }

    case VUELO_P_NAVEGACION:
        put_u16le(&buf[1], l->fix ? q_u16((double)l->speed_kmh * 10.0) : NA_U16);
        if (l->mag_ok && isfinite(l->heading_deg)) {
            double h = fmod((double)l->heading_deg, 360.0);
            if (h < 0) h += 360.0;
            uint16_t d = (uint16_t)(h * 10.0 + 0.5);
            put_u16le(&buf[3], d >= 3600 ? 0 : d);
        } else {
            put_u16le(&buf[3], NA_U16);
        }
        buf[5] = (l->fix && isfinite(l->hdop)) ? q_u8((double)l->hdop * 10.0) : NA_U8;
        put_i16le(&buf[6], (l->vspeed_ok && isfinite(l->vspeed_ms))
                           ? q_i16((double)l->vspeed_ms * 10.0) : NA_I16);
        buf[8]  = (uint8_t)(l->uptime_s);
        buf[9]  = (uint8_t)(l->uptime_s >> 8);
        buf[10] = (uint8_t)(l->uptime_s >> 16);
        break;
    }
    return VUELO_PAYLOAD_LEN;
}

uint32_t payload_terreno_airtime_ms(uint8_t sf, size_t payload_len)
{
    /* Time on Air de LoRa (Semtech AN1200.13), BW125, CR 4/5, cabecera
     * explicita, preambulo de 8 simbolos, CRC activo.
     *   PL = payload de aplicacion + 13 bytes de cabecera LoRaWAN
     *   DE = optimizacion de baja tasa, obligatoria en SF11/SF12 y usada
     *        tambien en SF10 a 125 kHz. */
    if (sf < 7 || sf > 12) return 0;

    const double bw   = 125000.0;
    const double tsym = (double)(1u << sf) / bw;            /* s */
    /* La optimizacion de baja tasa (DE) es obligatoria SOLO cuando el simbolo
     * dura mas de 16 ms, es decir SF11 y SF12 a 125 kHz. A SF10 el simbolo dura
     * 8,19 ms y NO se aplica. Activarla de mas inflaba el airtime de SF10 de
     * 371 a 453 ms y hacia parecer que el payload de 11 bytes excedia el limite
     * de dwell de US915, cuando en realidad cabe. */
    const int    de   = (tsym > 0.016) ? 1 : 0;
    const int    cr   = 1;                                   /* 4/5 */
    const int    pl   = (int)payload_len + 13;

    double num = 8.0 * pl - 4.0 * sf + 28 + 16;
    double den = 4.0 * (sf - 2 * de);
    double np  = ceil(num / den) * (cr + 4);
    if (np < 0) np = 0;

    const double t_pre  = (8 + 4.25) * tsym;
    const double t_pay  = (8 + np) * tsym;
    return (uint32_t)((t_pre + t_pay) * 1000.0 + 0.5);
}
