/**
 * ============================================================================
 *  board_pins.h  -  Pinout de la LILYGO T3 v1.6.1 (ESP32-PICO-D4 + SX1276)
 * ============================================================================
 *
 *  Fuente autoritativa: esquematico oficial T3_V1.6.1.pdf
 *  (LilyGo-LoRa-Series/schematic) y utilities.h de los ejemplos de LILYGO,
 *  macro T3_V1_6_SX1276. NO cambies estos pines salvo que cambies de placa.
 *
 *  Dos buses SPI independientes, uno por periferico:
 *    - SPI del RADIO (SX1276) -> VSPI (SPI3_HOST) .. SCK 5 / MISO 19 / MOSI 27
 *    - SPI de la microSD      -> HSPI (SPI2_HOST) .. SCK 14 / MISO 2 / MOSI 15
 *    - I2C (OLED SSD1306) ......................... SDA 21 / SCL 22
 *
 *  Lo que esta placa NO tiene, frente a la T-Beam Supreme: PMU (no hay rieles
 *  que encender: el radio tiene alimentacion fija), GPS, BME280,
 *  magnetometro, IMU ni RTC. Y tampoco tiene BOTON DE USUARIO: el unico
 *  pulsador es RESET. Ver BOOT_BUTTON_PIN.
 * ============================================================================
 */
#pragma once

/* ---------------------------------------------------------------------------
 * RADIO LoRa SX1276 (modulo "TTGO LORA", hoja 2 del esquematico)
 *   DIO0 = IO26 (TxDone/RxDone: es la IRQ que usa RadioLib)
 *   DIO1 = IO33 (RxTimeout: RadioLib la necesita para las ventanas RX)
 *   DIO2 = IO32 (no se usa)
 *  Sin TCXO: cristal normal, por eso no hay tension de TCXO en radio.begin().
 * ------------------------------------------------------------------------- */
#define LORA_SCK_PIN     5
#define LORA_MISO_PIN   19
#define LORA_MOSI_PIN   27
#define LORA_CS_PIN     18   /* NSS */
#define LORA_RST_PIN    23
#define LORA_DIO0_PIN   26
#define LORA_DIO1_PIN   33
#define LORA_DIO2_PIN   32

/* ---------------------------------------------------------------------------
 * microSD (hoja 1, bloque SD CARD). GPIO2 es pin de arranque: la placa ya
 * lleva su pull-up y no hay que tocarlo.
 * ------------------------------------------------------------------------- */
#define SD_MOSI_PIN     15
#define SD_MISO_PIN      2
#define SD_SCK_PIN      14
#define SDCARD_CS_PIN   13

/* ---------------------------------------------------------------------------
 * I2C -> solo el OLED SSD1306 0,96" @0x3C
 * ------------------------------------------------------------------------- */
#define I2C0_SDA_PIN    21
#define I2C0_SCL_PIN    22
#define I2C_ADDR_OLED   0x3C

/* ---------------------------------------------------------------------------
 * LED verde (IO25, activo en alto). Hace el papel del CHGLED de la T-Beam:
 * parpadea <=> estas en el menu.
 * ------------------------------------------------------------------------- */
#define LED_PIN         25

/* ---------------------------------------------------------------------------
 * Bateria: VBAT -> divisor 100k/100k (R42/R43) -> IO35 (ADC1 canal 7).
 * La tension real es el doble de la que ve el ADC.
 * ------------------------------------------------------------------------- */
#define BATT_ADC_PIN    35
#define BATT_DIVISOR    2

/* ---------------------------------------------------------------------------
 * Boton. La T3 v1.6.1 NO tiene boton de usuario (el unico pulsador es RESET)
 * y esta sonda se opera SOLO desde la app. El gesto del boton se desactiva
 * entero: IO0 va al circuito de auto-reset del puente USB-serie (CH9102 en
 * esta unidad), y abrir o cerrar el monitor serie mueve DTR/RTS, lo que se
 * leeria como pulsaciones fantasma (una "larga" abortaria una corrida). BOOT_BUTTON_PIN se conserva porque
 * escenarios.c, copia del de la T-Beam, lo nombra.
 * ------------------------------------------------------------------------- */
#define BOTON_HABILITADO 0
#define BOOT_BUTTON_PIN  0
