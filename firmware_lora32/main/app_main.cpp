/**
 * ============================================================================
 *  app_main.cpp  -  Sonda T3 v1.6.1 (LoRa32) · campana de PRUEBAS DE TERRENO
 * ============================================================================
 *
 *  Copia de ../../firmware/main/app_main.cpp (T-Beam Supreme) con los cambios
 *  minimos que pide la placa: sin PMU, OLED SSD1306, y GPS/BME280/
 *  magnetometro SIMULADOS en telemetry.c (simulacion.h). El payload es el de
 *  la T-Beam: los P1/P2/P3 de VUELO salen igual, con valores simulados.
 *  La maquina de estados, el BLE, el join en fondo, el runlog y la atencion
 *  de downlinks son los de la T-Beam, sin tocar: la app y el microservicio
 *  solo distinguen una sonda de otra por su DevEUI.
 *
 *  MAQUINA DE ESTADOS
 *  ------------------
 *      arranque -> JOIN -> [EMPAREJADO] -> MENU
 *
 *      MENU     parpadea la linea de seleccion. NO transmite, NO reconfigura la
 *               radio, NO toca contadores. Solo mueve un cursor.
 *                 corto -> siguiente de las 6 opciones
 *                 doble -> confirma y ARRANCA la corrida
 *                 larga -> abre la ventana de emparejamiento (v2, RF-11)
 *      CORRIDA  transmite. corto y doble se IGNORAN (un roce no debe alterar
 *               una medida en marcha).
 *                 larga -> aborta y vuelve al MENU
 *      FIN      corrida completa: FINALIZADO fijo, sin transmitir.
 *                 larga -> vuelve al MENU
 *
 *  LO QUE ANADE LA v2 (CR-v2 + equipo/CONTRATO-BLE.md), y lo que NO
 *  --------------------------------------------------------------
 *  Anade: (1) el BLE como segunda fuente de mando, fundida con el boton en
 *  comando_tomar(); (2) el estado EMPAREJADO, con pantalla propia; (3) la
 *  publicacion del estado por BLE en cada transicion, que es el ACK.
 *
 *  NO cambia: el OLED de corrida, el OLED de configuracion, el LED (parpadea
 *  ⇔ estas en el menu) ni lo que hace cada gesto del boton alli donde ya
 *  significaba algo. El boton es el RESPALDO (RF-8) y no depende de la app:
 *  con el movil muerto, la sonda se opera exactamente igual que en la v1. La
 *  unica pantalla nueva es la de EMPAREJADO, que es un estado nuevo y no una
 *  linea añadida a una pantalla que ya existia.
 *
 *  El join va ANTES del menu a proposito: puede tardar y reintentar, y asi
 *  ocurre mientras se monta el equipo. Cuando el operador confirma, el primer
 *  uplink sale en el acto en vez de tras una espera de duracion imprevisible.
 *
 *  Diferencias con el ej.09:
 *    - escenarios.h decide DR, intervalo, fPort, clase y numero de uplinks
 *    - payload de 11/14 bytes little-endian (payload_terreno.h)
 *    - CSV por corrida en la microSD (runlog.h)
 *    - ADR desactivado y datarate fijo
 *    - se atienden downlinks de ping/corte y se registran con marca UTC
 * ============================================================================
 */
#include <cstdio>
#include <cstring>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_chip_info.h"
#include "esp_idf_version.h"
#include "esp_timer.h"
#include "nvs_flash.h"

#include "board_pins.h"
#include "config_lorawan.h"
#include "sensores_config.h"
#include "pmu_t3.h"
#include "i2c0.h"
#include "radio.h"
#include "lorawan.h"
#include "telemetry.h"
#include "gps_l76k.h"      /* tipos; la T3 no tiene GPS (gps_ninguno.c) */
#include "oled_ssd1306.h"
#include "sdcard.h"

#include "escenarios.h"
#include "payload_terreno.h"
#include "runlog.h"
#include "ble_control.h"   /* v2: servidor GATT de control (contrato §9.2) */

#include "esp_heap_caps.h"

static const char *TAG = "picaro";

/* Ultimo downlink recibido, para la linea fija del OLED. Sin actuador ni LED,
 * esa linea es la UNICA confirmacion visual en campo de que un comando llego.
 * El numero es la secuencia que puso el servidor, asi que el asistente puede
 * cotejarla contra el log del pinger sin esperar a descargar la microSD. */
static char    s_dl_txt[24] = {0};
static int64_t s_dl_us      = 0;

/* Ultima telemetria leida. La pantalla de FIN la necesita para no quedarse con
 * las lineas de GPS y bateria en blanco cuando ya no se esta midiendo. */
static telemetry_t s_tel;
static bool        s_tel_valida = false;

static void nvs_bootstrap(void)
{
    esp_err_t r = nvs_flash_init();
    if (r == ESP_ERR_NVS_NO_FREE_PAGES || r == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }
}

/* Heap interno libre, con etiqueta para comparar antes/despues en el monitor.
 * Heredado del spike de la Fase 0, que era quien lo imprimia: el spike se borra
 * pero el numero se sigue necesitando, porque es el criterio de aceptacion de
 * RNF-1 (>= 180 000 B libres y >= 140 000 B de bloque mayor tras el JOIN).
 *
 * MALLOC_CAP_INTERNAL a proposito: la PSRAM esta desactivada, asi que lo unico
 * que cuenta es la SRAM interna. El bloque mayor importa tanto como el total:
 * la fragmentacion mata igual que el agotamiento. */
static void log_heap(const char *cuando)
{
    ESP_LOGW(TAG, "HEAP %-10s libre=%u B  min_historico=%u B  bloque_mayor=%u B",
             cuando,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL));
}

/* El firmware NO puede cambiar el device profile del servidor: elegir Clase C
 * aqui no sirve de nada si ChirpStack tiene el device en el perfil de Clase A,
 * porque entonces no encolara el downlink inmediato y el resultado se parecera
 * mucho a "la Clase C no funciona". Se muestra en el menu para que el operador
 * lo verifique ANTES de arrancar, que es el unico momento en que puede. */
static const char *perfil_requerido(void)
{
    return (clase_actual() == CLASE_C) ? "terreno-c" : "terreno-a";
}

