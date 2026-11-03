/**
 * ============================================================================
 *  lorawan.cpp  -  OTAA US915 (RadioLib) con persistencia de nonces/sesion NVS
 * ============================================================================
 *
 *  Flujo canonico de RadioLib:
 *    1) beginOTAA(joinEUI, devEUI, nwkKey, appKey)  -> nwkKey=NULL => 1.0.x
 *    2) (si hay) setBufferNonces()/setBufferSession() desde NVS
 *    3) activateOTAA() -> NEW_SESSION (join nuevo) o SESSION_RESTORED
 *    4) guardar getBufferNonces()/getBufferSession() en NVS
 *    5) sendReceive() para cada uplink; tras cada uno, guardar la sesion.
 * ============================================================================
 */
#include "lorawan.h"
#include "radio.h"
#include "config_lorawan.h"
#include "escenarios.h"

#include "esp_log.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "nvs.h"

#include <string.h>
#include <atomic>

static const char *TAG = "lorawan";

/* Ultimo downlink pendiente de leer (ver lorawan_tomar_downlink). */
static bool              s_dl_hay;
static uint8_t           s_dl_fport;
static uint8_t           s_dl_b0;
static size_t            s_dl_len;
static lorawan_ventana_t s_dl_ventana;

/* RadioLib devuelve la ventana como codigo de retorno (>0) de sendReceive y
 * getDownlinkClassC: RADIOLIB_LORAWAN_RX1=1, RX2=2, RX_BC=3 (LoRaWAN.h:56-58;
 * "return downlink window number" en LoRaWAN.cpp:1704 y 1809). El mapeo es
 * explicito: cualquier otro codigo se registra como DESCONOCIDA, no se inventa. */
static lorawan_ventana_t ventana_desde_codigo(int16_t st)
{
    switch (st) {
    case RADIOLIB_LORAWAN_RX1:   return LORAWAN_VENTANA_RX1;
    case RADIOLIB_LORAWAN_RX2:   return LORAWAN_VENTANA_RX2;
    case RADIOLIB_LORAWAN_RX_BC: return LORAWAN_VENTANA_RXC;
    default:                     return LORAWAN_VENTANA_DESCONOCIDA;
    }
}

/* Nodo LoRaWAN: se construye PEREZOSAMENTE en lorawan_join() (runtime), no como
 * global. Motivo: el constructor de LoRaWANNode hace phyLayer->getMod()->hal->...,
 * y si el nodo se construye como global ANTES que el objeto `radio` (orden de
 * inicializacion estatica indefinido entre .cpp), `hal` es NULL y crashea. */
/* --- A-11: una JoinAccept AJENA envenena el nodo ------------------------------
 * RadioLib 7.7.1, processJoinAccept(): descifra cualquier JoinAccept que oiga en
 * RX1/RX2 y, ANTES de verificar su MIC, fija this->rev con el bit OptNeg
 * (LoRaWAN.cpp:811; igual con joinNonce y devAddr). Si el MIC falla, devuelve
 * MIC_MISMATCH sin deshacer nada. Una JoinAccept de otra red, descifrada con
 * nuestra AppKey, trae un OptNeg al azar: la mitad de las veces deja rev = 1, y
 * desde entonces composeJoinRequest() firma con nwkKey, que en 1.0.x vale ceros
 * -> ChirpStack rechaza TODOS los JoinRequest con "Invalid MIC" y la sonda no
 * vuelve a unirse hasta reiniciarse. Ni clearSession() ni el re-join lo arreglan.
 * Es lo que paso en el cerro el 2026-09-27 (25 JoinRequest rechazados).
 *
 * Remedio: tras CUALQUIER intento fallido, y en cada re-join, se reconstruye el
 * nodo desde cero (rearmar_nodo) conservando solo los nonces, que es el unico
 * estado que tiene que sobrevivir. La subclase solo expone rev para registrar
 * cuando ocurrio: no se toca el estado interno de RadioLib a mano. */
/* final: se borra siempre como PicaroNode, asi el destructor no virtual de la
 * base no es problema (-Wdelete-non-virtual-dtor). */
class PicaroNode final : public LoRaWANNode {
public:
    using LoRaWANNode::LoRaWANNode;
    uint8_t revision() const { return rev; }
#if PICARO_TEST_REV_CORRUPTO
    void corromper_rev() { rev = 1; }   /* solo banco: simula la JoinAccept ajena */
#endif
};

