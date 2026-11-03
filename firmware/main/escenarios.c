/**
 * ============================================================================
 *  escenarios.c  -  Seleccion de corrida con el boton BOOT, persistida en NVS
 * ============================================================================
 *
 *  Este modulo NO decide politica: solo lee el boton, mantiene el cursor de
 *  seleccion y lleva los contadores. Que hacer con cada evento -- navegar,
 *  arrancar, abortar -- lo decide el bucle de app_main.cpp, que es donde vive
 *  la maquina de estados MENU/CORRIDA/FIN.
 *
 *  La v2 anade una segunda fuente de mando, el BLE, y con ella una capa de
 *  traduccion (comando_tomar) que funde las dos en un solo comando pendiente.
 *  Sigue sin decidir politica: traduce gestos y ordenes a la misma moneda para
 *  que la maquina de estados no tenga que saber por donde entro la orden.
 * ============================================================================
 */
#include "escenarios.h"
#include "ble_control.h"
#include "board_pins.h"
#include "gps_l76k.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "nvs.h"

#include <stdio.h>
#include <string.h>

static const char *TAG = "escenarios";

#define NVS_NS   "picaro_exp"
#define KEY_SEL  "sel"

/* ---------------------------------------------------------------------------
 *  La tabla. Unica fuente de verdad de DR, intervalo y fPort.
 *
 *  URBANO y TERRAZA usan DR1/SF9 y DR3/SF7 respectivamente: ahi el objetivo es
 *  cobertura, no alcance, y el payload extendido (con bateria) cabe de sobra.
 *
 *  CERRO16 usa DR0/SF10 porque el objetivo declarado es DEMOSTRAR EL ALCANCE
 *  MAXIMO, y en US915 no hay nada por debajo de SF10 para uplink. El precio es
 *  el limite de 11 bytes: la bateria no cabe y se queda solo en el log de la
 *  microSD.
 * ------------------------------------------------------------------------- */
const escenario_cfg_t ESCENARIOS[ESC_COUNT] = {
    [ESC_URBANO] = {
        .id = "URBANO", .descripcion = "terreno movil urbano (vehiculo 30-40 km/h)",
        .dr = 1, .sf = 9, .intervalo_ms = 8000, .uplinks_objetivo = 300,
        .fport = {11, 12}, .payload_extendido = true,
    },
    [ESC_TERRAZA] = {
        .id = "TERRAZA", .descripcion = "terraza piso 5, exterior, LoS a 2,74 km",
        .dr = 3, .sf = 7, .intervalo_ms = 8000, .uplinks_objetivo = 300,
        .fport = {13, 14}, .payload_extendido = true,
    },
    [ESC_CERRO] = {
        .id = "CERRO16", .descripcion = "Cerro del Muerto, LoS a 16,35 km",
        .dr = 0, .sf = 10, .intervalo_ms = 8000, .uplinks_objetivo = 300,
        .fport = {15, 16}, .payload_extendido = false,
    },
    /* VUELO (D-64, docs/VUELO-ESPEC.md): simula la telemetria de la capsula.
     * Una lectura completa por minuto, repartida en 3 paquetes de 11 bytes que
     * salen cada 20 s (P1 posicion, P2 ambiente, P3 navegacion). 55 rafagas =
     * 55 minutos de vuelo. Solo clase A: el fPort de C queda a 0 y no hay
     * entrada en CORRIDAS que lo use. */
    [ESC_VUELO] = {
        .id = "VUELO", .descripcion = "telemetria de capsula, puntos fijos",
        .dr = 0, .sf = 10, .intervalo_ms = 20000, .uplinks_objetivo = 165,
        .fport = {17, 0}, .payload_extendido = false, .paquetes_rafaga = 3,
    },
};

const corrida_def_t CORRIDAS[CORRIDAS_COUNT] = {
    { ESC_URBANO,  CLASE_A }, { ESC_URBANO,  CLASE_C },
    { ESC_TERRAZA, CLASE_A }, { ESC_TERRAZA, CLASE_C },
    { ESC_CERRO,   CLASE_A }, { ESC_CERRO,   CLASE_C },
    { ESC_VUELO,   CLASE_A },
};

/* Cursor del menu: 0..6. El escenario y la clase se derivan de el, asi no hay
 * dos variables que puedan quedar descoordinadas. */
static uint8_t  s_sel;
static uint16_t s_enviados, s_ok;

/* --- Persistencia -------------------------------------------------------- */

static void guardar(void)
{
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) != ESP_OK) return;
    nvs_set_u8(h, KEY_SEL, s_sel);
    nvs_commit(h);
    nvs_close(h);
}