/* Publica el estado del menu segun haya enlace LoRa o no (C-Fondo, Addendum
 * A.4). SIN_ENLACE y CONFIG son los dos "menu operable"; la app habilita el
 * selector en los dos y muestra el enlace como indicador aparte, no como
 * bloqueo. La transicion SIN_ENLACE->CONFIG la hace la sonda sola al unir. */
static void publicar_menu(void)
{
    ble_publicar_estado(seleccion_indice(),
        lorawan_esta_unido() ? BLE_ESTADO_CONFIG : BLE_ESTADO_SIN_ENLACE);
}

/* --------------------------------------------------------------------------
 *  Pantallas
 * ------------------------------------------------------------------------ */

/* Estado de una corrida (en marcha o terminada). Se llama TAMBIEN mientras se
 * intenta el join: una pantalla en negro durante el join es indistinguible de
 * una placa muerta, y en campo esa confusion cuesta un viaje. */
static void oled_corrida(const telemetry_t *t, const char *linea_estado,
                         const char *pie)
{
#if USE_OLED
    const escenario_cfg_t *c = escenario_cfg();
    char l[32];

    snprintf(l, sizeof l, "%-7s SF%u/DR%u %c", c->id,
             (unsigned)c->sf, (unsigned)c->dr,
             clase_actual() == CLASE_C ? 'C' : 'A');
    oled_line(0, l);

    snprintf(l, sizeof l, "fPort %-3u %.1fs", (unsigned)escenario_fport(),
             c->intervalo_ms / 1000.0f);
    oled_line(1, l);

    oled_line(2, linea_estado ? linea_estado : "");

    snprintf(l, sizeof l, "TX %u/%u OK %u",
             (unsigned)corrida_uplinks_enviados(),
             (unsigned)c->uplinks_objetivo,
             (unsigned)corrida_uplinks_ok());
    oled_line(3, l);

    if (t) {
        /* Linea 4: en la T-Beam es el GPS. La T3 no tiene: su posicion y su
         * ambiente son simulados (simulacion.h), y la pantalla lo dice. */
        snprintf(l, sizeof l, "Sensores SIMULADOS");
        oled_line(4, l);
        /* Porcentaje > 100 = lectura del gauge no disponible: se muestra "--"
         * en vez de "255%". Los mV son lectura directa del ADC y van siempre. */
        if (t->batt_pct > 100)
            snprintf(l, sizeof l, "Bat -- %umV", (unsigned)t->batt_mv);
        else
            snprintf(l, sizeof l, "Bat %u%% %umV",
                     (unsigned)t->batt_pct, (unsigned)t->batt_mv);
        oled_line(5, l);
    }

    /* Linea 6: ultimo downlink recibido y hace cuanto. Persistente. */
    if (s_dl_txt[0]) {
        long s = (long)((esp_timer_get_time() - s_dl_us) / 1000000);
        if (s < 600) snprintf(l, sizeof l, "%.15s %us", s_dl_txt, (unsigned)s);
        else         snprintf(l, sizeof l, "%.15s +10m", s_dl_txt);
    } else {
        snprintf(l, sizeof l, "DL --");
    }
    oled_line(6, l);

    oled_line(7, pie ? pie : "");
#else
    (void)t; (void)linea_estado; (void)pie;
#endif
}

/* Menu: todo lo que NO parpadea. Cambia al mover el cursor, porque el DR, el
 * fPort y el perfil requerido dependen de la opcion elegida. */
static void oled_menu_fijo(void)
{
#if USE_OLED
    const escenario_cfg_t *c = escenario_cfg();
    char l[32];

    oled_line(0, "ELIGE CORRIDA");
    /* Linea 1 (libre en la v1): indicador de enlace. No roba ninguna linea util
     * -- estaba en blanco -- y es lo unico que la pantalla del menu gana. */
    oled_line(1, lorawan_esta_unido() ? "Enlace: OK" : "Enlace: uniendo...");

    snprintf(l, sizeof l, "SF%u/DR%u fPort %u",
             (unsigned)c->sf, (unsigned)c->dr, (unsigned)escenario_fport());
    oled_line(3, l);

    snprintf(l, sizeof l, "%.1fs x %u uplinks",
             c->intervalo_ms / 1000.0f, (unsigned)c->uplinks_objetivo);
    oled_line(4, l);

    snprintf(l, sizeof l, "Perfil: %s", perfil_requerido());
    oled_line(5, l);

    oled_line(6, "elige y arranca");
    oled_line(7, "desde la app");
#endif
}

/* Menu: la linea que parpadea. Es la unica que se repinta al parpadear, asi el
 * bus I2C no repinta ocho lineas dos veces por segundo sin necesidad. */
static void oled_menu_cursor(bool visible)
{
#if USE_OLED
    if (!visible) { oled_line(2, ""); return; }
    char l[32];
    snprintf(l, sizeof l, "> %-7s Clase %c", escenario_cfg()->id,
             clase_actual() == CLASE_C ? 'C' : 'A');
    oled_line(2, l);
#else
    (void)visible;
#endif
}

/* Pantalla del estado EMPAREJADO (v2). Es la UNICA pantalla nueva: las de
 * configuracion y corrida quedan EXACTAMENTE como en la v1, y por eso el
 * numero tiene un estado propio en vez de una linea prestada -- en el menu las
 * 8 lineas ya estan llenas y todas son utiles.
 *
 * Va en TRES FASES porque no puede ser estatica: el passkey no existe hasta que
 * un telefono conecta e inicia el emparejamiento (contrato §7.2). Al entrar
 * todavia no hay ningun numero que enseñar, y una pantalla que enseñara uno
 * seria mentira.
 *
 * Limpia a proposito: sin bateria, sin GPS, sin modo, sin contadores. Lo unico
 * que se hace aqui es leer seis digitos y teclearlos en el movil.
 *
 * La linea 7 anuncia la salida de emergencia (RF-10) y NO anuncia el borrado de
 * bonds (la doble): una salida de emergencia sin señalizar no es una salida de
 * emergencia, y una accion destructiva señalizada es una invitacion a probarla
 * "a ver que hace". */
