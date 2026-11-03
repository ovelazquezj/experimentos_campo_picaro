/**
 * ============================================================================
 *  credenciales_lora32.example.h  -  Plantilla SIN secretos
 * ============================================================================
 *  Copia este fichero a credenciales_lora32.h (que esta en .gitignore) y pon
 *  los valores del device en ChirpStack (Proyecto PiCARO > aplicacion PiCARO).
 *  Los tres van MSB primero, tal cual los muestra la consola.
 *  En LoRaWAN 1.0.x la AppKey es la "Application key" (nwkKey por REST).
 * ============================================================================
 */
#pragma once

#define PICARO_DEV_EUI    0x0000000000000000ULL
#define PICARO_JOIN_EUI   0x0000000000000000ULL
#define PICARO_APP_KEY    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, \
                            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }
