/**
 * ============================================================================
 *  runlog.h  -  Log CSV por corrida en la microSD
 * ============================================================================
 *
 *  Envuelve el sdcard.c del ejercicio 09 SIN modificarlo: aquel escribe siempre
 *  en /sdcard/PICARO.CSV, y el experimento necesita un fichero por corrida.
 *  Aqui solo se abre /sdcard/<run_id>.csv y se escriben las filas.
 *
 *  POR QUE ESTE LOG ES CRITICO: es el DENOMINADOR del PDR. El servidor solo ve
 *  lo que llego, y sin el registro de lo que se ENVIO no se puede distinguir
 *  "no se envio" de "se perdio". Sin este fichero la corrida no es analizable
 *  aunque el servidor lo haya recibido todo.
 * ============================================================================
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "payload_terreno.h"   /* vuelo_lectura_t */

#ifdef __cplusplus
extern "C" {
#endif

/* Monta la microSD (delega en sdcard_init). */
esp_err_t runlog_init(void);
bool      runlog_disponible(void);

/* Convierte la base "20260814-CERRO16-C" en el run_id definitivo, añadiendo el
 * numero de intento si ya existe un fichero de una corrida anterior:
 *
 *     20260814-CERRO16-C      primer intento del dia
 *     20260814-CERRO16-C-2    segundo intento (el primero se aborto)
 *
 * POR QUE: una corrida abortada con el boton ya escribio filas. Si al reanudar
 * el mismo escenario se reutilizara el run_id, los dos intentos acabarian
 * mezclados en un solo CSV y serian imposibles de separar al analizar. Se
 * tratan como corridas DISTINTAS: si se aborto fue por algo, y sumarlas
 * despues es trivial mientras que separarlas no lo es.
 *
 * Se resuelve sondeando la tarjeta en vez de llevar un contador en NVS: el
 * estado real es el de los ficheros, y asi no hay forma de que un contador se
 * desincronice de lo que hay escrito. Sin microSD devuelve la base tal cual.
 * Escribe en buf y lo devuelve. */
const char *runlog_asignar_run_id(const char *base, char *buf, size_t len);

/* Una fila por uplink INTENTADO. Columnas:
 *   run_id,fcnt,utc,lat,lon,alt,sats,fix,temp_c,batt_mV,batt_mA,dr,sf,airtime_ms,tx_rc
 * batt_mA va vacia: el AXP2101 de esta placa no mide corriente de bateria.
 * tx_rc = 0 correcto, <0 error de RadioLib. Los fallidos SE REGISTRAN. */
void runlog_uplink(const char *run_id, uint32_t fcnt, const char *utc_iso,
                   bool fix, double lat, double lon, float alt_m, uint8_t sats,
                   float temp_c, uint16_t batt_mv,
                   uint8_t dr, uint8_t sf, uint32_t airtime_ms, int tx_rc,
                   uint8_t tipo, int rafaga);
/* tipo y rafaga (D-64) solo tienen sentido en VUELO: tipo 1..3 = P1..P3 y
 * rafaga 0..54. Fuera de VUELO se pasan tipo = 0 y rafaga = -1, y las dos
 * columnas quedan vacias. */

/* Solo VUELO: la lectura COMPLETA de cada rafaga, en <run_id>_lecturas.csv.
 * Es la verdad de lo que midio la placa, independiente de que paquetes
 * llegaran por aire. */
void runlog_lectura(const char *run_id, int rafaga, const char *utc_iso,
                    const vuelo_lectura_t *l);

/* Downlinks recibidos, en <run_id>_dl.csv:
 *   run_id,utc,fport,seq,accion,ventana
 * 'seq' es el primer byte del payload; en los pings de latencia es el numero de
 * secuencia que puso el servidor, y es lo que permite emparejar ambos lados.
 * 'utc' debe capturarse EN el momento de la recepcion (no al inicio del ciclo):
 * dos downlinks del mismo ciclo no deben compartir timestamp.
 * 'ventana' es rx1/rx2/rxc/desconocida: por que ventana llego, para auditar si
 * servidor y sonda coincidian en la clase (RX1/RX2 = Clase A; rxc = Clase C).
 * NOTA de compatibilidad: los CSV de campanas previas al 2026-08-29 tienen solo
 * las 5 primeras columnas; la cabecera se escribe al crear el fichero (lazy),
 * asi que el formato de un fichero ya empezado no cambia. */
void runlog_downlink(const char *run_id, const char *utc_iso,
                     uint8_t fport, uint8_t seq, const char *accion,
                     const char *ventana);

#ifdef __cplusplus
}
#endif
