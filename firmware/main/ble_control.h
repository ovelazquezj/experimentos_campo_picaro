/**
 * ============================================================================
 *  ble_control.h  -  Servidor GATT de control por BLE (v2)
 * ============================================================================
 *  Contrato: equipo/CONTRATO-BLE.md v2 (byte `ver` = 0x01).
 *
 *  La seguridad la da la pila: LE Secure Connections con Passkey Entry
 *  (decision I). Aqui NO hay criptografia propia.
 *
 *  Este modulo NO decide politica: recibe comandos por un enlace que la pila
 *  ya ha cifrado y autenticado, los encola, y publica el estado que le den.
 *  Que hacer con cada comando lo decide el bucle de app_main.cpp, igual que
 *  con el boton.
 * ============================================================================
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* --- Estado publicado (byte 2 de la caracteristica Estado) --------------- */
typedef enum {
    BLE_ESTADO_CONFIG     = 0x00,   /* menu operable CON enlace ya adquirido    */
    BLE_ESTADO_CORRIENDO  = 0x01,
    BLE_ESTADO_FINALIZADA = 0x02,
    BLE_ESTADO_ABORTADA   = 0x03,
    BLE_ESTADO_UNIENDO    = 0x04,   /* RETIRADO (C-Fondo): no se emite nunca     */
    BLE_ESTADO_EMPAREJADO = 0x05,
    BLE_ESTADO_SIN_ENLACE       = 0x06,  /* menu operable, enlace NO adquirido    */
    BLE_ESTADO_ESPERANDO_ENLACE = 0x07,  /* corrida agendada, esperando enlace    */
} ble_estado_t;

/* --- Comandos entrantes -------------------------------------------------- */
typedef enum {
    BLE_CMD_NINGUNO = 0,
    BLE_CMD_SELECCIONAR,     /* fijar s_sel = modo y arrancar (== doble puls.) */
    BLE_CMD_ABORTAR,         /* volver a configuracion                        */
    BLE_CMD_REJOIN,          /* rehacer el join OTAA (op 0x03, Addendum B /
                              * D-62). Solo aplicable en CONFIG y SIN_ENLACE  */
} ble_cmd_tipo_t;

typedef struct {
    ble_cmd_tipo_t tipo;
    uint8_t        modo;     /* 0..6; solo valido si tipo == SELECCIONAR       */
} ble_cmd_t;

/* --- Fases del estado EMPAREJADO (para pintar el OLED, §7.4) ------------- */
typedef enum {
    BLE_EMP_ESPERANDO = 0,   /* fase A: nadie ha iniciado el emparejamiento   */
    BLE_EMP_PASSKEY,         /* fase B: hay un passkey que mostrar            */
    BLE_EMP_FALLO,           /* fase C: el ultimo intento fallo               */
    BLE_EMP_HECHO,           /* cifrado=1 Y autenticado=1 Y key=16 -> a MENU  */
} ble_emp_fase_t;

/* --- Ciclo de vida ------------------------------------------------------- */

/* Arranca NimBLE con la configuracion de seguridad de §6.2, registra el GATT
 * y empieza a anunciar. Llamar UNA vez, despues de nvs_bootstrap(). Publica
 * (modo=0, estado=UNIENDO) hasta que alguien llame a ble_publicar_estado().
 * Arranca con la ventana de emparejamiento CERRADA. */
esp_err_t ble_init(void);

/* --- Entrada: comandos --------------------------------------------------- */

/* Consulta NO bloqueante, misma forma que boton_tomar(). Devuelve true y
 * rellena *out si habia un comando pendiente, y lo consume. La cola es de UNO:
 * un comando nuevo PISA al anterior sin consumir. Ver §9.4. */
bool ble_tomar_comando(ble_cmd_t *out);

/* --- Salida: estado ------------------------------------------------------ */

/* Publica el estado de la sonda. Idempotente: si los 6 bytes resultantes no
 * cambian respecto a lo ya publicado, NO notifica. Se puede llamar en cada
 * vuelta del bucle sin coste apreciable.
 *
 * OBLIGATORIO llamarla en CADA transicion de la maquina de estados: el modulo
 * valida los comandos entrantes contra el ULTIMO estado publicado (§5.3), asi
 * que un estado sin publicar hace que se acepten comandos que no tocan. */
void ble_publicar_estado(uint8_t modo, ble_estado_t estado);

/* --- Emparejamiento ------------------------------------------------------ */

/* true si hay al menos un bond registrado en la pila. Se consulta UNA vez,
 * tras el JOIN, para decidir si hay que entrar en EMPAREJADO (RF-9).
 * Implementacion: ble_store_util_count(BLE_STORE_OBJ_TYPE_OUR_SEC, &n) > 0. */
bool ble_hay_bonds(void);

/* Abre o cierra la ventana de emparejamiento (§6.6). Al ABRIRLA se corta la
 * conexion activa si la hay (§7.3) y se pasa a la fase ESPERANDO. Al CERRARLA,
 * cualquier emparejamiento en curso se aborta terminando la conexion.
 * Se llama al entrar y al salir del estado EMPAREJADO, y en ningun otro sitio. */
void ble_emparejable(bool abrir);

/* Fase actual del emparejamiento, para pintar el OLED. Si devuelve
 * BLE_EMP_PASSKEY, *passkey trae el numero de 6 digitos (0..999999) que hay que
 * mostrar con %06lu. Si devuelve BLE_EMP_FALLO, *motivo trae el status del
 * evento ENC_CHANGE (1028 = codigo mal tecleado). Los punteros pueden ser NULL.
 *
 * BLE_EMP_HECHO solo se devuelve si encrypted=1 Y authenticated=1 Y
 * key_size=16. Un emparejamiento Just Works NUNCA produce HECHO (§5.1). */
ble_emp_fase_t ble_emp_fase(uint32_t *passkey, uint16_t *motivo);

/* Olvida TODOS los teléfonos emparejados (ble_store_clear) y corta la conexion
 * activa. Revoca a un telefono perdido, que es el unico caso que "olvidar
 * dispositivo" en Android no cubre (§7.5). Gesto: DOBLE pulsacion en el estado
 * EMPAREJADO. */
void ble_bonds_borrar(void);

#ifdef __cplusplus
}
#endif
