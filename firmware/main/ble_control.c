/* ============================================================================
 *  ble_control.c  -  Servidor GATT de control por BLE (v2, Fase 2)
 * ----------------------------------------------------------------------------
 *  Sustituye a ble_spike.{c,h}, que se borra. Del spike se hereda lo que YA se
 *  probo en la placa (arranque de NimBLE, advertising con el nombre en el scan
 *  response, configuracion de seguridad, PASSKEY_ACTION con ble_sm_inject_io);
 *  NO se hereda ni el UUID del spike, ni su GATT, ni el passkey fijo 123456.
 *
 *  Este modulo hace tres cosas y ninguna mas:
 *    1. Expone dos caracteristicas PROTEGIDAS (_ENC|_AUTHEN). Que esten
 *       protegidas es lo que fuerza el emparejamiento: la pila responde 0x05
 *       Insufficient Authentication y Android empareja por su cuenta (§6.3).
 *       Aqui no hay ninguna llamada de "empareja ahora".
 *    2. Valida los comandos entrantes contra el ULTIMO estado publicado y los
 *       deja en una cola de UNO que app_main.cpp consume cuando le viene bien.
 *       Nada bloquea al bucle de la sonda.
 *    3. Publica los 6 bytes de Estado y notifica solo cuando cambian.
 *
 *  Lo que NO hace, a proposito (§9.1): no toca el OLED, ni el LED, ni el boton,
 *  ni conoce la maquina de estados. La pantalla de EMPAREJADO la pinta
 *  app_main.cpp leyendo ble_emp_fase(). Es la garantia estructural de que las
 *  pantallas de la v1 no pueden cambiar por accidente.
 *
 *  Doc NimBLE en ESP-IDF v5.5.2:
 *  https://docs.espressif.com/projects/esp-idf/en/v5.5.2/esp32s3/api-reference/bluetooth/nimble/index.html
 * ============================================================================ */

#include "ble_control.h"
#include "escenarios.h"   /* CORRIDAS_COUNT: rango valido del modo */

#include <string.h>

#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/ble_store.h"
#include "host/util/util.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"

/* Lo aporta el componente bt cuando NIMBLE_NVS_PERSIST esta activo. Sin esta
 * llamada el bonding no sobrevive a un reinicio (§9.5). */
void ble_store_config_init(void);

static const char *TAG = "ble_control";

#define BLE_NOMBRE        "PICARO-CAMPO"   /* igual en todas las sondas (§3.4) */
#define BLE_VER_PROTOCOLO 0x01             /* byte 0 de Estado (§4.3)          */
#define EST_LEN           6                /* tamano de Estado, exacto         */
#define CMD_LEN           2                /* tamano de Comando, exacto (§4.2) */
#define FALLO_US          (3 * 1000 * 1000)/* lo que dura la fase C (§7.4)     */

/* ult_cmd, byte 4 de Estado (§8.2). 0x01 SIN_AUTH queda RESERVADO y sin uso:
 * una escritura sin enlace seguro no llega a nuestro callback, la rechaza la
 * pila antes. Si alguna vez se viera un 0x01 en un log, seria la prueba de que
 * una caracteristica se declaro sin _ENC|_AUTHEN. */
#define ULT_OK        0x00
#define ULT_LONGITUD  0x02
#define ULT_PARAMETRO 0x03
#define ULT_ESTADO    0x04
#define ULT_NINGUNO   0xFF

/* Error ATT = 0x80 + ult_cmd (§8.3). El rango 0x80-0x9F esta reservado por la
 * especificacion a la capa de aplicacion y las pilas lo pasan tal cual, sin
 * interpretarlo. Nunca 0x05: ese codigo tiene un significado reservado (dispara
 * el emparejamiento del cliente) y confundirlo haria que Android intentara
 * emparejarse otra vez sobre un enlace ya seguro. */
#define ATT_ERR_DE(ult) (0x80 | (ult))

/* --------------------------------------------------------------- UUIDs ---- */
/* §2.3: BLE_UUID128_INIT espera los 16 bytes AL REVES que la forma legible, y
 * se invierte el array entero, no campo por campo. Comprobacion de 5 segundos:
 * los cuatro primeros bytes son 3c 1a f5 08 y los tres ultimos 2c f4 c9; lo
 * unico que distingue una caracteristica de otra es el indice 12. */

/*  Servicio  c9f42c00-f57d-43be-a6c4-466b08f51a3c  */
static const ble_uuid128_t UUID_SVC = BLE_UUID128_INIT(
    0x3c, 0x1a, 0xf5, 0x08, 0x6b, 0x46, 0xc4, 0xa6,
    0xbe, 0x43, 0x7d, 0xf5, 0x00, 0x2c, 0xf4, 0xc9);

