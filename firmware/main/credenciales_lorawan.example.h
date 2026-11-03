/**
 * ============================================================================
 *  credenciales_lorawan.example.h  -  Plantilla SIN secretos
 * ============================================================================
 *  Copia este fichero a credenciales_lorawan.h (que esta en .gitignore) y pon
 *  los valores de tu device en ChirpStack. Estos son valores de EJEMPLO.
 *  Los tres van MSB primero, tal cual los muestra la consola de ChirpStack.
 *  En LoRaWAN 1.0.x la AppKey es la "Application key" (nwkKey por REST).
 * ============================================================================
 */
#pragma once

/* 1) DEV_EUI  (8 bytes)  ->  en ChirpStack: "Device EUI" */
#define PICARO_DEV_EUI    0x0011223344550001ULL

/* 2) JOIN_EUI (8 bytes)  ->  en ChirpStack: "Join EUI" (todo ceros es lo comun) */
#define PICARO_JOIN_EUI   0x0000000000000000ULL

/* 3) APP_KEY  (16 bytes) ->  llave SECRETA. No la publiques. */
#define PICARO_APP_KEY    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, \
                            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }
