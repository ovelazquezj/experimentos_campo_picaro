/**
 * ============================================================================
 *  runlog.c  -  CSV por corrida sobre la microSD ya montada por sdcard.c
 * ============================================================================
 */
#include "runlog.h"
#include "sdcard.h"

#include "esp_log.h"
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

static const char *TAG = "runlog";

#define MOUNT "/sdcard"

static const char *CAB_UP =
    "run_id,fcnt,utc,lat,lon,alt,sats,fix,temp_c,batt_mV,batt_mA,dr,sf,airtime_ms,tx_rc,tipo,rafaga";
/* `tipo` y `rafaga` se anadieron el 2026-09-28 (D-64, VUELO); fuera de VUELO van
 * vacias. Van AL FINAL para que un lector por posicion de las columnas viejas
 * siga funcionando. */
static const char *CAB_LECT =
    "run_id,rafaga,utc,fix,lat,lon,alt,sats,hdop,speed_kmh,vspeed_ms,heading_deg,"
    "temp_c,press_hpa,hum_pct,batt_mV,batt_pct,usb,charging,gps_active,mag_ok,bme_ok,uptime_s";
/* La columna `ventana` (rx1/rx2/rxc/desconocida) se anadio el 2026-08-29; los
 * CSV anteriores tienen 5 columnas. Como la cabecera solo se escribe al CREAR
 * el fichero, un fichero viejo nunca queda con cabecera y filas discordantes. */
static const char *CAB_DL =
    "run_id,utc,fport,seq,accion,ventana";

esp_err_t runlog_init(void)
{
    esp_err_t e = sdcard_init();
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "sin microSD (%s): la corrida NO sera analizable",
                 esp_err_to_name(e));
        return e;
    }
    ESP_LOGI(TAG, "microSD lista. Un fichero por corrida: %s/<run_id>.csv", MOUNT);
    return ESP_OK;
}

bool runlog_disponible(void) { return sdcard_present(); }

const char *runlog_asignar_run_id(const char *base, char *buf, size_t len)
{
    snprintf(buf, len, "%s", base ? base : "SINBASE");
    if (!sdcard_present()) return buf;

    char ruta[96];
    struct stat st;

    for (unsigned n = 1; n <= 99; n++) {
        if (n == 1) snprintf(buf, len, "%s", base);
        else        snprintf(buf, len, "%s-%u", base, n);

        snprintf(ruta, sizeof ruta, MOUNT "/%s.csv", buf);
        if (stat(ruta, &st) != 0) {
            if (n > 1) ESP_LOGW(TAG, "ya habia corridas previas: este es el intento %u", n);
            return buf;
        }
    }

    /* 99 intentos del mismo escenario el mismo dia no es un escenario realista;
     * si ocurre, es preferible seguir escribiendo (aunque se mezcle) que perder
     * la corrida entera por no tener donde registrarla. */
    ESP_LOGE(TAG, "mas de 99 intentos de %s: se reutiliza %s y las filas se mezclaran",
             base, buf);
    return buf;
}

/* Abre en modo append y escribe la cabecera si el fichero acaba de nacer.
 * Se abre y cierra en cada fila a proposito: un corte de alimentacion en campo
 * no debe llevarse por delante lo ya registrado. A 7 s por uplink el coste es
 * irrelevante. */
static void escribir(const char *ruta, const char *cabecera, const char *fila)
{
    struct stat st;
    bool nuevo = (stat(ruta, &st) != 0 || st.st_size == 0);

    FILE *f = fopen(ruta, "a");
    if (!f) { ESP_LOGE(TAG, "no pude abrir %s", ruta); return; }
    if (nuevo) fprintf(f, "%s\n", cabecera);
    fprintf(f, "%s\n", fila);
    fclose(f);
}

void runlog_uplink(const char *run_id, uint32_t fcnt, const char *utc_iso,
                   bool fix, double lat, double lon, float alt_m, uint8_t sats,
                   float temp_c, uint16_t batt_mv,
                   uint8_t dr, uint8_t sf, uint32_t airtime_ms, int tx_rc,
                   uint8_t tipo, int rafaga)
{
    if (!sdcard_present()) return;

    char ruta[96];
    snprintf(ruta, sizeof ruta, MOUNT "/%s.csv", run_id);

    /* Sin fix las coordenadas se dejan VACIAS, no a cero: un 0,0 en el CSV se
     * confundiria con una posicion real en el golfo de Guinea al analizar. */
    char pos[48];
    if (fix) snprintf(pos, sizeof pos, "%.7f,%.7f", lat, lon);
    else     snprintf(pos, sizeof pos, ",");

    char vuelo[16] = ",";
    if (tipo) snprintf(vuelo, sizeof vuelo, "%u,%d", (unsigned)tipo, rafaga);

    char fila[256];
    snprintf(fila, sizeof fila,
             "%s,%lu,%s,%s,%.1f,%u,%d,%.2f,%u,,%u,%u,%lu,%d,%s",
             run_id, (unsigned long)fcnt, utc_iso ? utc_iso : "",
             pos, alt_m, (unsigned)sats, fix ? 1 : 0,
             temp_c, (unsigned)batt_mv,
             (unsigned)dr, (unsigned)sf, (unsigned long)airtime_ms, tx_rc, vuelo);

    escribir(ruta, CAB_UP, fila);
}

void runlog_lectura(const char *run_id, int rafaga, const char *utc_iso,
                    const vuelo_lectura_t *l)
{
    if (!sdcard_present() || !l) return;

    char ruta[96];
    snprintf(ruta, sizeof ruta, MOUNT "/%s_lecturas.csv", run_id);

    /* Igual que en runlog_uplink: lo que no se midio va VACIO, nunca a cero. */
    char pos[64], vs[16], rumbo[16], amb[48];
    if (l->fix) snprintf(pos, sizeof pos, "%.7f,%.7f,%.1f", l->lat, l->lon, l->alt_m);
    else        snprintf(pos, sizeof pos, ",,");
    if (l->vspeed_ok) snprintf(vs, sizeof vs, "%.2f", l->vspeed_ms); else vs[0] = 0;
    if (l->mag_ok) snprintf(rumbo, sizeof rumbo, "%.1f", l->heading_deg); else rumbo[0] = 0;
    if (l->bme_ok) snprintf(amb, sizeof amb, "%.2f,%.1f,%.1f", l->temp_c, l->press_hpa, l->hum_pct);
    else           snprintf(amb, sizeof amb, ",,");

    char fila[320];
    snprintf(fila, sizeof fila,
             "%s,%d,%s,%d,%s,%u,%.1f,%.1f,%s,%s,%s,%u,%u,%d,%d,%d,%d,%d,%lu",
             run_id, rafaga, utc_iso ? utc_iso : "", l->fix ? 1 : 0, pos,
             (unsigned)l->sats, l->hdop, l->speed_kmh, vs, rumbo, amb,
             (unsigned)l->batt_mv, (unsigned)l->batt_pct,
             l->usb ? 1 : 0, l->charging ? 1 : 0, l->gps_active ? 1 : 0,
             l->mag_ok ? 1 : 0, l->bme_ok ? 1 : 0, (unsigned long)l->uptime_s);

    escribir(ruta, CAB_LECT, fila);
}

void runlog_downlink(const char *run_id, const char *utc_iso,
                     uint8_t fport, uint8_t seq, const char *accion,
                     const char *ventana)
{
    if (!sdcard_present()) return;

    char ruta[96];
    snprintf(ruta, sizeof ruta, MOUNT "/%s_dl.csv", run_id);

    char fila[192];
    snprintf(fila, sizeof fila, "%s,%s,%u,%u,%s,%s",
             run_id, utc_iso ? utc_iso : "", (unsigned)fport,
             (unsigned)seq, accion ? accion : "",
             ventana ? ventana : "desconocida");

    escribir(ruta, CAB_DL, fila);
}