static void cargar(void)
{
    /* Al venir del firmware anterior (que guardaba escenario y clase por
     * separado) esta clave no existe y se arranca en URBANO-A. Es inocuo: con
     * el menu, la corrida SIEMPRE se elige y confirma a mano antes de arrancar,
     * asi que un valor inicial distinto no puede colarse en una medida. */
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) != ESP_OK) return;
    uint8_t v;
    if (nvs_get_u8(h, KEY_SEL, &v) == ESP_OK && v < CORRIDAS_COUNT) s_sel = v;
    nvs_close(h);
}

/* --- Boton --------------------------------------------------------------- */
/* El BOOT del T-Beam Supreme es activo en BAJO con pull-up interno. */

#define BTN_ANTIRREBOTE_MS   40
#define BTN_LARGA_MS       2000
#define BTN_DOBLE_MS        400

#define BTN_PULSADO()  (gpio_get_level((gpio_num_t)BOOT_BUTTON_PIN) == 0)

static QueueHandle_t s_evt_q;

static void emitir(boton_evt_t e)
{
    if (s_evt_q) xQueueSend(s_evt_q, &e, 0);
}

boton_evt_t boton_tomar(void)
{
    boton_evt_t e = BTN_NINGUNO;
    if (s_evt_q) xQueueReceive(s_evt_q, &e, 0);
    return e;
}

/* Sondeo, no interrupcion: distinguir pulsacion larga de doble exige medir
 * tiempos entre flancos, y hacerlo en una ISR obliga a temporizadores extra
 * sin ganar nada. A 20 ms de periodo el coste es despreciable.
 *
 * OJO CON LA LATENCIA DEL CLIC CORTO: para saber que una pulsacion NO es la
 * primera de una doble hay que esperar a que venza la ventana de 400 ms. Por
 * eso BTN_CORTO se emite al soltar MAS 400 ms, y el menu avanza con ese
 * retardo. Es inherente a tener dos gestos sobre un solo boton, no un fallo. */