static PicaroNode *node = nullptr;
static bool s_joined = false;

/* --- C-Fondo: arbitrio de la radio (equipo/DISENO-JOIN-EN-FONDO.md §4) ------
 * La radio (SX1262 + node) tiene EXACTAMENTE un dueno a la vez. La tarea de
 * join la posee mientras adquiere el enlace; el bucle, durante una corrida.
 * Nunca la quieren a la vez: la tarea suelta ANTES de marcar s_unido, y el
 * bucle solo la toma DESPUES de ver s_unido (§6.2). Cero contencion. */
typedef enum { RADIO_NADIE = 0, RADIO_JOIN, RADIO_BUCLE } radio_dueno_t;

static SemaphoreHandle_t      s_radio_mtx;              /* creado en iniciar_...    */
static volatile radio_dueno_t s_dueno = RADIO_NADIE;   /* solo para el assert      */
static std::atomic<bool>      s_unido{false};          /* la tarea lo pone AL SOLTAR */
static bool                   s_prepared = false;      /* preparar() idempotente   */

/* --- Re-join por BLE (D-62) -------------------------------------------------
 * Estado compartido entre lorawan_rejoin() y la tarea de join. Se lee y escribe
 * bajo una seccion critica de spinlock: son tres asignaciones sin nada que
 * bloquee, y hace falta que "anotar la peticion" y "la tarea decide morir"
 * sean mutuamente excluyentes -- si no, una peticion que llega justo cuando la
 * tarea esta saliendo se perderia sin nadie que la atienda, y la sonda se
 * quedaria sin enlace esperando un join que nadie va a intentar. */
static portMUX_TYPE s_rejoin_mux    = portMUX_INITIALIZER_UNLOCKED;
static bool         s_tarea_viva    = false;  /* hay una tarea de join corriendo  */
static bool         s_rejoin_pedido = false;  /* peticion aun sin consumir        */

/* Envuelven todo acceso a la radio. El assert de dueno unico es RNF-B3. */
static bool radio_tomar(radio_dueno_t quien, TickType_t timeout)
{
    if (xSemaphoreTake(s_radio_mtx, timeout) != pdTRUE) return false;
    configASSERT(s_dueno == RADIO_NADIE);
    s_dueno = quien;
    return true;
}
static void radio_soltar(radio_dueno_t quien)
{
    configASSERT(s_dueno == quien);
    s_dueno = RADIO_NADIE;
    xSemaphoreGive(s_radio_mtx);
}

#define NVS_NS       "picaro_lw"
#define KEY_NONCES   "nonces"
#define KEY_SESSION  "session"

/* ---- helpers NVS (blobs) ---- */
static bool nvs_load_blob(const char *key, uint8_t *buf, size_t len)
{
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) != ESP_OK) return false;
    size_t sz = len;
    esp_err_t e = nvs_get_blob(h, key, buf, &sz);
    nvs_close(h);
    return (e == ESP_OK && sz == len);
}
static void nvs_save_blob(const char *key, const uint8_t *buf, size_t len)
{
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) != ESP_OK) return;
    nvs_set_blob(h, key, buf, len);
    nvs_commit(h);
    nvs_close(h);
}
static void nvs_del_all(void)
{
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) != ESP_OK) return;
    nvs_erase_all(h);
    nvs_commit(h);
    nvs_close(h);
}

/* --- Setup del join, UNA sola vez (idempotente). Aqui, y SOLO aqui, viven el
 * wipe de FORCE_FRESH_JOIN, new LoRaWANNode, beginOTAA, setADR y restaurar
 * nonces/sesion. Repetirlo por intento borraria la sesion recien ganada (§3,
 * revision P3). Devuelve ESP_FAIL sin marcar preparado -> se reintenta. --- */
