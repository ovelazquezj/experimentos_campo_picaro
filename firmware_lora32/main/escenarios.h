/**
 * ============================================================================
 *  escenarios.h  -  Las 6 corridas del experimento de pruebas de terreno
 * ============================================================================
 *
 *  UN SOLO BINARIO cubre 3 escenarios x 2 clases LoRaWAN. No hay que
 *  recompilar entre corridas: se elige en un MENU y la eleccion sobrevive a
 *  reinicios (NVS).
 *
 *  SELECCIONAR NO ES ARRANCAR. Son dos acciones distintas y esa separacion es
 *  deliberada: navegar el menu no transmite, no reconfigura la radio y no toca
 *  los contadores. Nada ocurre hasta que el operador confirma. Antes esto no
 *  era asi -- cambiar de escenario lo arrancaba en el acto -- y en campo eso
 *  significaba uplinks basura al principio de cada corrida y ninguna forma de
 *  sincronizar el arranque con el momento real de la prueba.
 *
 *      MENU     pulsacion corta -> siguiente de las 6 opciones
 *               doble pulsacion -> CONFIRMA y arranca la corrida
 *      CORRIDA  pulsacion larga (>2 s) -> aborta y vuelve al MENU
 *               corta y doble se IGNORAN (un roce no debe hacer nada)
 *      FIN      pulsacion larga -> vuelve al MENU
 *
 *  Una sola regla que enseñar en campo: larga = ir al menu, siempre.
 *
 *  LA v2 NO CAMBIA NADA DE LO ANTERIOR. Anade el BLE como segunda fuente de
 *  mando (comando_tomar(), mas abajo) y dos gestos que antes no existian, los
 *  dos en huecos que estaban libres:
 *
 *      MENU        pulsacion larga -> abre la ventana de emparejamiento (RF-11).
 *                  Antes no hacia nada: ya estabas en el menu.
 *      EMPAREJADO  corta o larga -> sale al MENU (RF-10, la salida sin movil)
 *                  doble         -> olvida TODOS los telefonos emparejados
 *
 *  La regla de campo sigue en pie: larga = ir al menu, siempre. Desde el menu
 *  no hay menu al que ir, y ese es el hueco que ocupa RF-11.
 *
 *  DE DONDE SALEN LOS INTERVALOS (no son elegibles):
 *  El servidor tiene rx1_delay = 5 s y NO SE TOCA. En Clase A no se puede
 *  transmitir hasta cerrar RX1 (5 s) y RX2 (6 s), asi que el ciclo minimo real
 *  ronda los 6,5 s. Pedir menos no acelera nada: el stack lo retrasa solo y el
 *  intervalo declarado dejaria de ser el real.
 *
 *  TABLA DE DATA RATES DE US915 (distinta de EU868, error facil):
 *      DR0 = SF10/125k   DR1 = SF9/125k   DR2 = SF8/125k   DR3 = SF7/125k
 *      DR4 = SF8/500k    SF11 y SF12 NO existen para uplink en esta region.
 *  Por eso DR0/SF10 es el maximo alcance posible, y por eso su payload esta
 *  limitado a 11 bytes (dwell time de 400 ms).
 * ============================================================================
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ESC_URBANO  = 0,   /* terreno movil urbano, en vehiculo a 30-40 km/h */
    ESC_TERRAZA = 1,   /* terraza del piso 5, exterior, LoS al gateway   */
    ESC_CERRO   = 2,   /* Cerro del Muerto, LoS a 16,35 km              */
    ESC_VUELO   = 3,   /* telemetria de la capsula, por rafagas (D-64)  */
    ESC_COUNT   = 4
} escenario_t;

typedef enum {
    CLASE_A = 0,
    CLASE_C = 1,
    CLASE_COUNT = 2
} clase_t;

/* Las 7 opciones del menu, en este orden:
 *   0 URBANO-A  1 URBANO-C  2 TERRAZA-A  3 TERRAZA-C  4 CERRO16-A  5 CERRO16-C
 *   6 VUELO-A
 * Hasta D-64 el indice se partia en escenario = i/2, clase = i%2, porque todos
 * los escenarios tenian A y C. VUELO solo tiene A, asi que la correspondencia
 * pasa a una tabla explicita (CORRIDAS). Los indices 0..5 no cambian: son el
 * modo del contrato BLE y lo que hay guardado en NVS. */
#define CORRIDAS_COUNT  7