static void oled_emparejado(ble_emp_fase_t fase, uint32_t passkey, uint16_t motivo)
{
#if USE_OLED
    char l[32];

    oled_line(0, "EMPAREJA LA APP");
    oled_line(1, "");
    oled_line(2, "");
    oled_line(4, "");
    oled_line(5, "");
    oled_line(6, "");

    switch (fase) {
    case BLE_EMP_PASSKEY:
        /* %06lu, NO %lu. Si el passkey sale 12345, el dialogo de Android espera
         * SEIS caracteres, "012345". Imprimir cinco hace que el operador teclee
         * de menos y el emparejamiento falle con st=1028, que es exactamente lo
         * mismo que se ve al teclearlo mal: ocurriria en uno de cada diez
         * emparejamientos, al azar, y se le echaria la culpa al operador. */
        snprintf(l, sizeof l, "CODIGO  %06lu", (unsigned long)passkey);
        oled_line(3, l);
        oled_line(7, "teclealo en el movil");
        break;

    case BLE_EMP_FALLO:
        oled_line(3, "FALLO DE EMPAREJADO");
        /* 1028 = BLE_HS_ERR_SM_US_BASE + 4, "Confirm Value Failed". En la
         * practica significa una sola cosa, es la que mas veces pasara en campo
         * y es la unica que el operador puede arreglar el solo, asi que se
         * traduce. Lo demas se muestra en crudo, que es lo util para depurar. */
        if (motivo == 1028) {
            oled_line(4, "codigo mal tecleado");
        } else {
            snprintf(l, sizeof l, "st=%u", (unsigned)motivo);
            oled_line(4, l);
        }
        oled_line(7, "reintenta en la app");
        break;

    case BLE_EMP_ESPERANDO:
    default:
        oled_line(3, "Conecta desde la app");
        oled_line(7, "(sonda sin boton)");
        break;
    }
#else
    (void)fase; (void)passkey; (void)motivo;
#endif
}

/* --------------------------------------------------------------------------
 *  Downlinks
 * ------------------------------------------------------------------------ */

/* Texto de la columna `ventana` del _dl.csv. Cualquier valor no contemplado se
 * registra como "desconocida": mejor eso que inventar una ventana. */
static const char *ventana_txt(lorawan_ventana_t v)
{
    switch (v) {
    case LORAWAN_VENTANA_RX1: return "rx1";
    case LORAWAN_VENTANA_RX2: return "rx2";
    case LORAWAN_VENTANA_RXC: return "rxc";
    default:                  return "desconocida";
    }
}

/* Atiende un downlink si lo hubo. No hay actuador fisico: solo se registra con
 * su marca de tiempo, que es lo unico que necesita la medida de latencia. */
static void atender_downlink(const char *run_id)
{
    uint8_t fport = 0, b0 = 0;
    size_t  len = 0;
    lorawan_ventana_t vent = LORAWAN_VENTANA_DESCONOCIDA;
    if (!lorawan_tomar_downlink(&fport, &b0, &len, &vent)) return;

    /* Hora FRESCA capturada AQUI, al consumir el downlink. Reutilizar el utc
     * del inicio del ciclo hacia que dos downlinks del mismo ciclo (p. ej. el
     * de la ventana RX y uno de Clase C durante la espera) compartieran
     * timestamp, y la latencia dejaba de ser medible (visto en campo). */
    gps_fix_t gf;
    gps_get(&gf);
    const char *utc = gf.time_valid ? gf.utc_iso : "";

    const char *accion;
    char l[24];

    if (fport == 98) {
        accion = "ping";
        ESP_LOGW(TAG, ">>> PING de latencia seq=%u", (unsigned)b0);
        snprintf(l, sizeof l, "DL ping #%u", (unsigned)b0);
    } else if (fport == 99 && b0 == 0xA5) {
        accion = "corte";
        ESP_LOGW(TAG, ">>> COMANDO DE CORTE (sin actuador: solo se registra)");
        snprintf(l, sizeof l, "DL CORTE #%u", (unsigned)b0);
    } else {
        /* Se registra igual: un downlink inesperado es informacion, y callarlo
         * dificultaria diagnosticar por que no llego el que se esperaba. */
        accion = "ignorado";
        ESP_LOGW(TAG, ">>> downlink ignorado fPort=%u byte0=0x%02X",
                 (unsigned)fport, (unsigned)b0);
        snprintf(l, sizeof l, "DL ? fP%u", (unsigned)fport);
    }

    runlog_downlink(run_id, utc, fport, b0, accion, ventana_txt(vent));

    /* Se guarda en vez de pintarlo aqui: la linea 2 la reescribe el siguiente
     * refresco de estado y el aviso desaparecia en menos de un segundo. */
    snprintf(s_dl_txt, sizeof s_dl_txt, "%s", l);
    s_dl_us = esp_timer_get_time();
}

/* Un downlink que llego mientras el operador estaba en el menu pertenece a la
 * corrida ANTERIOR. Si se dejara en el buffer, se consumiria en el primer ciclo
 * de la siguiente y quedaria registrado con el run_id equivocado, falseando una
 * medida de latencia. Se descarta explicitamente y se deja constancia. */
static void descartar_downlink_pendiente(void)
{
    uint8_t fport = 0, b0 = 0;
    size_t  len = 0;
    while (lorawan_tomar_downlink(&fport, &b0, &len, NULL)) {
        ESP_LOGW(TAG, "descartado downlink previo a la corrida "
                      "(fPort=%u byte0=0x%02X): no pertenece a esta medida",
                 (unsigned)fport, (unsigned)b0);
    }
}

/* --------------------------------------------------------------------------
 *  Estados
 * ------------------------------------------------------------------------ */

/* true si se pidio abortar la corrida en marcha. Consume el comando pendiente.
 *
 * En corrida, corto y doble se DESCARTAN a proposito -- lo hace la tabla de
 * comando_tomar() -- : la unica entrada al menu por boton es una pulsacion
 * larga deliberada, para que un roce no pueda arruinar una corrida de 40
 * minutos. Un "seleccionar" por BLE tampoco deberia llegar hasta aqui (el GATT
 * lo rechaza con 0x84 mientras se esta CORRIENDO, porque cambiar de modo a
 * mitad de una corrida mezclaria dos escenarios bajo el mismo run_id); si
 * llegara, se descarta en silencio con el mismo criterio que el roce. */
static bool abortar_pedido(void)
{
    cmd_t c;
    return comando_tomar(CTX_CORRIDA, &c) && c.tipo == CMD_ABORTAR;
}