/*  Comando   c9f42c03-f57d-43be-a6c4-466b08f51a3c  (write, protegida)  */
static const ble_uuid128_t UUID_CMD = BLE_UUID128_INIT(
    0x3c, 0x1a, 0xf5, 0x08, 0x6b, 0x46, 0xc4, 0xa6,
    0xbe, 0x43, 0x7d, 0xf5, 0x03, 0x2c, 0xf4, 0xc9);

/*  Estado    c9f42c04-f57d-43be-a6c4-466b08f51a3c  (read+notify, protegida) */
static const ble_uuid128_t UUID_EST = BLE_UUID128_INIT(
    0x3c, 0x1a, 0xf5, 0x08, 0x6b, 0x46, 0xc4, 0xa6,
    0xbe, 0x43, 0x7d, 0xf5, 0x04, 0x2c, 0xf4, 0xc9);

/* c9f42c01 y c9f42c02 (Reto y Auth de la version 1 del contrato) quedan
 * RETIRADOS y no se reutilizan nunca: un identificador retirado hace que una
 * implementacion desactualizada falle en voz alta -- "caracteristica no
 * encontrada" -- en vez de enlazar en silencio con la equivocada (§2.1). */

/* ---------------------------------------------------------------- Estado -- */
/* Todo lo compartido entre la tarea del host NimBLE (callbacks GATT y GAP) y la
 * tarea de app_main (el resto de la API) vive aqui, protegido por una seccion
 * critica corta. No hace falta una cola de FreeRTOS para 2 bytes (§9.4). */

static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;

/* Los 6 bytes de Estado, tal cual viajan (§4.3). Los bytes 0, 3 y 5 son
 * constantes: version y dos reservados. Se arranca en SIN_ENLACE (C-Fondo): la
 * sonda es operable desde el primer instante aunque el join corra por detras.
 * NO se arranca en UNIENDO, que queda retirado (Addendum A / MENOR-6-2p). */
static uint8_t s_estado[EST_LEN] = {
    BLE_VER_PROTOCOLO, 0x00, BLE_ESTADO_SIN_ENLACE, 0x00, ULT_NINGUNO, 0x00
};

static ble_cmd_t s_cmd = { .tipo = BLE_CMD_NINGUNO, .modo = 0 };

static bool           s_emparejable = false;   /* la ventana de §6.6          */
static ble_emp_fase_t s_fase        = BLE_EMP_ESPERANDO;
static uint32_t       s_passkey     = 0;
static uint16_t       s_motivo      = 0;
static int64_t        s_fallo_us    = 0;       /* cuando empezo la fase C     */

static uint16_t s_conn = BLE_HS_CONN_HANDLE_NONE;
static uint8_t  s_addr_type;
static uint16_t s_h_cmd, s_h_est;

static void anunciar(void);

/* ------------------------------------------------------- Estado: publicar -- */

/* Notifica a quien este suscrito. ble_gatts_chr_updated() consulta el CCCD de
 * cada par, asi que no hay que llevar la cuenta de las suscripciones ni hay
 * riesgo de notificar a quien no pidio nada. Si no hay nadie, no hace nada. */
static void notificar_estado(void)
{
    ble_gatts_chr_updated(s_h_est);
}

void ble_publicar_estado(uint8_t modo, ble_estado_t estado)
{
    bool cambio;

    portENTER_CRITICAL(&s_mux);
    cambio = (s_estado[1] != modo) || (s_estado[2] != (uint8_t)estado);
    s_estado[1] = modo;
    s_estado[2] = (uint8_t)estado;
    portEXIT_CRITICAL(&s_mux);

    /* Solo cuando los 6 bytes cambian (§4.3). Sin notificaciones periodicas ni
     * keepalive: BLE ya tiene su supervision timeout y un latido de aplicacion
     * encima gastaria radio sin anadir informacion. */
    if (cambio) notificar_estado();
}

/* Anota el resultado del ultimo comando y notifica si cambio. Dos rechazos
 * identicos seguidos producen UNA sola notificacion, y esta bien: el acuse de
 * la escritura es el error ATT, que llega siempre; la notificacion es para
 * observadores (§4.3). */
static void anotar_ult_cmd(uint8_t ult)
{
    bool cambio;

    portENTER_CRITICAL(&s_mux);
    cambio = (s_estado[4] != ult);
    s_estado[4] = ult;
    portEXIT_CRITICAL(&s_mux);

    if (cambio) notificar_estado();
}

/* ----------------------------------------------------------------- GATT ---- */

static int chr_estado(uint16_t conn, uint16_t attr,
                      struct ble_gatt_access_ctxt *ctxt, void *arg)
{
    (void)conn; (void)attr; (void)arg;

