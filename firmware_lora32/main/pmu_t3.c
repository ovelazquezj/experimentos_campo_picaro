/**
 * ============================================================================
 *  pmu_t3.c  -  Bateria por ADC y LED de modo de la T3 v1.6.1
 * ============================================================================
 *
 *  ADC1 canal 7 (IO35) con atenuacion de 12 dB y calibracion por ajuste
 *  lineal (la que tiene el ESP32 clasico, a partir del eFuse Vref). ADC1 y no
 *  ADC2 a proposito: el ADC2 lo usa la radio WiFi/BT y con el BLE encendido
 *  sus lecturas fallan.
 *
 *  El parpadeo del LED lo hace un esp_timer, no una tarea: cuesta un
 *  callback cada medio periodo y nada de pila.
 * ============================================================================
 */
#include "pmu_t3.h"
#include "board_pins.h"

#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_timer.h"
#include "esp_log.h"

static const char *TAG = "pmu_t3";

#define BATT_ADC_UNIT     ADC_UNIT_1
#define BATT_ADC_CANAL    ADC_CHANNEL_7      /* IO35 */
#define BATT_MUESTRAS     16

static adc_oneshot_unit_handle_t s_adc;
static adc_cali_handle_t         s_cali;
static bool                      s_adc_ok;

static esp_timer_handle_t s_led_timer;
static bool               s_led_on;

static void led_set(bool on)
{
    s_led_on = on;
    gpio_set_level((gpio_num_t)LED_PIN, on ? 1 : 0);
}

static void led_tick(void *arg)
{
    (void)arg;
    led_set(!s_led_on);
}

esp_err_t pmu_init(void)
{
    /* --- LED ------------------------------------------------------------- */
    gpio_config_t led = {
        .pin_bit_mask = 1ULL << LED_PIN,
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    gpio_config(&led);
    led_set(false);

    const esp_timer_create_args_t ta = { .callback = led_tick, .name = "led" };
    esp_timer_create(&ta, &s_led_timer);

    /* --- ADC de bateria -------------------------------------------------- */
    adc_oneshot_unit_init_cfg_t ucfg = { .unit_id = BATT_ADC_UNIT };
    esp_err_t e = adc_oneshot_new_unit(&ucfg, &s_adc);
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "ADC1 no arranco (%s): sin lectura de bateria", esp_err_to_name(e));
        return e;
    }
    adc_oneshot_chan_cfg_t ccfg = {
        .atten    = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    adc_oneshot_config_channel(s_adc, BATT_ADC_CANAL, &ccfg);

    adc_cali_line_fitting_config_t cal = {
        .unit_id  = BATT_ADC_UNIT,
        .atten    = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    if (adc_cali_create_scheme_line_fitting(&cal, &s_cali) != ESP_OK) {
        ESP_LOGW(TAG, "sin calibracion de ADC: la tension sera aproximada");
        s_cali = NULL;
    }
    s_adc_ok = true;
    ESP_LOGI(TAG, "bateria por ADC en IO%d: %u mV", BATT_ADC_PIN, (unsigned)pmu_battery_mv());
    return ESP_OK;
}

uint16_t pmu_battery_mv(void)
{
    if (!s_adc_ok) return 0;
    int suma = 0, n = 0;
    for (int i = 0; i < BATT_MUESTRAS; i++) {
        int raw;
        if (adc_oneshot_read(s_adc, BATT_ADC_CANAL, &raw) != ESP_OK) continue;
        int mv;
        if (s_cali && adc_cali_raw_to_voltage(s_cali, raw, &mv) == ESP_OK)
            suma += mv;
        else
            suma += raw * 3300 / 4095;   /* sin calibrar: aproximado */
        n++;
    }
    if (!n) return 0;
    return (uint16_t)(suma / n * BATT_DIVISOR);
}

uint8_t pmu_battery_percent(void) { return 0xFF; }
bool    pmu_usb_present(void)     { return false; }
bool    pmu_charging(void)        { return false; }

void pmu_led_modo(pmu_led_t modo)
{
    if (!s_led_timer) return;
    esp_timer_stop(s_led_timer);   /* ESP_ERR_INVALID_STATE si no corria: da igual */
    switch (modo) {
    case PMU_LED_1HZ:  led_set(true); esp_timer_start_periodic(s_led_timer, 500000); break;
    case PMU_LED_4HZ:  led_set(true); esp_timer_start_periodic(s_led_timer, 125000); break;
    case PMU_LED_FIJO: led_set(true);  break;
    case PMU_LED_APAGADO:
    default:           led_set(false); break;
    }
}