/* Estado EMPAREJADO: la ventana de tiempo durante la cual la sonda acepta
 * emparejarse. Fuera de aqui NO hay emparejamiento posible (contrato §6.6).
 *
 * La restriccion no es estetica, la impone el resto del sistema: si el
 * emparejamiento pudiera ocurrir en cualquier momento, el passkey habria que
 * pintarlo encima de la pantalla de corrida o de la de configuracion, y las dos
 * conservan su comportamiento de la v1 SIN EXCEPCIONES. Como no hay donde poner
 * el numero, no puede haber emparejamiento fuera de la pantalla que si lo tiene.
 *
 * Y resulta ser ademas la decision de seguridad correcta: nadie empareja un
 * telefono nuevo sin que una persona pulse el boton de esta sonda. */
static void estado_emparejado(void)
{
    ESP_LOGW(TAG, "=== EMPAREJADO: sale al emparejar desde la app ===");

    /* LED APAGADO, como en el JOIN. El LED tiene un solo significado en todo
     * el firmware -- parpadea <=> estas en el menu -- y EMPAREJADO no es el
     * menu. Darle un patron propio romperia la unica propiedad que lo hace
     * util, que es leerse a distancia sin ambiguedad, a cambio de repetir una
     * informacion que ya esta en la pantalla que el operador tiene delante. */
    pmu_led_modo(PMU_LED_APAGADO);
    ble_publicar_estado(seleccion_indice(), BLE_ESTADO_EMPAREJADO);

    /* Abre la ventana y corta la conexion activa si la hay: con una sola
     * conexion permitida, un telefono ya emparejado que siga conectado ocupa la
     * unica ranura y el telefono NUEVO no podria ni conectar. */
    ble_emparejable(true);

    ble_emp_fase_t pintada    = (ble_emp_fase_t)-1;   /* fuerza el 1er repintado */
    uint32_t       pk_pintado = 0;

    for (;;) {
        cmd_t c;
        if (comando_tomar(CTX_EMPAREJADO, &c)) {
            /* RF-10, y es lo mas critico de este estado: se sale SIN la app.
             * Un telefono muerto no puede dejar la sonda encerrada aqui, o se
             * perderia la salida de campo entera. */
            if (c.tipo == CMD_ABORTAR) break;

            if (c.tipo == CMD_BORRAR_BONDS) {
                /* No sale del bucle: tras olvidarlos se sigue en EMPAREJADO,
                 * en fase A, para poder emparejar de nuevo en el acto. */
                ESP_LOGW(TAG, "olvidados TODOS los telefonos emparejados");
                ble_bonds_borrar();
                pintada = (ble_emp_fase_t)-1;
            }
        }

        uint32_t pk     = 0;
        uint16_t motivo = 0;
        ble_emp_fase_t f = ble_emp_fase(&pk, &motivo);

        /* HECHO exige cifrado=1 Y autenticado=1 Y llave de 16 B, no solo
         * cifrado: un emparejamiento "Just Works" da cifrado=1 con toda
         * normalidad y SIN proteccion contra man-in-the-middle. Quien lo
         * comprueba es ble_control; aqui solo se confia en que HECHO signifique
         * eso, que es lo que dice el contrato. */
        if (f == BLE_EMP_HECHO) {
            ESP_LOGW(TAG, "emparejamiento completo (cifrado Y autenticado)");
            break;
        }

        /* Se repinta SOLO al cambiar lo que se ve. El OLED va por I2C y
         * repintar ocho lineas cada 50 ms saturaria el bus para nada; es el
         * mismo criterio que ya usa el parpadeo del cursor del menu.
         *
         * Se vigila tambien el numero, no solo la fase: si alguna vez llegaran
         * dos passkeys seguidos sin pasar por otra fase, la pantalla se
         * quedaria enseñando el viejo y el operador tecleria un numero que ya
         * no vale. El fallo se veria como "lo tecleaste mal", que es
         * exactamente la confusion que hay que evitar en campo. */
        if (f != pintada || pk != pk_pintado) {
            oled_emparejado(f, pk, motivo);
            pintada    = f;
            pk_pintado = pk;
        }

        vTaskDelay(pdMS_TO_TICKS(50));
    }

    /* Cierra la ventana pase lo que pase. Esta llamada esta en la salida UNICA
     * y no repetida en cada break a proposito: una ventana de emparejamiento
     * que se queda abierta porque un camino de salida se olvido de cerrarla es
     * un fallo de seguridad silencioso. */
    ble_emparejable(false);
}

#define PARPADEO_MS  500

/* Bloquea hasta que llega una orden de arrancar, venga del boton (doble
 * pulsacion) o del BLE (seleccionar). Nada se aplica mientras tanto: navegar el
 * menu no transmite ni reconfigura nada.
 *
 * El parpadeo del OLED, el del LED y lo que hace cada gesto son los de la v1,
 * sin un pixel de diferencia. Lo unico nuevo es que la misma espera atiende
 * tambien al BLE, y que la pulsacion larga -- que aqui no hacia nada, porque ya
 * estabamos en el menu -- abre la ventana de emparejamiento (RF-11). */