static void boton_task(void *arg)
{
    bool    anterior = false;
    int64_t t_pulsa = 0, t_suelta = 0;
    int     clics = 0;
    bool    larga_emitida = false;

    for (;;) {
        bool ahora = BTN_PULSADO();
        int64_t t  = esp_timer_get_time() / 1000;

        if (ahora && !anterior) {                       /* flanco de bajada */
            if (t - t_suelta > BTN_ANTIRREBOTE_MS) { t_pulsa = t; larga_emitida = false; }
        } else if (ahora && anterior) {                 /* mantenido */
            /* Se emite al cumplirse los 2 s, sin esperar a que suelte: asi el
             * operador ve la reaccion en la pantalla y sabe que ya puede
             * soltar, en vez de adivinar cuanto lleva apretando. */
            if (!larga_emitida && (t - t_pulsa) >= BTN_LARGA_MS) {
                emitir(BTN_LARGO); larga_emitida = true; clics = 0;
            }
        } else if (!ahora && anterior) {                /* flanco de subida */
            t_suelta = t;
            if (!larga_emitida && (t - t_pulsa) > BTN_ANTIRREBOTE_MS) {
                if (++clics >= 2) { emitir(BTN_DOBLE); clics = 0; }
            }
        } else {                                        /* reposo */
            if (clics == 1 && (t - t_suelta) > BTN_DOBLE_MS) {
                emitir(BTN_CORTO); clics = 0;
            }
        }

        anterior = ahora;
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

/* --- Entrada unificada: boton O BLE -------------------------------------- */

/* La tabla de gestos de la v1, escrita de una vez en vez de repartida por los
 * bucles de app_main.cpp. Cada fila es literalmente lo que ya se hacia; las
 * unicas dos entradas nuevas son las de CTX_EMPAREJADO, que es un estado que
 * en la v1 no existia, y la larga del menu (RF-11), que en la v1 se ignoraba
 * explicitamente ("BTN_LARGO se ignora: ya estamos en el menu").
 *
 * Devolver CMD_NINGUNO es la forma de DESCARTAR un gesto, y es tan importante
 * como traducirlo: durante una corrida el corto y el doble tienen que seguir
 * sin significar nada, para que un roce del boton no arruine una medida de 40
 * minutos. */
static cmd_tipo_t mapear_boton(contexto_t ctx, boton_evt_t e)
{
    switch (ctx) {
    case CTX_MENU:
        if (e == BTN_CORTO) return CMD_SIGUIENTE;
        if (e == BTN_DOBLE) return CMD_ARRANCAR;
        if (e == BTN_LARGO) return CMD_EMPAREJAR;   /* RF-11: el hueco libre */
        break;

    case CTX_CORRIDA:
        /* corto y doble se DESCARTAN a proposito (regla de la v1). */
        if (e == BTN_LARGO) return CMD_ABORTAR;
        break;

    case CTX_FIN:
        /* Desde FIN el boton solo sabe volver al menu: no sabe decir "arranca
         * la 3". Por eso la larga sigue siendo obligatoria aqui aunque el BLE
         * si pueda arrancar directamente (contrato §5.3, punto 2). */
        if (e == BTN_LARGO) return CMD_ABORTAR;
        break;

    case CTX_EMPAREJADO:
        /* RF-10, y es CRITICO: sin esta salida, un telefono muerto o sin la
         * app inutilizaria el respaldo por boton y se perderia la salida de
         * campo. La larga hace lo mismo que la corta porque la regla que se
         * enseña en campo es "larga = ir al menu, siempre", y este no es sitio
         * para una excepcion: es justo el estado donde el operador ya esta
         * nervioso porque algo no le funciona. */
        if (e == BTN_CORTO || e == BTN_LARGO) return CMD_ABORTAR;
        /* La doble conserva su significado de siempre: el acto deliberado e
         * irreversible de este estado. Aqui es olvidar todos los telefonos. */
        if (e == BTN_DOBLE) return CMD_BORRAR_BONDS;
        break;

    case CTX_ESPERANDO:
        /* Espera de enlace (C-Fondo, D2=A). SOLO la larga aborta y vuelve al
         * menu -- coherente con "larga = ir al menu, siempre" y con CTX_CORRIDA.
         * Corta y doble se DESCARTAN (MENOR-3-2p): en la espera el OLED solo
         * anuncia "larga = abortar", y la corta no significa nada fuera del menu. */
        if (e == BTN_LARGO) return CMD_ABORTAR;
        break;
    }
    return CMD_NINGUNO;
}

bool comando_tomar(contexto_t ctx, cmd_t *out)
{
    if (!out) return false;

    out->tipo      = CMD_NINGUNO;
    out->modo      = 0;
    out->trae_modo = false;
    out->de_ble    = false;

    /* El BOTON PRIMERO, y no es indiferente: es el respaldo, y en un empate
     * tiene que ganar el que esta fisicamente delante de la sonda. Un comando
     * BLE que no se atienda en esta vuelta no se pierde -- sigue pendiente y
     * se recoge en la siguiente, 50 o 200 ms despues. */
    boton_evt_t e = boton_tomar();
    if (e != BTN_NINGUNO) {
        out->tipo = mapear_boton(ctx, e);
        if (out->tipo != CMD_NINGUNO) return true;
        /* Gesto sin significado en este contexto: consumido y descartado. Se
         * sigue mirando el BLE, que es una fuente independiente. */
    }

    /* En EMPAREJADO no se atiende NADA por BLE. El GATT ya rechaza todos los
     * comandos en ese estado (contrato §5.3), asi que esto es solo el segundo
     * cerrojo: que la ventana de emparejamiento no se pueda cerrar por radio,
     * sino unicamente con el dedo. */
    if (ctx == CTX_EMPAREJADO) return false;

    ble_cmd_t b;
    if (ble_tomar_comando(&b)) {
        switch (b.tipo) {
        case BLE_CMD_SELECCIONAR:
            /* Seleccionar ES arrancar (RF-4): equivale exactamente a la doble
             * pulsacion, solo que diciendo ademas cual. */
            out->tipo      = CMD_ARRANCAR;
            out->modo      = b.modo;
            out->trae_modo = true;
            break;
        case BLE_CMD_ABORTAR:
            out->tipo = CMD_ABORTAR;
            break;
        case BLE_CMD_REJOIN:
            /* Solo significa algo en el menu (CONFIG/SIN_ENLACE, contrato
             * Addendum B). El GATT ya lo rechaza en los demas estados; si aun
             * asi llegara aqui en otro contexto -- p. ej. el boton arranco una
             * corrida antes de que el bucle consumiera el comando --, se
             * descarta en silencio, con el mismo criterio que el roce del
             * boton: un re-join no puede tumbar una medida en marcha. */
            if (ctx == CTX_MENU) out->tipo = CMD_REJOIN;
            break;
        default:
            break;
        }
        if (out->tipo != CMD_NINGUNO) {
            out->de_ble = true;
            return true;
        }
    }

    return false;
}

/* --- API ----------------------------------------------------------------- */

void escenarios_init(void)
{
    cargar();

    gpio_config_t in = {
        .pin_bit_mask = 1ULL << BOOT_BUTTON_PIN,
        .mode         = GPIO_MODE_INPUT,
        .pull_up_en   = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    gpio_config(&in);

    s_evt_q = xQueueCreate(4, sizeof(boton_evt_t));
    xTaskCreate(boton_task, "boton", 2560, NULL, 4, NULL);

    const escenario_cfg_t *c = escenario_cfg();
    ESP_LOGI(TAG, "seleccion guardada: %s Clase %c  SF%u/DR%u  %.1fs  fPort %u",
             c->id, clase_actual() == CLASE_C ? 'C' : 'A',
             (unsigned)c->sf, (unsigned)c->dr, c->intervalo_ms / 1000.0f,
             (unsigned)escenario_fport());
    ESP_LOGI(TAG, "boton BOOT: corto = siguiente opcion · doble = ARRANCAR · larga = menu");
}

uint8_t     seleccion_indice(void) { return s_sel; }
escenario_t escenario_actual(void) { return CORRIDAS[s_sel].esc; }
clase_t     clase_actual(void)     { return CORRIDAS[s_sel].clase; }

const escenario_cfg_t *escenario_cfg(void) { return &ESCENARIOS[escenario_actual()]; }

uint8_t escenario_fport(void) { return escenario_cfg()->fport[clase_actual()]; }

void seleccion_siguiente(void)
{
    s_sel = (uint8_t)((s_sel + 1u) % CORRIDAS_COUNT);
    const escenario_cfg_t *c = escenario_cfg();
    ESP_LOGI(TAG, "menu -> %s Clase %c  SF%u/DR%u  fPort %u",
             c->id, clase_actual() == CLASE_C ? 'C' : 'A',
             (unsigned)c->sf, (unsigned)c->dr, (unsigned)escenario_fport());
}

void seleccion_fijar(uint8_t idx)
{
    /* La validacion vive AQUI y no en quien llama. El indice viene del aire
     * (lo escribe la app en la caracteristica Comando) y aunque el GATT ya lo
     * valida, s_sel tiene una sola puerta y esa puerta comprueba. Un valor
     * imposible se ignora dejando la seleccion anterior intacta: es mejor
     * arrancar la corrida equivocada -- que el operador ve en el OLED antes de
     * que salga el primer uplink -- que quedarse con un escenario fuera de la
     * tabla y leer memoria que no toca. */
    if (idx >= CORRIDAS_COUNT) {
        ESP_LOGE(TAG, "seleccion_fijar(%u) fuera de rango: se ignora", (unsigned)idx);
        return;
    }
    if (idx == s_sel) return;

    s_sel = idx;
    const escenario_cfg_t *c = escenario_cfg();
    ESP_LOGI(TAG, "seleccion -> %s Clase %c  SF%u/DR%u  fPort %u",
             c->id, clase_actual() == CLASE_C ? 'C' : 'A',
             (unsigned)c->sf, (unsigned)c->dr, (unsigned)escenario_fport());
}

void corrida_confirmar(void)
{
    corrida_reiniciar();
    guardar();
    const escenario_cfg_t *c = escenario_cfg();
    ESP_LOGW(TAG, "CONFIRMADA: %s Clase %c  SF%u/DR%u  %.1fs  fPort %u  (%u uplinks)",
             c->id, clase_actual() == CLASE_C ? 'C' : 'A',
             (unsigned)c->sf, (unsigned)c->dr, c->intervalo_ms / 1000.0f,
             (unsigned)escenario_fport(), (unsigned)c->uplinks_objetivo);
}

const char *escenario_run_id_base(char *buf, size_t len)
{
    /* Fecha UTC del GPS si hay fix. Sin fix se usa 00000000: el analisis
     * detecta esas corridas y el operador puede renombrarlas con la hoja de
     * campo, que si lleva la fecha real. */
    char fecha[9] = "00000000";
    gps_fix_t f;
    if (gps_get(&f) && f.valid && f.utc_year >= 2020) {
        snprintf(fecha, sizeof fecha, "%04u%02u%02u",
                 (unsigned)(f.utc_year  % 10000u),
                 (unsigned)(f.utc_month % 100u),
                 (unsigned)(f.utc_day   % 100u));
    }
    snprintf(buf, len, "%s-%s-%c", fecha, escenario_cfg()->id,
             clase_actual() == CLASE_C ? 'C' : 'A');
    return buf;
}

/* --- Progreso ------------------------------------------------------------ */

uint16_t corrida_uplinks_enviados(void) { return s_enviados; }
uint16_t corrida_uplinks_ok(void)       { return s_ok; }

bool corrida_completa(void)
{
    return s_enviados >= escenario_cfg()->uplinks_objetivo;
}

void corrida_registrar_tx(bool ok)
{
    if (s_enviados < UINT16_MAX) s_enviados++;
    if (ok && s_ok < UINT16_MAX) s_ok++;
}

void corrida_reiniciar(void) { s_enviados = 0; s_ok = 0; }
