import 'dart:convert';

import 'json_utils.dart';

/// Tipo de paquete de una rafaga de VUELO (docs/VUELO-ESPEC.md).
enum TipoPaquete { posicion, ambiente, navegacion }

/// «P1» / «P2» / «P3», como en la especificacion.
String etiquetaTipo(TipoPaquete? t) {
  switch (t) {
    case TipoPaquete.posicion:
      return 'P1';
    case TipoPaquete.ambiente:
      return 'P2';
    case TipoPaquete.navegacion:
      return 'P3';
    case null:
      return 'P?';
  }
}

TipoPaquete? _parseTipo(dynamic v) {
  switch (asString(v)?.toLowerCase().trim()) {
    case 'posicion':
    case 'p1':
    case '1':
      return TipoPaquete.posicion;
    case 'ambiente':
    case 'p2':
    case '2':
      return TipoPaquete.ambiente;
    case 'navegacion':
    case 'p3':
    case '3':
      return TipoPaquete.navegacion;
  }
  return null;
}

/// Uplink aplanado (mismas columnas que `dashboard/storage.py`, §4). Se recibe
/// por WebSocket (`type: uplink`) y por `GET /sessions/{id}/uplinks`.
class Uplink {
  final double? ts; // epoch unix (s)
  final String? iso;
  final String? devEui;
  final int? fCnt;
  final int? fPort;
  final int? rssi;
  final double? snr;
  final String? gatewayId;
  final int? freq;
  final int? dr;
  final bool? gpsActive;
  final bool? gpsFix;
  final double? latitude;
  final double? longitude;
  final double? altitudeM;
  final int? satellites;
  final double? batteryV;
  final int? batteryPct; // null si desconocida
  final bool? charging;
  final bool? usbPowered;
  final double? temperatureC;
  final double? pressureHpa;

  // --- Solo VUELO (fPort 17). El decoder los deja en `object` y el
  // microservicio no los aplana en columnas: pueden llegar en la raiz del
  // mensaje, en `object` o dentro de `raw_json` (ver [Uplink.fromJson]).
  final TipoPaquete? tipoPaquete;
  final int? rafaga; // 0..54
  final int? humidityPct;
  final double? speedKmh;
  final double? headingDeg; // null sin magnetometro
  final double? hdop;
  final double? vspeedMs; // null en la primera rafaga o sin fix
  final int? uptimeS;

  const Uplink({
    this.ts,
    this.iso,
    this.devEui,
    this.fCnt,
    this.fPort,
    this.rssi,
    this.snr,
    this.gatewayId,
    this.freq,
    this.dr,
    this.gpsActive,
    this.gpsFix,
    this.latitude,
    this.longitude,
    this.altitudeM,
    this.satellites,
    this.batteryV,
    this.batteryPct,
    this.charging,
    this.usbPowered,
    this.temperatureC,
    this.pressureHpa,
    this.tipoPaquete,
    this.rafaga,
    this.humidityPct,
    this.speedKmh,
    this.headingDeg,
    this.hdop,
    this.vspeedMs,
    this.uptimeS,
  });

  factory Uplink.fromJson(Map<String, dynamic> j) {
    // Campos de VUELO que no son columnas del microservicio. El microservicio
    // los manda en la clave `vuelo` de cada uplink (null en fPort != 17). Por
    // tolerancia se aceptan tambien en la raiz, en `object` o en `raw_json`
    // (texto o mapa, con el evento de ChirpStack). Si no estan, null.
    final extra = _extrasVuelo(j);
    dynamic x(String k) => j[k] ?? extra[k];
    final fPort = asInt(j['f_port']);
    return Uplink(
      ts: asDouble(j['ts']),
      iso: asString(j['iso']),
      devEui: asString(j['dev_eui']),
      fCnt: asInt(j['f_cnt']),
      fPort: fPort,
      rssi: asInt(j['rssi']),
      snr: asDouble(j['snr']),
      gatewayId: asString(j['gateway_id']),
      freq: asInt(j['freq']),
      dr: asInt(j['dr']),
      gpsActive: asBool(j['gps_active']),
      gpsFix: asBool(j['gps_fix']),
      latitude: asDouble(j['latitude']),
      longitude: asDouble(j['longitude']),
      altitudeM: asDouble(j['altitude_m']),
      satellites: asInt(j['satellites']),
      batteryV: asDouble(j['battery_v']),
      batteryPct: asInt(j['battery_pct']),
      charging: asBool(j['charging']),
      usbPowered: asBool(j['usb_powered']),
      temperatureC: asDouble(j['temperature_c']),
      pressureHpa: asDouble(j['pressure_hpa']),
      tipoPaquete: _parseTipo(x('tipo_paquete')),
      rafaga: asInt(x('rafaga')),
      humidityPct: asInt(x('humidity_pct')),
      speedKmh: asDouble(x('speed_kmh')),
      headingDeg: asDouble(x('heading_deg')),
      hdop: asDouble(x('hdop')),
      vspeedMs: asDouble(x('vspeed_ms')),
      uptimeS: asInt(x('uptime_s')),
    );
  }

  /// Mapa con los campos del `object` del decoder, si el mensaje los trae de
  /// alguna forma. Nunca lanza: un `raw_json` corrupto no debe tumbar el WS.
  static Map<String, dynamic> _extrasVuelo(Map<String, dynamic> j) {
    final vuelo = asMap(j['vuelo']);
    if (vuelo != null) return vuelo;
    final obj = asMap(j['object']);
    if (obj != null) return obj;
    final raw = j['raw_json'];
    Map<String, dynamic>? evento;
    if (raw is String && raw.isNotEmpty) {
      try {
        evento = asMap(jsonDecode(raw));
      } catch (_) {
        evento = null;
      }
    } else {
      evento = asMap(raw);
    }
    if (evento == null) return const {};
    return asMap(evento['object']) ?? evento;
  }

  /// Es un paquete de VUELO (fPort 17).
  bool get esVuelo => fPort == 17;

  /// Tipo de paquete: el que dice el decoder o, si el servidor no lo expone,
  /// el que se deduce de las columnas. P2 es el unico que trae bateria o
  /// temperatura; P1 el unico que trae posicion (o `gps_fix` sin bateria, que
  /// es un P1 sin fix). P3 no deja rastro en las columnas: sin `tipo_paquete`
  /// no se puede distinguir de «nada», y se devuelve null.
  TipoPaquete? get tipoEfectivo {
    if (tipoPaquete != null) return tipoPaquete;
    if (!esVuelo) return null;
    if (batteryV != null ||
        temperatureC != null ||
        pressureHpa != null ||
        humidityPct != null) {
      return TipoPaquete.ambiente;
    }
    if (latitude != null || longitude != null || altitudeM != null) {
      return TipoPaquete.posicion;
    }
    if (gpsFix != null) return TipoPaquete.posicion;
    if (speedKmh != null || headingDeg != null || hdop != null || uptimeS != null) {
      return TipoPaquete.navegacion;
    }
    return null;
  }

  /// Punto valido para el mapa: con fix, coords no nulas, distintas de (0,0)
  /// y dentro de rango. En VUELO los P2/P3 no traen posicion (null) y no
  /// cuentan como punto: el mapa nunca pinta un «0,0» de un paquete sin ella.
  bool get hasFixPoint {
    final lat = latitude;
    final lon = longitude;
    if (lat == null || lon == null) return false;
    if (gpsFix == false) return false;
    if (lat == 0 && lon == 0) return false;
    if (lat.abs() > 90 || lon.abs() > 180) return false;
    return true;
  }
}