static esp_err_t lorawan_join_preparar(void)
{
    if (s_prepared) return ESP_OK;

#if PICARO_RESET_NONCES
    ESP_LOGW(TAG, "PICARO_RESET_NONCES=1 -> borrando nonces/sesion guardados");
    nvs_del_all();
#endif
#if PICARO_FORCE_FRESH_JOIN
    ESP_LOGW(TAG, "PICARO_FORCE_FRESH_JOIN=1 -> ignoro la sesion guardada, join OTAA real");
    nvs_save_blob(KEY_SESSION, (const uint8_t[RADIOLIB_LORAWAN_SESSION_BUF_SIZE]){0},
                  RADIOLIB_LORAWAN_SESSION_BUF_SIZE);
#endif

    if (node == nullptr)
        node = new PicaroNode(&radio, &US915, PICARO_SUBBAND);

    uint64_t joinEUI = PICARO_JOIN_EUI;
    uint64_t devEUI  = PICARO_DEV_EUI;
    uint8_t  appKey[16] = PICARO_APP_KEY;

    /* nwkKey = NULL => LoRaWAN 1.0.x (solo AppKey). */
    int16_t st = node->beginOTAA(joinEUI, devEUI, NULL, appKey);
    if (st != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "beginOTAA fallo (%d)", st);
        return ESP_FAIL;
    }
    /* ADR DESACTIVADO: el experimento exige un datarate fijo y conocido; con ADR
     * la red lo cambiaria a mitad de corrida y las medidas dejarian de ser
     * comparables entre si. */
    node->setADR(false);

    uint8_t nonces[RADIOLIB_LORAWAN_NONCES_BUF_SIZE];
    if (nvs_load_blob(KEY_NONCES, nonces, sizeof(nonces))) {
        node->setBufferNonces(nonces);
#if !PICARO_FORCE_FRESH_JOIN
        uint8_t session[RADIOLIB_LORAWAN_SESSION_BUF_SIZE];
        if (nvs_load_blob(KEY_SESSION, session, sizeof(session)))
            node->setBufferSession(session);
#endif
        ESP_LOGI(TAG, "Nonces restaurados de NVS.");
    } else {
        ESP_LOGI(TAG, "Sin nonces guardados: primer join.");
    }

    s_prepared = true;
    return ESP_OK;
}

/* --- A-11: descarta el nodo entero y crea uno limpio con los MISMOS nonces.
 * Se llama con la radio en propiedad. Sin sesion: el siguiente activateOTAA()
 * sale por aire. Si los nonces no se pudieran restaurar, el DevNonce volveria a
 * 0 y el servidor rechazaria los joins por repetidos: se registra como error
 * pero se sigue, porque sin nodo la sonda tampoco uniria. --- */
static esp_err_t rearmar_nodo(void)
{
    uint8_t nonces[RADIOLIB_LORAWAN_NONCES_BUF_SIZE];
    memcpy(nonces, node->getBufferNonces(), sizeof(nonces));

    delete node;
    node = new PicaroNode(&radio, &US915, PICARO_SUBBAND);

    uint64_t joinEUI = PICARO_JOIN_EUI;
    uint64_t devEUI  = PICARO_DEV_EUI;
    uint8_t  appKey[16] = PICARO_APP_KEY;
    int16_t st = node->beginOTAA(joinEUI, devEUI, NULL, appKey);
    if (st != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "rearmar: beginOTAA fallo (%d)", st);
        return ESP_FAIL;
    }
    node->setADR(false);
    st = node->setBufferNonces(nonces);
    if (st != RADIOLIB_ERR_NONE)
        ESP_LOGE(TAG, "rearmar: setBufferNonces fallo (%d): el DevNonce reinicia", st);
    return ESP_OK;
}

/* --- UN solo activateOTAA(). Bloquea ~6-7 s (RX1 a rx1_delay, RX2). NO duerme
 * el backoff (lo decide quien llama) y NO aplica la corrida: eso lo hace el
 * bucle al arrancar (app_main), evitando ademas una carrera sobre s_sel. --- */
