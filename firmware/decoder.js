// ============================================================================
//  decoder.js  -  Codec ChirpStack para la radiosonda de PRUEBAS DE TERRENO
// ============================================================================
//
//  Payload de LONGITUD VARIABLE, little-endian (el ESP32 lo es, y la struct
//  se envia en crudo con __attribute__((packed))):
//
//    [0..3]   int32  latitude    grados * 1e7
//    [4..7]   int32  longitude   grados * 1e7
//    [8..9]   int16  altitude    metros
//    [10]     int8   temperature grados C * 2  (resolucion 0.5)
//    ------------------------------------------------- 11 bytes (minimo)
//    [11..12] uint16 batt_mV     milivoltios      \  extension opcional:
//    [13]     uint8  batt_pct    0-100, 0xFF=n/d  /  solo si el DR lo permite
//    ------------------------------------------------- 14 bytes (extendido)
//
//  POR QUE VARIABLE: en US915 el DR0 (SF10) limita el payload de aplicacion a
//  11 bytes por el dwell time de 400 ms. El escenario del cerro usa SF10 para
//  maximo alcance, asi que ahi NO caben los 3 bytes de bateria. En SF9 y SF7
//  si caben (53 y 242 bytes de limite). El decodificador lo resuelve mirando
//  la longitud, de modo que un unico device profile sirve para los 6 casos.
//
//  El fPort identifica la corrida del experimento (coste cero de aire):
//    11 = escenario 1 clase A     12 = escenario 1 clase C
//    13 = escenario 2 clase A     14 = escenario 2 clase C
//    15 = escenario 3 clase A     16 = escenario 3 clase C
//    17 = VUELO clase A (D-64): 3 paquetes por rafaga, ver decodeVuelo()
//    98 = ping de latencia (downlink)   99 = corte real (downlink, byte 0xA5)
// ============================================================================

var ESCENARIOS = {
    11: { escenario: 1, clase: "A", nombre: "urbano en vehiculo" },
    12: { escenario: 1, clase: "C", nombre: "urbano en vehiculo" },
    13: { escenario: 2, clase: "A", nombre: "terraza piso 5 LoS" },
    14: { escenario: 2, clase: "C", nombre: "terraza piso 5 LoS" },
    15: { escenario: 3, clase: "A", nombre: "cerro LoS 16,35 km" },
    16: { escenario: 3, clase: "C", nombre: "cerro LoS 16,35 km" }
};

// ----------------------------------------------------------------------------
//  VUELO (fPort 17). Especificacion completa: docs/VUELO-ESPEC.md
//  11 bytes exactos, little-endian. Byte 0 = tipo << 6 | rafaga (6 bits):
//    tipo 1 P1 posicion   : lat i32 1e7 · lon i32 1e7 · alt u16 m
//    tipo 2 P2 ambiente   : temp i16 x100 · pres u16 x10 · hum u8 · bat u16 mV
//                           · bat u8 % · sats u8 · banderas u8
//    tipo 3 P3 navegacion : vel u16 x10 · rumbo u16 x10 · hdop u8 x10
//                           · vvert i16 x10 · uptime u24 s
//  Sentinelas "no disponible": 0x7FFF (i16), 0xFFFF (u16), 0xFF (u8) -> null.
// ----------------------------------------------------------------------------
var TIPOS_VUELO = { 1: "posicion", 2: "ambiente", 3: "navegacion" };