    /* Si esta funcion se ejecuta, el enlace YA esta cifrado y autenticado: sin
     * eso la pila responde 0x05 y no llega hasta aqui. */
    if (ctxt->op != BLE_GATT_ACCESS_OP_READ_CHR)
        return BLE_ATT_ERR_UNLIKELY;

    uint8_t copia[EST_LEN];
    portENTER_CRITICAL(&s_mux);
    memcpy(copia, s_estado, EST_LEN);
    portEXIT_CRITICAL(&s_mux);

    return os_mbuf_append(ctxt->om, copia, EST_LEN) == 0
               ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
}

/* Tabla de §5.3: que comando admite cada estado de la SONDA. Es lo que decide
 * entre ult_cmd = OK y ult_cmd = ESTADO. */
static bool comando_aplicable(ble_cmd_tipo_t tipo, uint8_t estado)
{
    /* re-join (op 0x03, Addendum B / D-62): SOLO en los dos estados de menu
     * operable. En CORRIENDO/ESPERANDO_ENLACE pisaria una corrida en marcha o
     * agendada; en FINALIZADA/ABORTADA el bucle aun tiene la radio tomada; en
     * EMPAREJADO nada se interrumpe por radio. La app solo lo necesita desde
     * el menu (llega tras el 409 de "clase desajustada", antes de arrancar). */
    if (tipo == BLE_CMD_REJOIN)
        return estado == BLE_ESTADO_CONFIG || estado == BLE_ESTADO_SIN_ENLACE;

    switch (estado) {
    /* UNIENDO queda RETIRADO (C-Fondo): no se emite. EMPAREJADO: el
     * emparejamiento no se interrumpe por radio -- cierra el caso del telefono
     * ya emparejado que manda comandos mientras se empareja otro (§7.5). */
    case BLE_ESTADO_UNIENDO:
    case BLE_ESTADO_EMPAREJADO:
        return false;

    /* SIN_ENLACE (C-Fondo, Addendum A.3): la sonda es operable sin enlace LoRa.
     * seleccionar SE acepta y arranca (esperando enlace si aun no unio, D2=A);
     * abortar es un no-op OK, como en CONFIG. */
    case BLE_ESTADO_SIN_ENLACE:
        return true;

    /* Cambiar de modo a mitad de corrida -- o con una corrida ya agendada
     * esperando enlace -- corromperia la medida: para cambiar hay que abortar
     * primero. Es la misma regla que ya aplica el boton (escenarios.h). */
    case BLE_ESTADO_CORRIENDO:
    case BLE_ESTADO_ESPERANDO_ENLACE:
        return tipo == BLE_CMD_ABORTAR;

    /* Estados de reposo. abortar en CONFIG y en ABORTADA es un no-op que
     * devuelve OK, no un error: abortar significa "quiero que estes en
     * configuracion", y si ya lo estas, lo pedido se cumplio. */
    case BLE_ESTADO_CONFIG:
    case BLE_ESTADO_FINALIZADA:
    case BLE_ESTADO_ABORTADA:
        return true;

    default:
        return false;
    }
}

/* Valida la escritura y, si procede, la encola. Devuelve el ult_cmd resultante. */
static uint8_t evaluar_escritura(struct os_mbuf *om)
{
    /* OS_MBUF_PKTLEN y no om_len: om_len es la longitud del PRIMER fragmento,
     * no la del paquete. Con 2 bytes nunca hay fragmentacion, asi que el bug no
     * se manifestaria en pruebas -- por eso se escribe bien desde el principio
     * (§4.4). */
    if (OS_MBUF_PKTLEN(om) != CMD_LEN)
        return ULT_LONGITUD;

    uint8_t b[CMD_LEN];
    if (ble_hs_mbuf_to_flat(om, b, sizeof b, NULL) != 0)
        return ULT_LONGITUD;

    /* La longitud se comprueba ANTES de mirar el opcode: asi b[0] y b[1]
     * existen siempre y no hay forma de leer fuera del buffer. */
    const uint8_t op = b[0];
    ble_cmd_tipo_t tipo;
    uint8_t        modo;

    if (op == 0x01) {
        if (b[1] >= CORRIDAS_COUNT) return ULT_PARAMETRO;   /* 0..6 (D-64) */
        tipo = BLE_CMD_SELECCIONAR;
        modo = b[1];
    } else if (op == 0x02) {
        /* El byte 1 de abortar debe estar presente pero se ignora (§4.2). */
        tipo = BLE_CMD_ABORTAR;
        modo = 0;
    } else if (op == 0x03) {
        /* re-join (Addendum B / D-62): descartar la sesion LoRaWAN y rehacer
         * el join OTAA en segundo plano. El byte 1 debe estar presente pero se
         * ignora, igual que en abortar. En un firmware anterior a este opcode
         * la misma trama devuelve ATT 0x83 (parametro), que es como la app
         * detecta que aqui solo queda el remedio de apagar y encender. */
        tipo = BLE_CMD_REJOIN;
        modo = 0;
    } else {
        return ULT_PARAMETRO;
    }

    uint8_t estado;
    portENTER_CRITICAL(&s_mux);
    estado = s_estado[2];
    portEXIT_CRITICAL(&s_mux);

    if (!comando_aplicable(tipo, estado)) {
        ESP_LOGW(TAG, "comando op=0x%02X rechazado: no aplica al estado 0x%02X",
                 op, estado);
        return ULT_ESTADO;
    }

    /* Cola de UNO: el nuevo PISA al que no se haya consumido (§9.4). Los
     * comandos BLE son ordenes de estado deseado, no gestos: si llegan
     * seleccionar(3) y seleccionar(5), lo que se quiere es correr el 5, no
     * arrancar dos corridas. */
    portENTER_CRITICAL(&s_mux);
    s_cmd.tipo = tipo;
    s_cmd.modo = modo;
    portEXIT_CRITICAL(&s_mux);

    return ULT_OK;
}

