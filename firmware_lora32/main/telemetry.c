/**
 * ============================================================================
 *  telemetry.c  -  Recoleccion de la T3 v1.6.1: bateria real, sensores SIMULADOS
 * ============================================================================
 *  La T3 no tiene GPS, BME280 ni magnetometro. Sus magnitudes salen de
 *  simulacion.h, con las banderas a true, para que la corrida VUELO mande los
 *  mismos P1/P2/P3 que la T-Beam y la app los pinte igual. Bateria y uptime
 *  son lecturas reales. La struct y el runlog son los de la T-Beam.
 * ============================================================================
 */
#include "telemetry.h"
#include "pmu_t3.h"
#include "simulacion.h"

#include <math.h>
#include <string.h>
#include <stdio.h>

void telemetry_collect(telemetry_t *t, uint32_t uptime_s)
{
    memset(t, 0, sizeof(*t));
    t->uptime_s = uptime_s;
    t->batt_mv  = pmu_battery_mv();
    t->batt_pct = pmu_battery_percent();
    t->usb      = pmu_usb_present();
    t->charging = pmu_charging();

    /* --- Simulado (simulacion.h) --- */
    const float fase = 2.0f * (float)M_PI * (float)uptime_s / SIM_PERIODO_S;

    t->gps_active = true;
    t->gps_fix    = true;
    t->lat        = SIM_LAT;
    t->lon        = SIM_LON;
    t->alt_m      = SIM_ALT_M;
    t->sats       = SIM_SATS;
    t->hdop       = SIM_HDOP;
    t->speed_kmh  = SIM_VEL_KMH;

    t->bme_ok     = true;
    t->temp_c     = SIM_TEMP_C   + SIM_TEMP_AMP * sinf(fase);
    t->press_hpa  = SIM_PRES_HPA + SIM_PRES_AMP * cosf(fase);
    t->hum_pct    = SIM_HUM_PCT  + SIM_HUM_AMP  * sinf(fase + 1.0f);

    t->mag_ok      = true;
    t->heading_deg = SIM_RUMBO_DEG;
}

void telemetry_csv_header(char *out, size_t n)
{
    snprintf(out, n,
        "uptime_s,gps_active,gps_fix,lat,lon,alt_m,sats,hdop,speed_kmh,"
        "batt_mv,batt_pct,usb,charging,temp_c,press_hpa,hum_pct,"
        "imu_ok,ax,ay,az,gx,gy,gz,mag_ok,heading_deg");
}

void telemetry_csv_line(const telemetry_t *t, char *out, size_t n)
{
    snprintf(out, n,
        "%lu,%d,%d,%.6f,%.6f,%.1f,%u,%.1f,%.1f,"
        "%u,%u,%d,%d,%.2f,%.1f,%.1f,"
        "%d,%.3f,%.3f,%.3f,%.2f,%.2f,%.2f,%d,%.1f",
        (unsigned long)t->uptime_s, t->gps_active ? 1 : 0, t->gps_fix ? 1 : 0,
        t->lat, t->lon, t->alt_m,
        t->sats, t->hdop, t->speed_kmh,
        t->batt_mv, t->batt_pct, t->usb ? 1 : 0, t->charging ? 1 : 0,
        t->temp_c, t->press_hpa, t->hum_pct,
        t->imu_ok ? 1 : 0, t->ax, t->ay, t->az, t->gx, t->gy, t->gz,
        t->mag_ok ? 1 : 0, t->heading_deg);
}