static lorawan_join_t lorawan_join_intento(void)
{
    if (!node) return LORAWAN_JOIN_FAIL;

#if PICARO_TEST_REV_CORRUPTO
    static bool corrompido = false;          /* una sola vez por arranque */
    if (!corrompido) {
        corrompido = true;
        node->corromper_rev();
        ESP_LOGW(TAG, "TEST A-11: rev forzada a 1 -> este JoinRequest debe dar Invalid MIC");
    }
#endif

    int16_t st = node->activateOTAA();
    nvs_save_blob(KEY_NONCES, node->getBufferNonces(), RADIOLIB_LORAWAN_NONCES_BUF_SIZE);

    if (st == RADIOLIB_LORAWAN_NEW_SESSION) {
        s_joined = true;
        nvs_save_blob(KEY_SESSION, node->getBufferSession(), RADIOLIB_LORAWAN_SESSION_BUF_SIZE);
        ESP_LOGI(TAG, "JOIN NUEVO por aire (JoinAccept recibido). Enlace REAL.");
        return LORAWAN_JOIN_NEW;
    }
    if (st == RADIOLIB_LORAWAN_SESSION_RESTORED) {
        s_joined = true;
        ESP_LOGW(TAG, "Sesion RESTAURADA de NVS. NO confirma gateway en rango; "
                      "el enlace se validara con un uplink confirmado.");
        return LORAWAN_JOIN_RESTORED;
    }
    ESP_LOGW(TAG, "  activateOTAA sin exito (codigo %d).", st);
    if (node->revision() != 0)
        ESP_LOGW(TAG, "  A-11: rev=%u tras el intento (JoinAccept ajena); se rearma el nodo",
                 (unsigned)node->revision());
    rearmar_nodo();
    return LORAWAN_JOIN_FAIL;
}

/* Conveniencia bloqueante (preparar + 3 intentos). app_main YA NO lo llama --usa
 * la tarea de fondo--; se conserva por si otro consumidor lo necesitara. */