static int chr_comando(uint16_t conn, uint16_t attr,
                       struct ble_gatt_access_ctxt *ctxt, void *arg)
{
    (void)conn; (void)attr; (void)arg;

    if (ctxt->op != BLE_GATT_ACCESS_OP_WRITE_CHR)
        return BLE_ATT_ERR_UNLIKELY;

    const uint8_t ult = evaluar_escritura(ctxt->om);
    anotar_ult_cmd(ult);

    /* Dos canales para dos publicos: el error ATT es la respuesta sincrona a
     * quien escribio; ult_cmd en Estado es observable por lectura y por
     * notificacion, que es lo que permite validar la Fase 2 con un escaner. */
    return (ult == ULT_OK) ? 0 : ATT_ERR_DE(ult);
}

static const struct ble_gatt_svc_def GATT_SVCS[] = {
    {
        .type            = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid            = &UUID_SVC.u,
        .characteristics = (struct ble_gatt_chr_def[]) {
            {
                /* Write CON respuesta: sin ella la app no distingue "lo
                 * escribi" de "lo acepto". Nada de F_WRITE_NO_RSP.
                 * ENC = enlace cifrado; AUTHEN = ademas autenticado. Pedir
                 * AUTHEN es lo que fuerza Passkey Entry en vez de Just Works,
                 * que se completa igual y sin proteccion contra MITM. */
                .uuid       = &UUID_CMD.u,
                .access_cb  = chr_comando,
                .flags      = BLE_GATT_CHR_F_WRITE
                            | BLE_GATT_CHR_F_WRITE_ENC
                            | BLE_GATT_CHR_F_WRITE_AUTHEN,
                .val_handle = &s_h_cmd,
            },
            {
                /* Sin F_WRITE: cualquier escritura la rechaza la pila con 0x03
                 * Write Not Permitted, sin pasar por nuestro codigo. */
                .uuid       = &UUID_EST.u,
                .access_cb  = chr_estado,
                .flags      = BLE_GATT_CHR_F_READ
                            | BLE_GATT_CHR_F_READ_ENC
                            | BLE_GATT_CHR_F_READ_AUTHEN
                            | BLE_GATT_CHR_F_NOTIFY,
                .val_handle = &s_h_est,
            },
            { 0 }
        },
    },
    { 0 }
};

/* ------------------------------------------------------------ Conexiones -- */

static uint16_t conn_activa(void)
{
    uint16_t c;
    portENTER_CRITICAL(&s_mux);
    c = s_conn;
    portEXIT_CRITICAL(&s_mux);
    return c;
}

static void cortar_conexion(void)
{
    const uint16_t c = conn_activa();
    if (c != BLE_HS_CONN_HANDLE_NONE)
        ble_gap_terminate(c, BLE_ERR_REM_USER_CONN_TERM);
}

static void log_seguridad(uint16_t conn_handle, const char *cuando)
{
    struct ble_gap_conn_desc d;
    if (ble_gap_conn_find(conn_handle, &d) != 0) return;

    /* autenticado es el que no se puede olvidar: es el unico de los cuatro que
     * distingue Passkey Entry de Just Works (§5.1). */
    ESP_LOGW(TAG, "SEGURIDAD %s: cifrado=%d autenticado=%d bonded=%d llave=%d",
             cuando, d.sec_state.encrypted, d.sec_state.authenticated,
             d.sec_state.bonded, d.sec_state.key_size);
}

/* ------------------------------------------------------------ Eventos GAP -- */