static void menu_elegir(void)
{
    ESP_LOGW(TAG, "=== MENU: se opera desde la app ===");

    /* El LED parpadea SOLO aqui. Es la confirmacion de que se esta configurando
     * y no midiendo, visible sin acercarse a leer la pantalla. */
    pmu_led_modo(PMU_LED_1HZ);
    publicar_menu();                 /* SIN_ENLACE o CONFIG segun el join de fondo */

    bool    visible    = true;
    bool    unido_prev = lorawan_esta_unido();
    int64_t t_parpadeo = esp_timer_get_time();

    oled_menu_fijo();
    oled_menu_cursor(visible);

    for (;;) {
        cmd_t c;
        if (comando_tomar(CTX_MENU, &c)) {

            if (c.tipo == CMD_ARRANCAR) {
                /* El BLE dice CUAL corrida arrancar; el boton solo sabe decir
                 * "esta", la que el cursor ya tiene encima. De ahi trae_modo. */
                if (c.trae_modo) {
                    seleccion_fijar(c.modo);
                    /* Solo en este camino: el modo pudo cambiar y las lineas
                     * fijas (SF/DR, fPort, perfil) se quedarian mintiendo
                     * durante el sondeo de la microSD, que no es instantaneo.
                     * Por el boton NO se repinta, exactamente como en la v1. */
                    oled_menu_fijo();
                }
                pmu_led_modo(PMU_LED_APAGADO);
                oled_menu_cursor(true);      /* deja de parpadear: queda fija */
                return;
            }

            if (c.tipo == CMD_SIGUIENTE) {
                seleccion_siguiente();
                /* El cursor se publica para que la app lo vea moverse: el byte
                 * `modo` es la seleccion PROVISIONAL, lo que se mira, no lo que
                 * se mide. SIN_ENLACE o CONFIG segun haya enlace. */
                publicar_menu();
                visible = true;              /* al cambiar, se ve entera */
                t_parpadeo = esp_timer_get_time();
                oled_menu_fijo();
                oled_menu_cursor(visible);
            }

            if (c.tipo == CMD_EMPAREJAR) {              /* RF-11 */
                estado_emparejado();
                /* Al volver hay que dejar el menu EXACTAMENTE como estaba antes
                 * de la pulsacion larga: mismo estado publicado, mismo LED,
                 * mismas ocho lineas y el parpadeo empezando de cero. */
                publicar_menu();
                pmu_led_modo(PMU_LED_1HZ);
                visible = true;
                t_parpadeo = esp_timer_get_time();
                oled_menu_fijo();
                oled_menu_cursor(visible);
            }

            /* Re-join por BLE (D-62). La app lo pide cuando el servidor rechaza
             * abrir la sesion con "clase desajustada": ChirpStack congela la
             * clase efectiva en el JOIN, asi que rehacerlo es lo unico que la
             * pone al dia sin apagar la sonda. No hay que publicar nada aqui:
             * al soltar el enlace, el bloque de transicion de abajo republica
             * SIN_ENLACE y repinta la linea 1 -- el mismo camino que cuando el
             * enlace se pierde solo--, y la vuelta a CONFIG la hara ese mismo
             * bloque cuando la tarea de fondo una. */
            if (c.tipo == CMD_REJOIN) {
                ESP_LOGW(TAG, "re-join pedido por BLE: rehaciendo el join OTAA");
                lorawan_rejoin();
            }

            /* CMD_ABORTAR estando ya en configuracion es un NO-OP deliberado, y
             * el GATT ya respondio OK: abortar significa "quiero que estes en
             * configuracion", y si ya lo estas, lo pedido se cumplio. La app lo
             * manda a ciegas al cerrar una sesion sin saber donde esta la
             * sonda; convertir una operacion de higiene en un aviso rojo
             * enseñaria al operador a ignorar los avisos. */
        }

        /* SIN_ENLACE -> CONFIG cuando la tarea de join une por detras: republica
         * el estado y repinta el indicador de enlace (linea 1), sin accion del
         * operador. Es la transicion automatica de la maquina de estados. */
        if (lorawan_esta_unido() != unido_prev) {
            unido_prev = lorawan_esta_unido();
            publicar_menu();
            oled_menu_fijo();
            oled_menu_cursor(visible);
        }

        if ((esp_timer_get_time() - t_parpadeo) / 1000 >= PARPADEO_MS) {
            visible = !visible;
            t_parpadeo = esp_timer_get_time();
            oled_menu_cursor(visible);
        }

        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

typedef enum { FIN_COMPLETA = 0, FIN_ABORTADA } fin_t;

static fin_t ejecutar_corrida(const char *run_id)
{
    const escenario_cfg_t *cfg = escenario_cfg();

    /* VUELO (D-64): la lectura se toma UNA vez por rafaga y los N paquetes de
     * la rafaga la reparten, asi que los tres llevan el mismo instante. La
     * velocidad vertical sale de la altitud GPS de la rafaga anterior. */
    const uint8_t   por_rafaga = cfg->paquetes_rafaga;
    int             rafaga = -1;
    vuelo_lectura_t lect = {};
    bool            alt_prev_ok = false;
    float           alt_prev = 0.0f;
    int64_t         t_prev_us = 0;

    while (!corrida_completa()) {
        const uint8_t idx  = por_rafaga ? (uint8_t)(corrida_uplinks_enviados() % por_rafaga) : 0;
        const uint8_t tipo = por_rafaga ? (uint8_t)(idx + 1) : 0;

        if (!por_rafaga || idx == 0) {
            telemetry_collect(&s_tel, (uint32_t)(esp_log_timestamp() / 1000));
            s_tel_valida = true;
        }

        gps_fix_t gf;
        gps_get(&gf);
        const char *utc = gf.time_valid ? gf.utc_iso : "";

        uint8_t payload[16];
        size_t  len;
        if (por_rafaga) {
            if (idx == 0) {
                rafaga++;
                const int64_t ahora_us = esp_timer_get_time();
                lect = vuelo_lectura_t{};
                lect.fix = s_tel.gps_fix; lect.lat = s_tel.lat; lect.lon = s_tel.lon;
                lect.alt_m = s_tel.alt_m; lect.sats = s_tel.sats; lect.hdop = s_tel.hdop;
                lect.speed_kmh = s_tel.speed_kmh; lect.gps_active = s_tel.gps_active;
                lect.bme_ok = s_tel.bme_ok; lect.temp_c = s_tel.temp_c;
                lect.press_hpa = s_tel.press_hpa; lect.hum_pct = s_tel.hum_pct;
                lect.batt_mv = s_tel.batt_mv; lect.batt_pct = s_tel.batt_pct;
                lect.usb = s_tel.usb; lect.charging = s_tel.charging;
                lect.mag_ok = s_tel.mag_ok; lect.heading_deg = s_tel.heading_deg;
                lect.uptime_s = s_tel.uptime_s;
                if (s_tel.gps_fix && alt_prev_ok && ahora_us > t_prev_us) {
                    lect.vspeed_ok = true;
                    lect.vspeed_ms = (s_tel.alt_m - alt_prev) / ((ahora_us - t_prev_us) / 1e6f);
                }
                alt_prev_ok = s_tel.gps_fix;
                alt_prev = s_tel.alt_m;
                t_prev_us = ahora_us;
                runlog_lectura(run_id, rafaga, utc, &lect);
            }
            len = payload_vuelo_build(payload, sizeof payload, tipo, (uint8_t)rafaga, &lect);
        } else {
            /* En DR0/SF10 la bateria NO cabe: 14 bytes darian 412 ms de airtime y
             * el limite de dwell de US915 son 400. Va solo al log de la microSD. */
            len = payload_terreno_build(
                payload, sizeof payload,
                s_tel.gps_fix, s_tel.lat, s_tel.lon, s_tel.alt_m, s_tel.temp_c,
                cfg->payload_extendido, s_tel.batt_mv, s_tel.batt_pct);
        }

        const int64_t t_ciclo_us = esp_timer_get_time();

        uint32_t airtime = payload_terreno_airtime_ms(cfg->sf, len);
        uint32_t fcnt    = lorawan_fcnt_up();

        char hex[40] = {0};
        for (size_t i = 0; i < len && i < 16; i++)
            snprintf(hex + i * 2, sizeof(hex) - i * 2, "%02x", payload[i]);

        ESP_LOGI(TAG, "---- %s  TX %u/%u ----", run_id,
                 (unsigned)(corrida_uplinks_enviados() + 1),
                 (unsigned)cfg->uplinks_objetivo);
        if (por_rafaga)
            ESP_LOGI(TAG, "  rafaga %d/%u  paquete P%u", rafaga + 1,
                     (unsigned)(cfg->uplinks_objetivo / por_rafaga), (unsigned)tipo);
        ESP_LOGI(TAG, "  SIMULADO: %.5f,%.5f %.0fm | %.2fC %.1fhPa %.0f%% | bat %umV",
                 s_tel.lat, s_tel.lon, s_tel.alt_m, s_tel.temp_c, s_tel.press_hpa,
                 s_tel.hum_pct, (unsigned)s_tel.batt_mv);
        ESP_LOGI(TAG, "  payload %uB fPort %u DR%u/SF%u airtime ~%lu ms | HEX %s",
                 (unsigned)len, (unsigned)escenario_fport(),
                 (unsigned)cfg->dr, (unsigned)cfg->sf,
                 (unsigned long)airtime, hex);

        int  rc = lorawan_send(payload, (uint8_t)len, escenario_fport(), false);
        bool ok = (rc >= 0);
        corrida_registrar_tx(ok);

        /* Se registra SIEMPRE, tambien los fallos: son el denominador del PDR.
         * Sin ellos no se distingue "no se envio" de "se perdio". */
        runlog_uplink(run_id, fcnt, utc,
                      s_tel.gps_fix, s_tel.lat, s_tel.lon, s_tel.alt_m, s_tel.sats,
                      s_tel.temp_c, s_tel.batt_mv,
                      cfg->dr, cfg->sf, airtime, ok ? 0 : rc,
                      tipo, por_rafaga ? rafaga : -1);

        atender_downlink(run_id);
        if (por_rafaga) {
            char est[40];
            snprintf(est, sizeof est, "R%d/%u P%u %s", rafaga + 1,
                     (unsigned)(cfg->uplinks_objetivo / por_rafaga), (unsigned)tipo,
                     ok ? "OK" : "FALLO");
            oled_corrida(&s_tel, est, "abortar: app");
        } else {
            oled_corrida(&s_tel, ok ? "TX OK" : "TX FALLO", "abortar: app");
        }

        if (corrida_completa()) break;

        /* Espera al siguiente uplink sondeando la Clase C por el camino: es lo
         * que permite que el downlink llegue al instante en vez de en la
         * siguiente ventana RX, que es justo la ventaja que mide el experimento.
         *
         * OJO: el periodo se cuenta desde que EMPEZO este ciclo, no desde que
         * termino. El ciclo (TX + RX1 + RX2) consume ~6,5 s; esperar el
         * intervalo completo despues lo sumaria y el periodo real seria el
         * doble del declarado. */
        int64_t transcurrido_ms = (esp_timer_get_time() - t_ciclo_us) / 1000;
        int64_t resta_ms = (int64_t)cfg->intervalo_ms - transcurrido_ms;
        if (resta_ms < 0) {
            ESP_LOGW(TAG, "el ciclo tardo %lld ms, mas que el intervalo de %lu ms",
                     (long long)transcurrido_ms, (unsigned long)cfg->intervalo_ms);
            resta_ms = 0;
        }
        const uint32_t paso_ms = 200;
        for (int64_t t = 0; t < resta_ms; t += paso_ms) {
            lorawan_sondear_clase_c();
            atender_downlink(run_id);
            if (abortar_pedido()) return FIN_ABORTADA;
            vTaskDelay(pdMS_TO_TICKS(paso_ms));
        }
    }

    return FIN_COMPLETA;
}

/* Como se sale de FIN. El boton solo sabe volver al menu; el BLE puede ademas
 * arrancar la siguiente corrida sin pasar por el, porque SI sabe decir cual
 * (contrato §5.3): FIN es un estado de reposo, la sonda no mide nada y arrancar
 * otra no destruye informacion, que la anterior ya esta cerrada en la microSD.
 * Obligar al BLE a mandar abortar + seleccionar seria un viaje de ida y vuelta
 * a cambio de nada. EL BOTON NO CAMBIA: desde FIN sigue haciendo falta la
 * larga, y sigue llevando al menu. */
typedef enum { FIN_SALIR_A_MENU = 0, FIN_ARRANCAR_YA } fin_salida_t;

/* Corrida terminada: la pantalla se queda en FINALIZADO y NO se transmite. Que
 * arrancase sola la siguiente mezclaria dos corridas; que saltara al menu
 * parpadeante borraria el aviso de que esta termino bien. Quien llegue a la
 * sonda ve de un vistazo que acabo y que no esta corriendo nada. */
static fin_salida_t esperar_en_fin(const char *run_id)
{
    ESP_LOGW(TAG, "=== FINALIZADO %s: %u enviados, %u OK ===", run_id,
             (unsigned)corrida_uplinks_enviados(), (unsigned)corrida_uplinks_ok());

    ble_publicar_estado(seleccion_indice(), BLE_ESTADO_FINALIZADA);

    for (;;) {
        /* Se sigue sondeando: un downlink tardio de la corrida que acaba de
         * cerrar todavia es un dato valido de latencia. atender_downlink toma
         * su propia hora fresca del GPS al recibir. */
        lorawan_sondear_clase_c();
        atender_downlink(run_id);

        oled_corrida(s_tel_valida ? &s_tel : NULL, "FINALIZADO", "siguiente: app");

        for (int i = 0; i < 5; i++) {
            cmd_t c;
            if (comando_tomar(CTX_FIN, &c)) {
                if (c.tipo == CMD_ABORTAR) return FIN_SALIR_A_MENU;
                if (c.tipo == CMD_ARRANCAR) {
                    /* Solo puede venir del BLE: la tabla de gestos no produce
                     * CMD_ARRANCAR desde FIN, asi que el boton no puede llegar
                     * aqui ni por accidente. */
                    if (c.trae_modo) seleccion_fijar(c.modo);
                    return FIN_ARRANCAR_YA;
                }
            }
            vTaskDelay(pdMS_TO_TICKS(200));
        }
    }
}

/* Pantalla de la espera de enlace (ESPERANDO_ENLACE, C-Fondo D2=A). Limpia:
 * solo la corrida elegida, los segundos esperando y la salida. */
static void oled_esperando_enlace(long seg)
{
#if USE_OLED
    const escenario_cfg_t *c = escenario_cfg();
    char l[32];

    oled_line(0, "ESPERANDO ENLACE");
    oled_line(1, "");
    snprintf(l, sizeof l, "> %-7s Clase %c", c->id,
             clase_actual() == CLASE_C ? 'C' : 'A');
    oled_line(2, l);
    oled_line(3, "uniendo la sonda...");
    snprintf(l, sizeof l, "%ld s", seg);
    oled_line(4, l);
    oled_line(5, "");
    oled_line(6, "arrancara al unir");
    oled_line(7, "abortar: app");
#else
    (void)seg;
#endif
}

/* Espera ABORTABLE a que la tarea de join adquiera el enlace, tras seleccionar
 * una corrida sin estar aun unida (C-Fondo, D2=A). Devuelve true cuando hay
 * enlace (hay que arrancar), false si el operador aborto (volver al menu).
 *
 * NO toca la radio: solo sondea s_unido. El bucle la tomara DESPUES de que esto
 * devuelva true, y en ese punto la tarea de join ya la solto (§7). Abortar
 * SIEMPRE disponible: nunca se bloquea en mudo, que es el bug que arreglamos. */
static bool esperar_enlace(void)
{
    ESP_LOGW(TAG, "=== ESPERANDO ENLACE: abortar desde la app ===");

    /* LED apagado: no es el menu. El LED solo parpadea en el menu. */
    pmu_led_modo(PMU_LED_APAGADO);
    ble_publicar_estado(seleccion_indice(), BLE_ESTADO_ESPERANDO_ENLACE);

    const int64_t t0 = esp_timer_get_time();
    for (;;) {
        if (lorawan_esta_unido()) return true;

        cmd_t c;
        if (comando_tomar(CTX_ESPERANDO, &c) && c.tipo == CMD_ABORTAR) {
            ESP_LOGW(TAG, "espera de enlace abortada; vuelvo al menu");
            /* Publica ABORTADA como cualquier otro aborto (uniforme con el de una
             * corrida en marcha): da a la app una senal explicita de que la
             * corrida AGENDADA se cancelo. Sin esto, la sonda volvia al menu en
             * silencio y la app -- que habia abierto la sesion -- no se enteraba
             * de que la corrida esperando enlace ya no existia. */
            ble_publicar_estado(seleccion_indice(), BLE_ESTADO_ABORTADA);
            oled_corrida(NULL, "ABORTADA", "");
            vTaskDelay(pdMS_TO_TICKS(1500));
            return false;
        }

        oled_esperando_enlace((long)((esp_timer_get_time() - t0) / 1000000));
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

/* --------------------------------------------------------------------------
 *  Arranque
 * ------------------------------------------------------------------------ */

extern "C" void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(200));
    printf("\n#############################################\n");
    printf("#   PICARO - PRUEBAS DE TERRENO             #\n");
    printf("#   LILYGO T3 v1.6.1 (ESP32 + SX1276)       #\n");
    printf("#   sensores SIMULADOS (simulacion.h)       #\n");
    printf("#############################################\n");

    esp_chip_info_t chip; esp_chip_info(&chip);
    ESP_LOGI(TAG, "ESP-IDF v%s · %d nucleos · rev %d",
             esp_get_idf_version(), chip.cores, chip.revision);

    nvs_bootstrap();
    escenarios_init();   /* recupera la seleccion guardada y arranca el boton */

    /* ---------- v2: servidor GATT de control por BLE ------------------------
     * Ocupa el sitio exacto que tenia el spike de la Fase 0: despues de la NVS
     * (la pila guarda alli los bonds) y antes de todo lo demas, para que el
     * coste de RAM se vea con el sistema aun vacio y se pueda comparar con el
     * de despues del JOIN, que es cuando el LoRaWAN ya ha pedido lo suyo.
     *
     * Si NimBLE no arranca se sigue adelante a proposito: sin BLE la sonda se
     * queda sin el control remoto, pero el boton la opera entera (RF-8) y una
     * salida de campo no se puede perder por eso. */
    log_heap("pre-BLE");
    if (ble_init() != ESP_OK)
        ESP_LOGE(TAG, "BLE: NimBLE no arranco (queda solo el boton, RF-8)");
    log_heap("post-BLE");

    /* ---------- Arranque de la T3 ----------
     * Mismo orden que en la T-Beam, sin los pasos que esta placa no tiene: aqui
     * no hay PMU que encienda rieles (el radio tiene alimentacion fija), ni GPS
     * ni sensores, y la microSD tiene su propio bus. */

    /* 1) LED de modo + ADC de bateria. */
    if (pmu_init() != ESP_OK) ESP_LOGE(TAG, "ADC de bateria no disponible");
    /* Apagado desde el arranque: el LED solo significa "estas en el menu". */
    pmu_led_modo(PMU_LED_APAGADO);

    /* 2) I2C (solo el OLED). */
    i2c0_init();
    i2c0_scan();

    /* 3) OLED + microSD. */
#if USE_OLED
    oled_init();
    oled_line(0, "PICARO LORA32");
    oled_line(1, "Arrancando...");
#endif
#if USE_SDCARD
    if (runlog_init() != ESP_OK)
        ESP_LOGE(TAG, "SIN microSD: la corrida NO sera analizable "
                      "(falta el denominador del PDR)");
#endif

    /* 4) Radio + JOIN en SEGUNDO PLANO (C-Fondo, equipo/DISENO-JOIN-EN-FONDO.md).
     * El join YA NO bloquea el arranque: una tarea lo adquiere por detras
     * mientras la sonda es operable desde el primer segundo (emparejar, navegar,
     * seleccionar). Esto cierra el bug del JOIN bloqueante, que dejaba la sonda
     * sin control por BLE --y sin poder emparejarse-- cuando no habia gateway. */
    int rst = picaro_radio_begin_test();
    if (rst != RADIOLIB_ERR_NONE) ESP_LOGE(TAG, "Radio begin=%d", rst);

    ESP_LOGI(TAG, "=======================================");
    ESP_LOGI(TAG, "  DevEUI %016llX · US915 sub-banda %d",
             (unsigned long long)PICARO_DEV_EUI, PICARO_SUBBAND);
#ifdef PICARO_CORRIDA_FIJA
    ESP_LOGI(TAG, "  corrida fija: VUELO-A (modo %d)", PICARO_CORRIDA_FIJA);
#else
    ESP_LOGI(TAG, "  7 corridas: 3 escenarios x 2 clases + VUELO-A");
#endif
    ESP_LOGI(TAG, "=======================================");

    if (rst == RADIOLIB_ERR_NONE)
        lorawan_iniciar_join_en_fondo();   /* lanza la tarea de join en 2.o plano */
    else
        ESP_LOGE(TAG, "radio no arranco: no se podra unir (la sonda sigue operable)");

    log_heap("tarea-join-viva");   /* RNF-B2: peor caso de RAM, con la tarea aun viva */

    /* Gestos del boton acumulados durante el arranque (buses/OLED/SD/radio) no
     * deben interpretarse al entrar al menu operable (MENOR-9-2p). */
    while (boton_tomar() != BTN_NINGUNO) { }

    /* Sin ningun telefono emparejado no hay forma de mandarle nada a la sonda,
     * asi que se abre la ventana de emparejamiento una vez, aqui -- y AHORA sin
     * esperar al join, que corre por detras (antes esto estaba preso del enlace,
     * y era la otra mitad del bug: una sonda sin bond no se podia ni emparejar).
     * Se sale con el boton (RF-10) aunque no haya movil. */
    if (!ble_hay_bonds())
        estado_emparejado();

    /* 5) Menu -> corrida -> fin -> menu, indefinidamente. */
    char base[40];
    char run_id[64];

    /* Puesto por FIN_ARRANCAR_YA: un "seleccionar" por BLE desde FIN arranca la
     * siguiente corrida sin volver a pasar por el menu. En ese caso YA tenemos
     * la radio (no se solto entre corridas encadenadas), asi que no se re-toma. */
    bool arrancar_ya = false;

    while (true) {
        const bool cadena = arrancar_ya;   /* venimos de FIN_ARRANCAR_YA: radio en mano */

        if (!arrancar_ya)
            menu_elegir();           /* bloquea hasta la orden de arrancar */
        arrancar_ya = false;

        /* Espera de enlace (C-Fondo, D2=A). Si aun no hay enlace, se espera de
         * forma ABORTABLE a que la tarea de join una, y entonces arranca. En
         * cadena ya estamos unidos y con la radio, asi que se salta. La espera
         * NO toma la radio: solo sondea s_unido; el bucle la toma despues (§7). */
        if (!cadena && !lorawan_esta_unido()) {
            if (!esperar_enlace())
                continue;            /* abortada: vuelve al menu, sin radio tomada */
        }

        corrida_confirmar();         /* persiste la eleccion y pone a cero */

        /* Toma la radio SOLO tras s_unido (aqui garantizado) y solo si NO venimos
         * de la cadena, que ya la tiene: re-tomar un mutex ya poseido seria un
         * assert/self-deadlock (MAYOR-1-2p). */
        if (!cadena)
            radio_tomar_para_corrida();

        /* El ACK va AQUI por plazo: entre confirmar y el primer uplink estan
         * lorawan_aplicar_corrida() y runlog_asignar_run_id() (sondea la microSD
         * y puede tardar). Publicar antes mantiene la confirmacion dentro de los
         * 2 s que espera la app; y con enlace ya adquirido, CORRIENDO es honesto. */
        ble_publicar_estado(seleccion_indice(), BLE_ESTADO_CORRIENDO);

        lorawan_aplicar_corrida();   /* ADR off + DR y clase del escenario */
        descartar_downlink_pendiente();

        escenario_run_id_base(base, sizeof base);
        runlog_asignar_run_id(base, run_id, sizeof run_id);

        const escenario_cfg_t *cfg = escenario_cfg();
        ESP_LOGW(TAG, "=== ARRANCA %s ===", run_id);
        ESP_LOGI(TAG, "  %s · %s", cfg->id, cfg->descripcion);
        ESP_LOGI(TAG, "  DR%u/SF%u · %.1f s · %u uplinks · fPort %u · Clase %c",
                 (unsigned)cfg->dr, (unsigned)cfg->sf, cfg->intervalo_ms / 1000.0f,
                 (unsigned)cfg->uplinks_objetivo, (unsigned)escenario_fport(),
                 clase_actual() == CLASE_C ? 'C' : 'A');
        ESP_LOGI(TAG, "  el device profile del servidor debe ser: %s", perfil_requerido());

        if (ejecutar_corrida(run_id) == FIN_ABORTADA) {
            ESP_LOGW(TAG, "=== ABORTADA %s: %u de %u uplinks ===", run_id,
                     (unsigned)corrida_uplinks_enviados(),
                     (unsigned)cfg->uplinks_objetivo);
            ble_publicar_estado(seleccion_indice(), BLE_ESTADO_ABORTADA);
            oled_corrida(s_tel_valida ? &s_tel : NULL, "ABORTADA", "");
            vTaskDelay(pdMS_TO_TICKS(1500));
            radio_soltar_de_corrida();   /* SALIDA al menu: suelta la radio (MAYOR-1-2p) */
        } else {
            if (esperar_en_fin(run_id) == FIN_ARRANCAR_YA) {
                arrancar_ya = true;      /* CADENA: NO suelta (misma posesion) */
            } else {
                radio_soltar_de_corrida();  /* SALIDA al menu: suelta la radio */
            }
        }
    }
}
