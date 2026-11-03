/**
 * ============================================================================
 *  gps_ninguno.c  -  La T3 no tiene GPS: implementacion vacia de gps_l76k.h
 * ============================================================================
 *
 *  escenarios.c, runlog y app_main consultan el GPS para la fecha del run_id
 *  y la hora UTC de cada registro. Aqui nunca hay fix ni hora, que es lo que
 *  esos modulos ya saben tratar (run_id "00000000-..." y columna utc vacia):
 *  la referencia temporal de esta sonda la pone el servidor al recibir.
 * ============================================================================
 */
#include "gps_l76k.h"
#include <string.h>

esp_err_t gps_init(void) { return ESP_ERR_NOT_SUPPORTED; }

bool gps_get(gps_fix_t *out)
{
    if (out) memset(out, 0, sizeof(*out));
    return false;
}

bool gps_active(void) { return false; }