static int gap_evento(struct ble_gap_event *ev, void *arg)
{
    (void)arg;

    switch (ev->type) {

    case BLE_GAP_EVENT_CONNECT:
        if (ev->connect.status == 0) {
            portENTER_CRITICAL(&s_mux);
            s_conn = ev->connect.conn_handle;
            portEXIT_CRITICAL(&s_mux);
            ESP_LOGI(TAG, "conexion aceptada");
            log_seguridad(ev->connect.conn_handle, "al conectar");
            /* Con MAX_CONNECTIONS=1 la sonda deja de anunciarse sola mientras
             * hay un central conectado; una segunda app ni la encuentra. */
        } else {
            ESP_LOGI(TAG, "conexion fallida (status %d); vuelvo a anunciar",
                     ev->connect.status);
            anunciar();
        }
        break;

    case BLE_GAP_EVENT_DISCONNECT:
        portENTER_CRITICAL(&s_mux);
        s_conn = BLE_HS_CONN_HANDLE_NONE;
        portEXIT_CRITICAL(&s_mux);
        ESP_LOGI(TAG, "desconexion (razon %d); vuelvo a anunciar",
                 ev->disconnect.reason);
        anunciar();
        break;

    case BLE_GAP_EVENT_ADV_COMPLETE:
        anunciar();
        break;

    /* Util para P-F1-07: si aqui aparece una suscripcion con cifrado=0, el CCCD
     * que NimBLE crea solo no hereda las restricciones de la caracteristica. */
    case BLE_GAP_EVENT_SUBSCRIBE:
        if (ev->subscribe.attr_handle == s_h_est) {
            ESP_LOGI(TAG, "suscripcion a Estado: notify=%d",
                     ev->subscribe.cur_notify);
            log_seguridad(ev->subscribe.conn_handle, "al suscribirse");
        }
        break;

    /* Con sm_io_cap = DISPLAY_ONLY la pila NO genera el passkey: espera que la
     * aplicacion elija el numero, lo muestre y lo inyecte (§6.4). */
    case BLE_GAP_EVENT_PASSKEY_ACTION: {
        if (ev->passkey.params.action != BLE_SM_IOACT_DISP) {
            ESP_LOGE(TAG, "accion de passkey NO esperada (%d): revisar sm_io_cap",
                     ev->passkey.params.action);
            return 0;
        }

        bool abierta;
        portENTER_CRITICAL(&s_mux);
        abierta = s_emparejable;
        portEXIT_CRITICAL(&s_mux);

        if (!abierta) {
            /* Fuera de EMPAREJADO no hay sitio donde pintar el numero, porque
             * las pantallas de config y de corrida conservan su comportamiento
             * de la v1 sin excepciones. Y como no hay sitio, no puede haber
             * emparejamiento: nadie empareja un telefono sin que alguien pulse
             * el boton de la sonda (§6.6). */
            ESP_LOGW(TAG, "emparejamiento fuera de EMPAREJADO: corto la conexion");
            ble_gap_terminate(ev->passkey.conn_handle, BLE_ERR_REM_USER_CONN_TERM);
            return 0;
        }

        /* esp_random() es el RNG por hardware, criptograficamente fuerte con el
         * subsistema de RF activo -- y aqui lo esta por construccion, porque
         * este evento solo llega con la pila corriendo. */
        const uint32_t pk = esp_random() % 1000000u;

        portENTER_CRITICAL(&s_mux);
        s_passkey = pk;
        s_fase    = BLE_EMP_PASSKEY;   /* fase B: app_main ya puede pintarlo */
        portEXIT_CRITICAL(&s_mux);

        struct ble_sm_io io = { .action = BLE_SM_IOACT_DISP, .passkey = pk };
        const int rc = ble_sm_inject_io(ev->passkey.conn_handle, &io);
        /* %06lu, con ceros a la izquierda: el dialogo de Android espera SIEMPRE
         * seis caracteres. Un passkey de 12345 impreso como "12345" hace que el
         * operador teclee cinco digitos y el emparejamiento falle con 1028, que
         * es indistinguible de haberlo tecleado mal (§6.4). */
        ESP_LOGW(TAG, "passkey de esta sesion: %06lu (inject_io rc=%d)",
                 (unsigned long)pk, rc);
        return 0;
    }

    /* Resultado del emparejamiento, o de un cifrado automatico al reconectar. */
    case BLE_GAP_EVENT_ENC_CHANGE: {
        struct ble_gap_conn_desc d;
        bool seguro = false;

        if (ev->enc_change.status == 0 &&
            ble_gap_conn_find(ev->enc_change.conn_handle, &d) == 0) {
            /* Los CUATRO, no solo encrypted: un Just Works da encrypted=1 y
             * bonded=1 con toda normalidad y sin proteccion MITM. Conformarse
             * con encrypted es el unico fallo de este contrato que funciona y
             * parece que funciona (§5.1, D-F1-22). */
            seguro = d.sec_state.encrypted     &&
                     d.sec_state.authenticated &&
                     d.sec_state.bonded        &&
                     d.sec_state.key_size == 16;
        }
        ESP_LOGW(TAG, "ENC_CHANGE status=%d", ev->enc_change.status);
        log_seguridad(ev->enc_change.conn_handle, "tras cifrar");

        bool abierta;
        portENTER_CRITICAL(&s_mux);
        abierta = s_emparejable;
        portEXIT_CRITICAL(&s_mux);

        /* Fuera de la ventana esto es una reconexion con llaves existentes: no
         * hay pantalla que actualizar y no se toca la fase. */
        if (!abierta) break;

        if (seguro) {
            portENTER_CRITICAL(&s_mux);
            s_fase = BLE_EMP_HECHO;
            portEXIT_CRITICAL(&s_mux);
            break;
        }

        /* Fallo real, o exito parcial (Just Works): en los dos casos NO se sale
         * de EMPAREJADO y se corta la conexion. El motivo que se ensena es el
         * status en crudo; con un Just Works vale 0, y ese "st=0" en la fase C
         * es precisamente la senal de T-11. */
        const int64_t ahora  = esp_timer_get_time();
        const uint16_t motivo = (uint16_t)ev->enc_change.status;

        portENTER_CRITICAL(&s_mux);
        s_fase     = BLE_EMP_FALLO;
        s_motivo   = motivo;
        s_fallo_us = ahora;
        s_passkey  = 0;
        portEXIT_CRITICAL(&s_mux);

        ble_gap_terminate(ev->enc_change.conn_handle, BLE_ERR_REM_USER_CONN_TERM);
        break;
    }

    /* Llega cuando un par con el que YA tenemos bond inicia un emparejamiento
     * nuevo. Caso real: el telefono hizo "olvidar dispositivo" y la sonda no se
     * entero. Sin manejarlo, el emparejamiento entra en bucle y el sintoma es
     * "nunca termina", sin ningun error legible (§6.5). */
    case BLE_GAP_EVENT_REPEAT_PAIRING: {
        struct ble_gap_conn_desc d;
        if (ble_gap_conn_find(ev->repeat_pairing.conn_handle, &d) != 0)
            return BLE_GAP_REPEAT_PAIRING_IGNORE;

        bool abierta;
        portENTER_CRITICAL(&s_mux);
        abierta = s_emparejable;
        portEXIT_CRITICAL(&s_mux);

        if (!abierta) {
            /* La rama que convierte el borrado de bonds en una revocacion de
             * verdad: un telefono que perdio sus llaves no las recupera sin que
             * alguien ponga la sonda en modo emparejar, o sea sin estar
             * fisicamente delante. */
            ESP_LOGW(TAG, "REPEAT_PAIRING fuera de EMPAREJADO: corto la conexion");
            ble_gap_terminate(ev->repeat_pairing.conn_handle,
                              BLE_ERR_REM_USER_CONN_TERM);
            return BLE_GAP_REPEAT_PAIRING_IGNORE;
        }

        ESP_LOGW(TAG, "REPEAT_PAIRING: borro el bond viejo de ese par y reintento");
        ble_store_util_delete_peer(&d.peer_id_addr);
        return BLE_GAP_REPEAT_PAIRING_RETRY;
    }

    default:
        break;
    }

    return 0;
}