function decodeVuelo(b) {
    var warnings = [];
    var errors = [];
    if (b.length !== 11) {
        errors.push("VUELO: se esperaban 11 bytes, llegaron " + b.length);
        return { data: {}, warnings: warnings, errors: errors };
    }
    function u16(i) { return b[i] | (b[i + 1] << 8); }
    function i16(i) { var v = u16(i); return (v & 0x8000) ? v - 0x10000 : v; }
    function i32(i) { return (b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) | (b[i + 3] << 24)); }
    function na16(v, esc) { return v === 0xFFFF ? null : v / esc; }
    function nai16(v, esc) { return v === 0x7FFF ? null : v / esc; }
    function na8(v, esc) { return v === 0xFF ? null : v / esc; }

    var tipo = b[0] >> 6;
    var data = {
        tipo_paquete: TIPOS_VUELO[tipo] || null,
        rafaga: b[0] & 0x3F,
        escenario: 4,
        clase: "A",
        escenario_nombre: "vuelo (puntos fijos)"
    };
    if (tipo === 1) {
        var lat = i32(1) / 10000000.0;
        var lon = i32(5) / 10000000.0;
        data.gps_fix = !(lat === 0 && lon === 0);
        data.latitude = data.gps_fix ? lat : null;
        data.longitude = data.gps_fix ? lon : null;
        data.altitude_m = data.gps_fix ? na16(u16(9), 1) : null;
        if (!data.gps_fix) warnings.push("Sin fix de GPS: sin posicion en esta rafaga");
    } else if (tipo === 2) {
        var f = b[10];
        data.temperature_c = nai16(i16(1), 100);
        data.pressure_hpa = na16(u16(3), 10);
        data.humidity_pct = na8(b[5], 1);
        data.battery_v = u16(6) / 1000.0;
        data.battery_pct = na8(b[8], 1);
        data.satellites = b[9];
        data.gps_fix = !!(f & 0x01);
        data.usb_powered = !!(f & 0x02);
        data.charging = !!(f & 0x04);
        data.gps_active = !!(f & 0x08);
        data.mag_ok = !!(f & 0x10);
        data.bme_ok = !!(f & 0x20);
        if (data.battery_pct === null) warnings.push("Nivel de bateria no disponible; usar battery_v");
    } else if (tipo === 3) {
        data.speed_kmh = na16(u16(1), 10);
        data.heading_deg = na16(u16(3), 10);
        data.hdop = na8(b[5], 10);
        data.vspeed_ms = nai16(i16(6), 10);
        data.uptime_s = b[8] | (b[9] << 8) | (b[10] << 16);
    } else {
        errors.push("VUELO: tipo de paquete desconocido (" + tipo + ")");
    }
    return { data: data, warnings: warnings, errors: errors };
}

function decodeUplink(input) {
    if (input.fPort === 17) return decodeVuelo(input.bytes);
    var b = input.bytes;
    var warnings = [];
    var errors = [];

    if (b.length < 11) {
        errors.push("Payload demasiado corto: se esperaban >=11 bytes, llegaron " + b.length);
        return { data: {}, warnings: warnings, errors: errors };
    }

    // Little-endian. OJO: el codec del ejercicio 09 es big-endian; este NO.
    function u16(i) { return b[i] | (b[i + 1] << 8); }
    function i16(i) { var v = u16(i); return (v & 0x8000) ? v - 0x10000 : v; }
    function i32(i) {
        var v = (b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) | (b[i + 3] << 24));
        return v;   // el operador | ya devuelve int32 con signo en JS
    }
    function i8(i) { return (b[i] & 0x80) ? b[i] - 256 : b[i]; }

    var lat = i32(0) / 10000000.0;
    var lon = i32(4) / 10000000.0;

    var data = {
        latitude: lat,
        longitude: lon,
        altitude_m: i16(8),
        temperature_c: i8(10) / 2.0
    };

    // Sin fix, el firmware envia lat/lon a cero. Se marcan como invalidas en
    // vez de dibujar un punto en el golfo de Guinea.
    data.gps_fix = !(lat === 0 && lon === 0);
    if (!data.gps_fix) {
        data.latitude = null;
        data.longitude = null;
        warnings.push("Sin fix de GPS: no se incluyen latitud/longitud");
    }

    // Extension de bateria (no cabe en SF10 / DR0).
    if (b.length >= 14) {
        data.battery_v = u16(11) / 1000.0;
        // 0xFF = el firmware no pudo leer el gauge. Se reporta null en vez de
        // 255%: un fallo de lectura no debe llegar como un dato de bateria
        // valido. Los milivoltios (battery_v) son lectura directa y si valen.
        if (b[13] === 0xFF) {
            data.battery_pct = null;
            warnings.push("Nivel de bateria no disponible (fallo de lectura del gauge); usar battery_v");
        } else {
            data.battery_pct = b[13];
        }
    } else {
        warnings.push("Payload corto (SF10): sin telemetria de bateria, ver log de microSD");
    }

    // Etiqueta de corrida a partir del fPort.
    var run = ESCENARIOS[input.fPort];
    if (run) {
        data.escenario = run.escenario;
        data.clase = run.clase;
        data.escenario_nombre = run.nombre;
    } else {
        warnings.push("fPort " + input.fPort + " no corresponde a ninguna corrida conocida");
    }

    return { data: data, warnings: warnings, errors: errors };
}

// Downlink: 1 byte. fPort 99 + 0xA5 = corte real; fPort 98 = ping de latencia.
function encodeDownlink(input) {
    if (input.data && typeof input.data.comando === "string") {
        if (input.data.comando === "corte") {
            return { bytes: [0xA5], fPort: 99, warnings: [], errors: [] };
        }
        if (input.data.comando === "ping") {
            return { bytes: [0x01], fPort: 98, warnings: [], errors: [] };
        }
    }
    return { bytes: [], fPort: input.fPort || 98, warnings: [], errors: ["comando no reconocido: usa 'corte' o 'ping'"] };
}
