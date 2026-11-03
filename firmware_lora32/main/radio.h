/**
 * ============================================================================
 *  radio.h  -  Radio SX1276 de la T3 v1.6.1 via RadioLib + EspHal
 * ============================================================================
 *
 *  Constructores usados:
 *    EspHal(sck, miso, mosi, host)          -> bus SPI del radio (VSPI)
 *    SX1276 = new Module(hal, NSS, DIO0, RST, DIO1)
 * ============================================================================
 */
#pragma once

#include <RadioLib.h>
#include "esp_hal.h"    /* HAL de RadioLib sobre spi_master */

/* Objeto global del radio (definido en radio.cpp). */
extern SX1276 radio;

/* Arranque del radio. Devuelve el codigo de RadioLib: 0 == RADIOLIB_ERR_NONE. */
int picaro_radio_begin_test(void);