/* --------------------------------------------------------- Advertising ---- */

static void anunciar(void)
{
    /* 31 bytes contados: flags (3) + UUID de 128 bits (18) = 21, y sobran 10
     * que se quedan libres. El nombre (14) NO cabe -- 35 > 31 -- y va en el
     * SCAN RESPONSE, que Android fusiona con el advertising antes de entregar
     * el ScanResult. El UUID va en el advertising porque es el campo por el que
     * filtra la app, y en Android ese filtrado se resuelve en el chip contra el
     * paquete de advertising (§3.2). Si alguien mete el nombre aqui, esto
     * devuelve BLE_HS_EMSGSIZE, o sea rc=4. */
    struct ble_hs_adv_fields adv;
    memset(&adv, 0, sizeof adv);
    adv.flags                = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    adv.uuids128             = (ble_uuid128_t *)&UUID_SVC;
    adv.num_uuids128         = 1;
    adv.uuids128_is_complete = 1;

    int rc = ble_gap_adv_set_fields(&adv);
    if (rc != 0) { ESP_LOGE(TAG, "adv_set_fields rc=%d", rc); return; }

    struct ble_hs_adv_fields rsp;
    memset(&rsp, 0, sizeof rsp);
    rsp.name             = (uint8_t *)BLE_NOMBRE;
    rsp.name_len         = strlen(BLE_NOMBRE);
    rsp.name_is_complete = 1;

    rc = ble_gap_adv_rsp_set_fields(&rsp);
    if (rc != 0) { ESP_LOGE(TAG, "adv_rsp_set_fields rc=%d", rc); return; }

    struct ble_gap_adv_params params;
    memset(&params, 0, sizeof params);
    params.conn_mode = BLE_GAP_CONN_MODE_UND;   /* conectable, no dirigido */
    params.disc_mode = BLE_GAP_DISC_MODE_GEN;   /* descubrible siempre     */

    /* BLE_HS_FOREVER: anuncia mientras este encendida y no conectada (RF-1). */
    rc = ble_gap_adv_start(s_addr_type, NULL, BLE_HS_FOREVER,
                           &params, gap_evento, NULL);
    if (rc != 0) ESP_LOGE(TAG, "adv_start rc=%d", rc);
    else         ESP_LOGI(TAG, "anunciando como '%s'", BLE_NOMBRE);
}

