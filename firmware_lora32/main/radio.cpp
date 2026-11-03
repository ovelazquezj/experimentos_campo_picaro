/**
 * ============================================================================
 *  radio.cpp  -  Instancia del SX1276 (RadioLib) para la T3 v1.6.1
 * ============================================================================
 *
 *  Diferencias con el SX1262 de la T-Beam Supreme:
 *    - Sin TCXO ni BUSY: el SX127x usa cristal y no tiene linea de ocupado.
 *    - La IRQ principal es DIO0 (TxDone/RxDone); DIO1 da el RxTimeout que
 *      RadioLib necesita para cerrar las ventanas RX1/RX2.
 *    - Salida por PA_BOOST (la unica cableada en el modulo de LILYGO).
 * ============================================================================
 */
#include "radio.h"
#include "board_pins.h"
#include "esp_log.h"

static const char *TAG = "radio";

/* El radio va en VSPI (SPI3_HOST); HSPI (SPI2_HOST) queda para la microSD. */
static EspHal *hal = new EspHal(LORA_SCK_PIN, LORA_MISO_PIN, LORA_MOSI_PIN, SPI3_HOST);

/* Radio SX1276:  Module(hal, NSS, DIO0, RST, DIO1). */
SX1276 radio = new Module(hal, LORA_CS_PIN, LORA_DIO0_PIN, LORA_RST_PIN, LORA_DIO1_PIN);

int picaro_radio_begin_test(void)
{
    ESP_LOGI(TAG, "SX1276.begin(): 915 MHz, BW125, SF9 ...");

    /* Firma: begin(freq, bw, sf, cr, syncWord, power, preamble, gain).
     * Los parametros de modulacion dan igual: el nodo LoRaWAN los reescribe
     * en cada TX/RX. Esto solo comprueba que el chip responde por SPI. */
    int state = radio.begin(915.0,                                 /* MHz     */
                            125.0,                                 /* kHz BW  */
                            9,                                     /* SF      */
                            7,                                     /* CR 4/7  */
                            RADIOLIB_SX127X_SYNC_WORD,
                            10,                                    /* dBm     */
                            8,                                     /* preamb. */
                            0);                                    /* AGC     */
    return state;
}