typedef struct {
    const char *id;              /* corto, para el OLED: "CERRO16"        */
    const char *descripcion;     /* legible, para los logs                */
    uint8_t     dr;              /* Data Rate US915 (0..3)                */
    uint8_t     sf;              /* informativo: para mostrar y registrar */
    uint32_t    intervalo_ms;    /* periodo de uplink                     */
    uint16_t    uplinks_objetivo;/* la corrida termina al alcanzarlo      */
    uint8_t     fport[CLASE_COUNT];  /* etiqueta de corrida, por clase    */
    bool        payload_extendido;   /* false en DR0: no caben los 3 bytes
                                        de bateria (limite de 11)         */
    uint8_t     paquetes_rafaga; /* 0 = un payload clasico por uplink; N =
                                    la lectura se reparte en N paquetes
                                    consecutivos (VUELO, docs/VUELO-ESPEC) */
} escenario_cfg_t;

typedef struct {
    escenario_t esc;
    clase_t     clase;
} corrida_def_t;

extern const corrida_def_t CORRIDAS[CORRIDAS_COUNT];

/* Definida en escenarios.c:
 *
 *   esc      DR/SF      intervalo  uplinks  fPort A/C  payload
 *   URBANO   DR1/SF9    8,0 s      300      11 / 12    14 bytes
 *   TERRAZA  DR3/SF7    8,0 s      300      13 / 14    14 bytes
 *   CERRO16  DR0/SF10   8,0 s      300      15 / 16    11 bytes
 *   VUELO    DR0/SF10  20,0 s      165      17 / --    11 bytes, 3 por rafaga
 */
extern const escenario_cfg_t ESCENARIOS[ESC_COUNT];

/* --- Boton --------------------------------------------------------------- */

typedef enum {
    BTN_NINGUNO = 0,
    BTN_CORTO,        /* solo significa algo en el MENU                     */
    BTN_LARGO,        /* >2 s: ir al menu (abortando la corrida si la hay)  */
    BTN_DOBLE,        /* solo significa algo en el MENU: confirmar          */
} boton_evt_t;

/* Consulta no bloqueante. Devuelve el evento pendiente y lo consume.
 * QUIEN LLAMA DECIDE QUE HACER CON EL: en corrida, los eventos corto y doble
 * se descartan a proposito, para que un roce del boton no altere una medida en
 * marcha. La unica entrada al menu es una pulsacion larga deliberada.
 *
 * La maquina de estados ya NO llama a esto: usa comando_tomar(), que funde el
 * boton con el BLE. Se conserva expuesto porque es el gesto en crudo y sigue
 * siendo lo que hay que mirar para depurar el boton en si. */
boton_evt_t boton_tomar(void);

/* --- Entrada unificada: boton O BLE -------------------------------------- */
/*
 *  La v2 anade el BLE como segunda fuente de mando (CR-v2 §6). Para que la
 *  maquina de estados no tenga que preguntar dos veces, ni sepa de donde vino
 *  la orden, las dos entradas se funden aqui en un unico comando pendiente:
 *  comando_tomar() es lo unico que consultan los bucles de app_main.cpp.
 *
 *  EL BOTON NO DEPENDE DEL BLE (RF-8). Esta capa solo TRADUCE gestos a
 *  comandos; no arbitra, no espera a nadie y no consulta ningun estado del
 *  enlace. Con el modulo BLE caido, o sin movil, cada gesto sigue produciendo
 *  exactamente el mismo comando que producia en la v1. Ese es el respaldo, y
 *  es lo que no se puede romper: una salida de campo con el telefono muerto
 *  tiene que poder operarse igual.
 *
 *  El significado de un gesto depende de DONDE se este -- en corrida el corto
 *  no significa nada, en el menu si --, exactamente como en la v1. Por eso hay
 *  que decir el contexto: asi la tabla de traduccion vive en un solo sitio
 *  (escenarios.c) en vez de repartida por los bucles, que es como estaba.
 */
typedef enum {
    CTX_MENU = 0,     /* configuracion: se navega y se arranca               */
    CTX_CORRIDA,      /* midiendo: solo se puede abortar                     */
    CTX_FIN,          /* corrida terminada, sin transmitir                   */
    CTX_EMPAREJADO,   /* ventana de emparejamiento BLE (v2, §7 del contrato) */
    CTX_ESPERANDO,    /* espera de enlace tras seleccionar sin unir (C-Fondo) */
} contexto_t;