/* --------------------------------------------------- API: comandos/estado -- */

bool ble_tomar_comando(ble_cmd_t *out)
{
    bool hay;

    portENTER_CRITICAL(&s_mux);
    hay = (s_cmd.tipo != BLE_CMD_NINGUNO);
    if (hay && out != NULL) *out = s_cmd;
    s_cmd.tipo = BLE_CMD_NINGUNO;   /* consultar consume, igual que boton_tomar */
    portEXIT_CRITICAL(&s_mux);

    return hay;
}

/* ------------------------------------------------- API: emparejamiento ----- */

bool ble_hay_bonds(void)
{
    int n = 0;
    if (ble_store_util_count(BLE_STORE_OBJ_TYPE_OUR_SEC, &n) != 0) {
        ESP_LOGW(TAG, "no se pudo contar los bonds; asumo que no hay");
        return false;
    }
    return n > 0;
}

void ble_emparejable(bool abrir)
{
    if (abrir) {
        /* La ventana se abre ANTES de cortar: el telefono que se reconecte tras
         * el corte tiene que encontrarla ya abierta. */
        portENTER_CRITICAL(&s_mux);
        s_emparejable = true;
        s_fase        = BLE_EMP_ESPERANDO;
        s_passkey     = 0;
        s_motivo      = 0;
        portEXIT_CRITICAL(&s_mux);

        /* §7.3: con MAX_CONNECTIONS=1, un telefono ya emparejado que siga
         * conectado ocupa la unica ranura y el telefono nuevo no puede ni
         * conectar. Ademas, sin cortar, el operador no veria nada distinto. */
        cortar_conexion();
        ESP_LOGI(TAG, "ventana de emparejamiento ABIERTA");
        return;
    }

    ble_emp_fase_t antes;
    portENTER_CRITICAL(&s_mux);
    s_emparejable = false;
    antes         = s_fase;
    s_fase        = BLE_EMP_ESPERANDO;
    s_passkey     = 0;
    s_motivo      = 0;
    portEXIT_CRITICAL(&s_mux);

    /* Un emparejamiento a medias se aborta. Uno que ya termino bien NO se toca:
     * cortar ahi seria echar al telefono que acaba de emparejarse. */
    if (antes == BLE_EMP_PASSKEY) cortar_conexion();
    ESP_LOGI(TAG, "ventana de emparejamiento CERRADA");
}

ble_emp_fase_t ble_emp_fase(uint32_t *passkey, uint16_t *motivo)
{
    const int64_t ahora = esp_timer_get_time();
    ble_emp_fase_t f;
    uint32_t pk;
    uint16_t mo;

    portENTER_CRITICAL(&s_mux);
    /* La fase C se ensena 3 s y vuelve sola a la A (§7.4). El temporizador vive
     * aqui y no en app_main porque el bucle de §9.3.1 solo repinta cuando la
     * fase cambia: si nadie la hiciera caducar, el OLED se quedaria con el
     * mensaje de fallo hasta el siguiente intento. */
    if (s_fase == BLE_EMP_FALLO && (ahora - s_fallo_us) >= FALLO_US) {
        s_fase   = BLE_EMP_ESPERANDO;
        s_motivo = 0;
    }
    f  = s_fase;
    pk = s_passkey;
    mo = s_motivo;
    portEXIT_CRITICAL(&s_mux);

    if (passkey != NULL) *passkey = pk;
    if (motivo  != NULL) *motivo  = mo;
    return f;
}

