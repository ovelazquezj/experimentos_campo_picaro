/**
 * ============================================================================
 *  lorawan.h  -  Capa LoRaWAN (OTAA) sobre RadioLib para la Radiosonda PICARO
 * ============================================================================
 *
 *  IMPORTANTE (joins honestos): RadioLib puede "restaurar" una sesion guardada
 *  en NVS SIN contactar la red (devuelve SESSION_RESTORED). Eso NO prueba que
 *  haya gateway en rango. Por eso distinguimos:
 *    - LORAWAN_JOIN_NEW      -> hubo handshake OTAA REAL por aire (JoinAccept).
 *    - LORAWAN_JOIN_RESTORED -> se reuso una sesion de NVS, SIN confirmar enlace.
 *  Y el "enlace confirmado" solo se declara cuando llega un downlink/ACK real
 *  (ver lorawan_send con confirmed=true).
 * ============================================================================
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>   /* size_t en lorawan_tomar_downlink */
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    LORAWAN_JOIN_FAIL = 0,   /* no hay sesion */
    LORAWAN_JOIN_NEW,        /* join OTAA real por aire (confirmado) */
    LORAWAN_JOIN_RESTORED,   /* sesion restaurada de NVS (SIN confirmar) */
} lorawan_join_t;

/* Intenta unir/restaurar. Ver el enum para el significado honesto. */
lorawan_join_t lorawan_join(void);

/* Envia un uplink. Si confirmed=true, exige ACK de la red.
 * Devuelve: <0 error · 0 enviado sin downlink · >0 llego downlink/ACK. */
int lorawan_send(const uint8_t *data, uint8_t len, uint8_t fport, bool confirmed);

/* true si hay una sesion (nueva o restaurada) cargada. */
bool lorawan_is_joined(void);

/* ===========================================================================
 *  C-Fondo: join en segundo plano y arbitrio de la radio
 *  (equipo/DISENO-JOIN-EN-FONDO.md). El join deja de bloquear el arranque: una
 *  tarea lo adquiere por detras mientras la sonda ya es operable.
 * ========================================================================= */

/* Crea el mutex de la radio y lanza la tarea de join en segundo plano. Llamar
 * UNA vez, tras el radio_begin, en lugar del antiguo bucle de JOIN bloqueante. */
void lorawan_iniciar_join_en_fondo(void);

/* true cuando la tarea de join ya adquirio el enlace (y solto la radio). Es la
 * senal que gatea el arranque de una corrida (atomic, semantica acquire).
 * OJO (D-62): desde que existe lorawan_rejoin() ya NO es monotona: un re-join
 * la devuelve a false hasta que el join nuevo complete. */
bool lorawan_esta_unido(void);

/* Re-join por BLE (D-62): descarta la sesion LoRaWAN actual (clearSession de
 * RadioLib + blob de sesion en NVS; los NONCES se conservan, el DevNonce debe
 * seguir creciendo) y relanza el join OTAA en la tarea de fondo (C-Fondo).
 * Garantias:
 *   - El join resultante es un OTAA REAL por aire, como al encender: sin
 *     sesion no hay SESSION_RESTORED posible.
 *   - Nunca hay dos tareas de join ni dos joins concurrentes: si la tarea
 *     sigue viva (SIN_ENLACE), solo se le anota la peticion; si ya murio
 *     (CONFIG), se relanza una. La decision se toma bajo una seccion critica
 *     compartida con la salida de la tarea, asi que la peticion no se pierde
 *     ni en la ventana en que la tarea esta terminando. Llamadas repetidas
 *     colapsan en un unico re-join (idempotente).
 *   - El mutex D-55 se respeta: la sesion se descarta DENTRO de la tarea de
 *     join, con la radio en propiedad; esta funcion no toca la radio.
 * Llamar SOLO desde el menu (CONFIG/SIN_ENLACE), nunca con la radio tomada
 * para una corrida. Tras esto lorawan_esta_unido() vuelve a false; se pone a
 * true cuando el join nuevo complete (el menu publica entonces CONFIG). */
void lorawan_rejoin(void);

/* El bucle toma/suelta la radio alrededor de una corrida. Tomar SOLO tras ver
 * lorawan_esta_unido() (§4.3/§7): en ese punto la tarea de join ya solto y la
 * radio esta libre. Soltar en TODO retorno al menu (incl. la rama abortada); NO
 * soltar entre corridas encadenadas (FIN_ARRANCAR_YA). */
void radio_tomar_para_corrida(void);
void radio_soltar_de_corrida(void);

/* ===========================================================================
 *  Anadidos para el experimento de pruebas de terreno
 * ========================================================================= */

/* Aplica la configuracion de la corrida ACTIVA (la de escenarios.h):
 *   - ADR DESACTIVADO: el experimento exige un datarate fijo y conocido; con
 *     ADR la red lo cambiaria a mitad de corrida y las medidas de cobertura
 *     dejarian de ser comparables entre si.
 *   - Datarate fijo del escenario.
 *   - Clase A o C segun la corrida.
 * Llamar tras el join y despues de cada cambio de corrida por boton. */
void lorawan_aplicar_corrida(void);

/* Ventana por la que llego un downlink. Los valores calcan los codigos que
 * devuelve RadioLib (RADIOLIB_LORAWAN_RX1/RX2/RX_BC = 1/2/3), pero el mapeo se
 * hace explicito en lorawan.cpp: si RadioLib devolviera otra cosa, se registra
 * DESCONOCIDA antes que inventar una ventana. Es la columna `ventana` del
 * _dl.csv, que permite auditar si servidor y sonda coincidian en la clase. */
typedef enum {
    LORAWAN_VENTANA_DESCONOCIDA = 0,
    LORAWAN_VENTANA_RX1 = 1,    /* ventana RX1 de Clase A */
    LORAWAN_VENTANA_RX2 = 2,    /* ventana RX2 de Clase A */
    LORAWAN_VENTANA_RXC = 3,    /* recepcion continua de Clase C */
} lorawan_ventana_t;

/* Ultimo downlink recibido (por ventana RX o, en Clase C, en cualquier
 * momento). Devuelve true si habia uno sin leer y lo copia a los parametros
 * (cualquiera puede ser NULL si no interesa).
 * Consume el evento: la siguiente llamada devuelve false hasta el proximo. */
bool lorawan_tomar_downlink(uint8_t *fport, uint8_t *primer_byte, size_t *len,
                            lorawan_ventana_t *ventana);

/* Sondea downlinks de Clase C fuera de las ventanas RX de un uplink. En Clase A
 * no hace nada. Llamar periodicamente desde el bucle principal: es lo que
 * permite que el comando llegue al instante y no al siguiente uplink, que es
 * justo la ventaja de la Clase C que el experimento mide. */
void lorawan_sondear_clase_c(void);

/* Contador de trama de subida, para cruzar el log del dispositivo con el del
 * servidor. Es la CLAVE DE UNION del analisis. */
uint32_t lorawan_fcnt_up(void);

#ifdef __cplusplus
}
#endif