typedef enum {
    CMD_NINGUNO = 0,
    CMD_SIGUIENTE,     /* mover el cursor a la siguiente de las 7 corridas   */
    CMD_ARRANCAR,      /* confirmar y arrancar (== la doble pulsacion)       */
    CMD_ABORTAR,       /* volver a configuracion (== "ir al menu")           */
    CMD_EMPAREJAR,     /* abrir la ventana de emparejamiento (RF-11)         */
    CMD_BORRAR_BONDS,  /* olvidar TODOS los telefonos emparejados            */
    CMD_REJOIN,        /* rehacer el join OTAA en fondo (D-62). Solo lo
                        * produce el BLE, y solo en CTX_MENU: el boton no
                        * tiene gesto para esto (su respaldo es apagar y
                        * encender, que consigue lo mismo)                    */
} cmd_tipo_t;

typedef struct {
    cmd_tipo_t tipo;
    uint8_t    modo;       /* 0..6; solo valido si trae_modo                 */
    bool       trae_modo;  /* el boton NO dice CUAL corrida, solo "esta", y
                            * por eso hay que navegar hasta ella. El BLE si
                            * la dice, y por eso puede arrancar desde FIN
                            * sin pasar por el menu (contrato §5.3)          */
    bool       de_ble;     /* de donde vino. SOLO para el log: ninguna
                            * decision puede depender de este campo          */
} cmd_t;

/* Consulta NO bloqueante, misma forma que boton_tomar(): devuelve true y
 * rellena *out si habia un comando, y lo consume.
 *
 * Un gesto sin significado en `ctx` se descarta AQUI, igual que la v1
 * descartaba el corto y el doble durante una corrida. Un comando BLE que no
 * toca en `ctx` tambien: el GATT ya lo rechaza antes (contrato §5.3), asi que
 * si llega es que algo va mal y se tira en silencio, como el roce del boton. */
bool comando_tomar(contexto_t ctx, cmd_t *out);

/* --- Ciclo de vida ------------------------------------------------------- */

/* Carga la seleccion de NVS y arranca la tarea del boton. Sin nada guardado
 * arranca en URBANO / Clase A. Llamar una vez al inicio. */
void escenarios_init(void);

/* --- Seleccion ----------------------------------------------------------- */
/* Mientras se navega el menu la seleccion es PROVISIONAL: se refleja aqui para
 * poder pintarla, pero no se ha persistido ni aplicado a la radio. */

uint8_t     seleccion_indice(void);   /* 0..6 */
escenario_t escenario_actual(void);
clase_t     clase_actual(void);

/* Configuracion activa. Nunca devuelve NULL. */
const escenario_cfg_t *escenario_cfg(void);

/* fPort de la corrida seleccionada (11..17). */
uint8_t escenario_fport(void);

/* Avanza a la siguiente de las 7 opciones. NO persiste ni aplica nada: solo
 * mueve el cursor del menu. */
void seleccion_siguiente(void);

/* Pone el cursor en una opcion concreta. NO persiste ni aplica nada, igual que
 * seleccion_siguiente(): sigue haciendo falta corrida_confirmar().
 *
 * Existe porque el BLE si sabe decir "la 3" mientras que el boton solo sabe
 * avanzar. La validacion (0..6) va DENTRO, no en quien llama: la invariante de
 * s_sel -- que escenario y clase se derivan de el y nunca discrepan -- se
 * garantiza en un sitio, y un indice fuera de rango se ignora con un aviso en
 * vez de dejar la seleccion en un valor imposible. */
void seleccion_fijar(uint8_t idx);

/* Confirma la seleccion: la persiste en NVS y pone los contadores a cero.
 * Tras esto hay que llamar a lorawan_aplicar_corrida() y asignar el run_id. */
void corrida_confirmar(void);

/* Identificador BASE de corrida, con la fecha UTC del GPS si hay fix:
 * "20260814-CERRO16-C". Sin fix usa "00000000".
 * OJO: es la base, no el run_id definitivo. El numero de intento lo añade
 * runlog_asignar_run_id() sondeando la microSD, porque solo alli se sabe si ya
 * existe un fichero de una corrida anterior con la misma fecha y escenario. */
const char *escenario_run_id_base(char *buf, size_t len);

/* --- Progreso de la corrida ---------------------------------------------- */

uint16_t corrida_uplinks_enviados(void);  /* intentos, incluidos los fallidos */
uint16_t corrida_uplinks_ok(void);        /* transmitidos sin error           */
bool     corrida_completa(void);
void     corrida_registrar_tx(bool ok);
void     corrida_reiniciar(void);

#ifdef __cplusplus
}
#endif