void ble_bonds_borrar(void)
{
    /* Es el unico caso que "olvidar dispositivo" en Android no cubre: si el
     * telefono se perdio, sus llaves siguen siendo validas y quien lo tenga
     * puede mandar comandos. Tras esto, volver a entrar exige que alguien pulse
     * el boton, asi que la revocacion es efectiva y no cosmetica (§7.5). */
    const int rc = ble_store_clear();
    ESP_LOGW(TAG, "TODOS los bonds borrados (rc=%d)", rc);

    portENTER_CRITICAL(&s_mux);
    s_fase    = BLE_EMP_ESPERANDO;   /* se permanece en EMPAREJADO, fase A */
    s_passkey = 0;
    s_motivo  = 0;
    portEXIT_CRITICAL(&s_mux);

    cortar_conexion();
}

/* -------------------------------------------------------------- Arranque -- */

static void on_sync(void)
{
    int rc = ble_hs_util_ensure_addr(0);
    if (rc != 0) { ESP_LOGE(TAG, "ensure_addr rc=%d", rc); return; }

    /* Direccion PUBLICA, y con bonding lo es mas que antes: el bond asocia las
     * llaves a la direccion de identidad del par, asi que una direccion privada
     * aleatoria dejaria el bond inservible en cada rotacion (§3.3). */
    rc = ble_hs_id_infer_auto(0, &s_addr_type);
    if (rc != 0) { ESP_LOGE(TAG, "infer_auto rc=%d", rc); return; }

    uint8_t addr[6] = {0};
    ble_hs_id_copy_addr(s_addr_type, addr, NULL);
    ESP_LOGI(TAG, "BLE listo · addr %02X:%02X:%02X:%02X:%02X:%02X",
             addr[5], addr[4], addr[3], addr[2], addr[1], addr[0]);

    anunciar();
}

static void on_reset(int razon)
{
    ESP_LOGE(TAG, "el stack BLE se reinicio (razon %d)", razon);
}

static void host_task(void *param)
{
    (void)param;
    nimble_port_run();
    nimble_port_freertos_deinit();
}

esp_err_t ble_init(void)
{
    esp_err_t err = nimble_port_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nimble_port_init fallo: %s", esp_err_to_name(err));
        return err;
    }

    ble_hs_cfg.sync_cb  = on_sync;
    ble_hs_cfg.reset_cb = on_reset;

    /* --- LE Secure Connections con Passkey Entry (§6.2) -------------------
     * NINGUNA de estas lineas es cosmetica:
     *   io_cap DISPLAY_ONLY = "yo muestro un numero, tu lo tecleas". Con
     *     NO_INPUT_OUTPUT el emparejamiento cae a Just Works: se completa igual,
     *     sin ensenar numero, y sin proteccion contra man-in-the-middle.
     *   sm_sc = 1 evita el legacy pairing, cuyo intercambio de llaves es
     *     recuperable en pasivo. Por si solo NO impide una negociacion a la
     *     baja: la defensa real es compilarlo fuera con SM_LEGACY=n (§9.5).
     *   sm_mitm = 1 es lo que se EXIGE; io_cap solo dice lo que se PUEDE.
     *   sm_bonding = 1 guarda las llaves -> reconexion automatica en ~270 ms. */
    ble_hs_cfg.sm_io_cap         = BLE_HS_IO_DISPLAY_ONLY;
    ble_hs_cfg.sm_sc             = 1;
    ble_hs_cfg.sm_mitm           = 1;
    ble_hs_cfg.sm_bonding        = 1;
    ble_hs_cfg.sm_our_key_dist   = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
    ble_hs_cfg.sm_their_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;

    ble_svc_gap_init();
    ble_svc_gatt_init();

    int rc = ble_gatts_count_cfg(GATT_SVCS);
    if (rc != 0) { ESP_LOGE(TAG, "gatts_count_cfg rc=%d", rc); return ESP_FAIL; }

    rc = ble_gatts_add_svcs(GATT_SVCS);
    if (rc != 0) { ESP_LOGE(TAG, "gatts_add_svcs rc=%d", rc); return ESP_FAIL; }

    rc = ble_svc_gap_device_name_set(BLE_NOMBRE);
    if (rc != 0) ESP_LOGW(TAG, "device_name_set rc=%d", rc);

    ble_store_config_init();   /* bonding persistente en NVS */

    /* Sin esto, cuando el almacen se llena (MAX_BONDS = 3) el emparejamiento
     * numero cuatro falla con BLE_HS_ESTORE_CAP, y el sintoma -- "falla en esta
     * sonda y en las demas no" -- es desproporcionadamente dificil de
     * diagnosticar. status_rr desaloja el bond mas antiguo y reintenta. */
    ble_hs_cfg.store_status_cb = ble_store_util_status_rr;

    nimble_port_freertos_init(host_task);
    return ESP_OK;
}
