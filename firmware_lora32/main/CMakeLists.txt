# ============================================================================
#  main/CMakeLists.txt  -  componente principal de la sonda T3 (LoRa32)
# ----------------------------------------------------------------------------
#  RadioLib se declara en idf_component.yml (la baja el IDF Component Manager).
# ============================================================================
idf_component_register(
    SRCS
        "app_main.cpp"
        # --- propios de la placa T3 v1.6.1 ---
        "radio.cpp"
        "pmu_t3.c"
        "oled_ssd1306.c"
        "gps_ninguno.c"
        "telemetry.c"
        "sdcard.c"
        # --- copias de ../firmware/main (ver README, "Modulos compartidos") ---
        "lorawan.cpp"
        "i2c0.c"
        "escenarios.c"
        "payload_terreno.c"
        "runlog.c"
        "ble_control.c"
    INCLUDE_DIRS
        "."
    REQUIRES
        driver
        esp_adc
        esp_timer
        nvs_flash
        fatfs
        sdmmc
        esp_driver_sdspi
        bt            # NimBLE (ble_control.c)
)

# La T3 corre UNA sola corrida: VUELO-A, modo 6 del contrato BLE (D-65). El
# selector arranca ahi, el BLE rechaza cualquier otro modo con ATT 0x83 y el
# microservicio tampoco abre otra para la sonda lora32.
target_compile_definitions(${COMPONENT_LIB} PRIVATE PICARO_CORRIDA_FIJA=6)
