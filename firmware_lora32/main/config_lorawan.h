/**
 * ============================================================================
 *  config_lorawan.h  -  CONFIGURACION LoRaWAN de la sonda T3 v1.6.1 (LoRa32)
 * ============================================================================
 *
 *  Copia de config_lorawan.h de la T-Beam con UNA diferencia: las tres
 *  credenciales OTAA NO estan aqui sino en credenciales_lora32.h, que esta en
 *  .gitignore. La AppKey de esta sonda es la real de ChirpStack y lo que
 *  entra al historial de git se queda alli para siempre.
 *
 *      cp main/credenciales_lora32.example.h main/credenciales_lora32.h
 *      # y rellena DEV_EUI, JOIN_EUI y APP_KEY tal cual estan en ChirpStack
 * ============================================================================
 */
#pragma once

#include <stdint.h>

#if __has_include("credenciales_lora32.h")
#  include "credenciales_lora32.h"
#else
#  error "Falta main/credenciales_lora32.h: copia credenciales_lora32.example.h y rellenalo"
#endif

/* ---------------------------------------------------------------------------
 * Parametros de red (NO cambiar salvo que sepas lo que haces).
 *   - Region US915 + sub-banda 2 (canales 8-15): el default de ChirpStack y
 *     del gateway del curso. RadioLib enumera las sub-bandas desde 1, asi que
 *     "sub-banda 2" se pide como selectSubBand(2).
 *   - LoRaWAN 1.0.x -> solo se usa AppKey.
 * ------------------------------------------------------------------------- */
#define PICARO_SUBBAND            2       /* US915 FSB2 (canales 8-15) */

/* Datarate de uplink inicial (US915): DR3 = SF7/BW125, admite hasta 242 bytes.
 * IMPORTANTE: en DR0 (SF10) solo caben ~11 bytes y el payload de 19 bytes NO
 * cabe (error PACKET_TOO_LONG / -4). Cerca del gateway, DR3 va perfecto; con
 * ADR activo la red lo ajustara. Sube el SF (baja el DR) solo si te alejas. */
#define PICARO_UPLINK_DR          3
#define PICARO_UPLINK_FPORT       10      /* puerto de aplicacion del uplink  */
#define PICARO_UPLINK_INTERVAL_S  30      /* cada cuantos segundos se transmite */

/* Auto re-join: si el enlace se pierde (no llega ACK del gateway) durante este
 * numero de ciclos seguidos, el firmware intenta un JOIN nuevo por su cuenta.
 * 0 = desactivado (solo se une al arrancar). */
#define PICARO_REJOIN_AFTER       5

/* Poner en 1 UNA vez si ChirpStack rechaza el join por "DevNonce ya usado":
 * borra los nonces guardados en NVS, arranca, y regresa a 0 y reflashea. */
#define PICARO_RESET_NONCES       0

/* Si 1: IGNORA la sesion guardada y fuerza un JOIN OTAA REAL por aire en cada
 * arranque. Asi "JOIN OK" solo aparece si de verdad hubo JoinAccept (necesita
 * gateway en rango). Con 0 (por defecto) se reusa la sesion de NVS si existe,
 * pero el firmware NO la marca como enlace confirmado hasta recibir un ACK. */
#define PICARO_FORCE_FRESH_JOIN   1

/* SOLO BANCO (A-11). Si 1: antes del primer join fuerza en RadioLib el estado que
 * deja una JoinAccept ajena (rev = 1). Ese JoinRequest debe salir con MIC
 * invalido y el siguiente, tras rearmar el nodo, unir normal. Siempre 0 en campo. */
#ifndef PICARO_TEST_REV_CORRUPTO
#define PICARO_TEST_REV_CORRUPTO  0
#endif
