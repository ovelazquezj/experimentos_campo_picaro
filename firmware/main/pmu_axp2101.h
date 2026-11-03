/**
 * ============================================================================
 *  pmu_axp2101.h  -  Gestor de energia AXP2101 (I2C bus1) del T-Beam Supreme
 * ============================================================================
 *
 *  El AXP2101 es CRITICO y va PRIMERO: sus rieles LDO alimentan al radio, al
 *  GPS, a los sensores y a la microSD. Si no se enciende ALDO3, el SX1262 no
 *  tiene energia y `radio.begin()` falla. Mapeo de rieles del Supreme (3.3V):
 *     ALDO3 -> LoRa (SX1262)     ALDO4 -> GPS (L76K)
 *     ALDO1 / ALDO2 -> sensores / OLED     BLDO1 -> microSD
 *  (tomado del LoRaBoards.cpp oficial de LILYGO, bloque T_BEAM_S3_SUPREME).
 * ============================================================================
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "driver/i2c_master.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Inicializa el bus I2C1, detecta el AXP2101 y enciende los rieles. */
esp_err_t pmu_init(void);

/* Handle del bus I2C1 (PMU + RTC) para que otros drivers (PCF8563) lo reusen. */
i2c_master_bus_handle_t pmu_i2c_bus1(void);

/* true si el AXP2101 respondio en el bus. */
bool pmu_present(void);

/* Bateria: milivolts (0 si no hay) y porcentaje 0..100 (0xFF = desconocido). */
uint16_t pmu_battery_mv(void);
uint8_t  pmu_battery_percent(void);

/* Estado de alimentacion. */
bool pmu_usb_present(void);
bool pmu_charging(void);

/* --- LED de carga (CHGLED del AXP2101) ------------------------------------
 *
 *  Se usa como INDICADOR DE MODO, visible sin mirar la pantalla:
 *
 *      parpadeando  ->  modo configuracion (menu). NO esta midiendo.
 *      apagado      ->  cualquier otra cosa: join, corrida o corrida terminada.
 *
 *  Un solo significado, comprobable de un vistazo y a distancia: si parpadea,
 *  estas configurando; si no, no. Antes quedaba en parpadeo permanente desde el
 *  arranque como senal de "vivo", lo que no distinguia nada.
 *
 *  OJO: poner el LED en control manual le quita el control al cargador, y el
 *  registro persiste con la placa apagada. Es decir, con la sonda apagada y
 *  cargando por USB, el LED muestra lo ultimo que escribio el firmware, NO el
 *  estado de carga. Para saber si carga, mira la tension de bateria al
 *  encender. */
typedef enum {
    PMU_LED_APAGADO = 0,
    PMU_LED_1HZ     = 1,   /* parpadeo lento: modo configuracion */
    PMU_LED_4HZ     = 2,
    PMU_LED_FIJO    = 3,
} pmu_led_t;

void pmu_led_modo(pmu_led_t modo);

#ifdef __cplusplus
}
#endif
