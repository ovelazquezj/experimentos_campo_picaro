/**
 * ============================================================================
 *  pmu_t3.h  -  Energia y LED de la T3 v1.6.1 (sin PMU)
 * ============================================================================
 *
 *  La T3 no tiene gestor de energia: el radio tiene alimentacion fija y la
 *  carga la hace un TP4054 sin interfaz digital. Este modulo ofrece la MISMA
 *  API que pmu_axp2101.h del firmware de la T-Beam, para que app_main y
 *  telemetry no cambien:
 *    - bateria: tension por ADC (IO35, divisor 1:2). El porcentaje no existe
 *      (no hay gauge): devuelve 0xFF, que el decoder y la app ya tratan como
 *      "no disponible".
 *    - USB y carga: no se pueden leer; devuelven false.
 *    - LED: el verde de IO25 hace de CHGLED (parpadea <=> menu).
 * ============================================================================
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Configura el ADC de bateria y el LED. */
esp_err_t pmu_init(void);

/* Bateria: milivoltios (0 si no hay lectura) y porcentaje (0xFF = sin gauge). */
uint16_t pmu_battery_mv(void);
uint8_t  pmu_battery_percent(void);

/* No medibles en esta placa: siempre false. */
bool pmu_usb_present(void);
bool pmu_charging(void);

/* LED de modo: un solo significado, igual que en la T-Beam.
 *      parpadeando  ->  modo configuracion (menu). NO esta midiendo.
 *      apagado      ->  cualquier otra cosa: join, corrida o corrida terminada. */
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