lorawan_join_t lorawan_join(void)
{
    if (lorawan_join_preparar() != ESP_OK) return LORAWAN_JOIN_FAIL;
    for (int a = 1; a <= 3; a++) {
        ESP_LOGI(TAG, "activateOTAA intento #%d ...", a);
        lorawan_join_t r = lorawan_join_intento();
        if (r != LORAWAN_JOIN_FAIL) return r;
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
    ESP_LOGE(TAG, "No se logro unir (sin gateway en rango?).");
    return LORAWAN_JOIN_FAIL;
}

/* --- Descarta la sesion LoRaWAN para que el proximo activateOTAA salga por
 * aire de verdad. Se llama DENTRO de la tarea y CON la radio en propiedad: toca
 * el nodo, que es de la radio (mutex D-55). Los NONCES no se tocan a proposito
 * -- el DevNonce tiene que seguir creciendo o el servidor rechaza el
 * JoinRequest como repetido, y nos quedariamos sin poder unir. --- */
static void descartar_sesion(void)
{
    /* Rearmar, no clearSession(): este ultimo no restaura rev (A-11). */
    if (node) rearmar_nodo();
    s_joined = false;
    nvs_save_blob(KEY_SESSION, (const uint8_t[RADIOLIB_LORAWAN_SESSION_BUF_SIZE]){0},
                  RADIOLIB_LORAWAN_SESSION_BUF_SIZE);
    ESP_LOGW(TAG, "re-join: sesion descartada; el proximo join sera por aire");
}

/* --- La tarea de join en segundo plano (§4.2). Posee la radio SOLO mientras
 * une; suelta ANTES de marcar s_unido; se autodestruye al unir (recupera su
 * stack). Si nunca une, sigue reintentando: la sonda es operable mientras.
 * Desde D-62 tambien atiende los re-join: el bucle exterior la mantiene viva
 * si llega una peticion mientras estaba saliendo. --- */
static void tarea_join(void *_)
{
    (void)_;

    esp_err_t prep;                         /* setup reintentado si falla (MENOR-1-2p) */
    do {
        radio_tomar(RADIO_JOIN, portMAX_DELAY);
        prep = lorawan_join_preparar();     /* idempotente; bajo el mutex (MENOR-4) */
        radio_soltar(RADIO_JOIN);
        if (prep != ESP_OK) {
            ESP_LOGE(TAG, "preparar() fallo; reintento en 15 s");
            vTaskDelay(pdMS_TO_TICKS(15000));
        }
    } while (prep != ESP_OK);

    for (;;) {
        int intento = 0;
        while (!s_unido.load(std::memory_order_acquire)) {
            /* Consumir la peticion de re-join, si la hay, para descartar la
             * sesion en la MISMA toma de la radio que el intento que sigue. */
            bool rehacer;
            portENTER_CRITICAL(&s_rejoin_mux);
            rehacer = s_rejoin_pedido;
            s_rejoin_pedido = false;
            portEXIT_CRITICAL(&s_rejoin_mux);

            ESP_LOGI(TAG, "JOIN en segundo plano, intento #%d ...", ++intento);

            radio_tomar(RADIO_JOIN, portMAX_DELAY);
            if (rehacer) descartar_sesion();
            lorawan_join_t r = lorawan_join_intento();      /* ~6-7 s con la radio */
            bool ok = (r == LORAWAN_JOIN_NEW || r == LORAWAN_JOIN_RESTORED);
            radio_soltar(RADIO_JOIN);                        /* SOLTAR antes de marcar unido */

            if (ok) {
                /* release: ordena el xSemaphoreGive de arriba antes de que el bucle,
                 * con su load(acquire), vea s_unido y tome la radio libre (§6.2). */
                s_unido.store(true, std::memory_order_release);
                break;
            }

            /* Sin red: backoff SIN la radio, troceado para poder salir si unio
             * o si entra un re-join que haya que atender ya. */
            for (int t = 0; t < 15000 && !s_unido.load(std::memory_order_acquire); t += 200) {
                if (s_rejoin_pedido) break;
                vTaskDelay(pdMS_TO_TICKS(200));
            }
        }

        /* Salida coordinada con lorawan_rejoin(): marcar la tarea muerta y ver
         * si quedo una peticion pendiente ocurre bajo la MISMA seccion critica
         * que la anota, asi que no hay ventana en la que la peticion se pierda
         * ni en la que se creen dos tareas de join a la vez. */
        bool morir;
        portENTER_CRITICAL(&s_rejoin_mux);
        morir = !s_rejoin_pedido;
        if (morir) s_tarea_viva = false;
        portEXIT_CRITICAL(&s_rejoin_mux);
        if (morir) break;
        /* Hay peticion: quien la hizo ya puso s_unido a false, asi que el bucle
         * de intentos vuelve a entrar y la atiende sin recrear la tarea. */
    }

    ESP_LOGW(TAG, "enlace adquirido en segundo plano; la tarea de join termina");
    vTaskDelete(NULL);                       /* el mutex ya esta soltado: no queda huerfano */
}

void lorawan_iniciar_join_en_fondo(void)
{
    if (!s_radio_mtx) s_radio_mtx = xSemaphoreCreateMutex();
    s_unido.store(false, std::memory_order_release);
    portENTER_CRITICAL(&s_rejoin_mux);
    s_tarea_viva = true;              /* un re-join posterior NO crea otra tarea */
    portEXIT_CRITICAL(&s_rejoin_mux);
    /* Prioridad baja (2): por encima del bucle (1) para progresar en el arranque,
     * pero sin robar CPU a la UI. La correccion la da el mutex, no la prioridad. */
    xTaskCreate(tarea_join, "join", 8192, NULL, 2, NULL);
}

void lorawan_rejoin(void)
{
    if (!s_radio_mtx) s_radio_mtx = xSemaphoreCreateMutex();

    /* Soltar el enlace ANTES de anotar la peticion: cuando la tarea la vea,
     * s_unido ya es false con seguridad y su bucle de intentos entra sin
     * carrera. Ademas el menu, que republica al ver cambiar esta senal, pasa
     * a SIN_ENLACE de inmediato -- que es lo que la app espera para saber que
     * el re-join arranco. */
    s_unido.store(false, std::memory_order_release);

    bool lanzar = false;
    portENTER_CRITICAL(&s_rejoin_mux);
    s_rejoin_pedido = true;
    if (!s_tarea_viva) { s_tarea_viva = true; lanzar = true; }
    portEXIT_CRITICAL(&s_rejoin_mux);

    /* Si la tarea sigue viva basta con la anotacion: la consumira en su proximo
     * intento. Llamadas repetidas colapsan en un unico re-join. */
    if (lanzar)
        xTaskCreate(tarea_join, "join", 8192, NULL, 2, NULL);
}

bool lorawan_esta_unido(void)
{
    return s_unido.load(std::memory_order_acquire);
}

void radio_tomar_para_corrida(void) { radio_tomar(RADIO_BUCLE, portMAX_DELAY); }
void radio_soltar_de_corrida(void)  { radio_soltar(RADIO_BUCLE); }

int lorawan_send(const uint8_t *data, uint8_t len, uint8_t fport, bool confirmed)
{
    if (!s_joined) return -1;

    /* Se captura el downlink (no solo si LLEGO, sino QUE llego): el fPort
     * distingue un ping de latencia de un comando de corte, y el primer byte
     * es el numero de secuencia que permite emparejarlo con el log del
     * servidor. Sin esto la latencia no es medible. */
    uint8_t dl[64];
    size_t  dl_len = sizeof dl;
    LoRaWANEvent_t ev_dl = {};

    int16_t st = node->sendReceive(data, len, fport, dl, &dl_len, confirmed, NULL, &ev_dl);
    if (st > 0 && dl_len > 0) {
        s_dl_hay     = true;
        s_dl_fport   = ev_dl.fPort;
        s_dl_b0      = dl[0];
        s_dl_len     = dl_len;
        s_dl_ventana = ventana_desde_codigo(st);
        ESP_LOGI(TAG, "downlink en Rx%d: fPort=%u len=%u byte0=0x%02X",
                 st, (unsigned)ev_dl.fPort, (unsigned)dl_len, dl[0]);
    }
    if (st >= RADIOLIB_ERR_NONE) {
        nvs_save_blob(KEY_SESSION, node->getBufferSession(), RADIOLIB_LORAWAN_SESSION_BUF_SIZE);
        if (st > 0) ESP_LOGI(TAG, "Uplink%s OK + downlink/ACK en Rx%d (ENLACE CONFIRMADO)",
                             confirmed ? " confirmado" : "", st);
        else        ESP_LOGI(TAG, "Uplink enviado%s (sin downlink)%s",
                             confirmed ? " confirmado" : "",
                             confirmed ? " -> SIN ACK (no hay enlace)" : "");
        return st;
    }
    ESP_LOGE(TAG, "Uplink fallo (codigo %d)", st);
    return st;
}

bool lorawan_is_joined(void) { return s_joined; }

/* ===========================================================================
 *  Anadidos del experimento de pruebas de terreno
 * ========================================================================= */

void lorawan_aplicar_corrida(void)
{
    if (!node) return;

    const escenario_cfg_t *c = escenario_cfg();

    node->setADR(false);                 /* imprescindible: DR fijo */
    int16_t r = node->setDatarate(c->dr);
    if (r != RADIOLIB_ERR_NONE)
        ESP_LOGW(TAG, "setDatarate(%u) devolvio %d", (unsigned)c->dr, (int)r);

    const bool clase_c = (clase_actual() == CLASE_C);
    r = node->setClass(clase_c ? RADIOLIB_LORAWAN_CLASS_C : RADIOLIB_LORAWAN_CLASS_A);
    if (r != RADIOLIB_ERR_NONE)
        ESP_LOGW(TAG, "setClass(%c) devolvio %d", clase_c ? 'C' : 'A', (int)r);

    ESP_LOGI(TAG, "corrida aplicada: %s  DR%u/SF%u  Clase %c  fPort %u  ADR OFF",
             c->id, (unsigned)c->dr, (unsigned)c->sf,
             clase_c ? 'C' : 'A', (unsigned)escenario_fport());
}

bool lorawan_tomar_downlink(uint8_t *fport, uint8_t *primer_byte, size_t *len,
                            lorawan_ventana_t *ventana)
{
    if (!s_dl_hay) return false;
    if (fport)       *fport       = s_dl_fport;
    if (primer_byte) *primer_byte = s_dl_b0;
    if (len)         *len         = s_dl_len;
    if (ventana)     *ventana     = s_dl_ventana;
    s_dl_hay = false;                    /* se consume: no se reprocesa */
    return true;
}

void lorawan_sondear_clase_c(void)
{
    if (!node || !s_joined) return;
    if (clase_actual() != CLASE_C) return;   /* en Clase A no hay RXC */

    uint8_t dl[64];
    size_t  dl_len = sizeof dl;
    LoRaWANEvent_t ev = {};

    int16_t st = node->getDownlinkClassC(dl, &dl_len, &ev);
    if (st > 0 && dl_len > 0) {
        s_dl_hay     = true;
        s_dl_fport   = ev.fPort;
        s_dl_b0      = dl[0];
        s_dl_len     = dl_len;
        s_dl_ventana = ventana_desde_codigo(st);   /* RX_BC=3 -> rxc */
        ESP_LOGI(TAG, "downlink CLASE C: fPort=%u len=%u byte0=0x%02X",
                 (unsigned)ev.fPort, (unsigned)dl_len, dl[0]);
    }
}

uint32_t lorawan_fcnt_up(void)
{
    return node ? node->getFCntUp() : 0;
}
