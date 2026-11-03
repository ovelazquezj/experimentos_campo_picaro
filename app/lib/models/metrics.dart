import 'json_utils.dart';

/// Metricas en vivo calculadas por el servidor sobre la sesion activa (§6).
class Metrics {
  final int received;
  final int? expectedFport;
  final int? lastFcnt;
  final int gaps;
  final double? pdrEst; // estimado: etiquetar siempre como "est."
  final double? progressPct; // min(100, 100·(last−first+1)/target), §12.3
  final double? rssiMean;
  final int? rssiLast;
  final double? snrMean;
  final double? distGwKmMax;
  final String? lastUplinkIso;
  final double? batteryV;
  final int? batteryPct; // puede ser null (0xFF -> null), no tratar como 0
  final bool? gpsFix;
  final int? satellites;

  /// Bloque `vuelo` de las metricas (solo corridas VUELO). **Opcional**: un
  /// servidor sin soporte de VUELO no lo manda y aqui queda null sin fallar.
  final MetricsVuelo? vuelo;

  /// Distancia medida con el GPS del telefono (D-65, sondas sin GPS): la del
  /// ultimo uplink, la ultima posicion enviada y el gateway que lo recibio.
  final double? distGwKmUltima;
  final PosicionTelefono? posicionTelefono;
  final String? gatewayUltimo;

  const Metrics({
    this.received = 0,
    this.expectedFport,
    this.lastFcnt,
    this.gaps = 0,
    this.pdrEst,
    this.progressPct,
    this.rssiMean,
    this.rssiLast,
    this.snrMean,
    this.distGwKmMax,
    this.lastUplinkIso,
    this.batteryV,
    this.batteryPct,
    this.gpsFix,
    this.satellites,
    this.vuelo,
    this.distGwKmUltima,
    this.posicionTelefono,
    this.gatewayUltimo,
  });

  /// Uplinks ENVIADOS por la sonda desde que empezo la sesion (estimado):
  /// `received + gaps` = rango de fCnt observado `(last − first + 1)`.
  ///
  /// Es el «TX n/300» del contrato (§12.3): espeja el contador de la OLED del
  /// device, que se reinicia al arrancar cada corrida. NO usar [lastFcnt] para
  /// esto: es el fCnt LoRaWAN absoluto y solo se reinicia con un re-join, asi
  /// que una segunda corrida sin reiniciar la sonda seguiria acumulando
  /// (301/300, 302/300, …) en vez de partir de 0.
  int get sentEst => received + gaps;

  factory Metrics.fromJson(Map<String, dynamic> j) {
    return Metrics(
      received: asInt(j['received']) ?? 0,
      expectedFport: asInt(j['expected_fport']),
      lastFcnt: asInt(j['last_fcnt']),
      gaps: asInt(j['gaps']) ?? 0,
      pdrEst: asDouble(j['pdr_est']),
      progressPct: asDouble(j['progress_pct']),
      rssiMean: asDouble(j['rssi_mean']),
      rssiLast: asInt(j['rssi_last']),
      snrMean: asDouble(j['snr_mean']),
      distGwKmMax: asDouble(j['dist_gw_km_max']),
      lastUplinkIso: asString(j['last_uplink_iso']),
      batteryV: asDouble(j['battery_v']),
      batteryPct: asInt(j['battery_pct']),
      gpsFix: asBool(j['gps_fix']),
      satellites: asInt(j['satellites']),
      vuelo: MetricsVuelo.tryParse(j['vuelo']),
      distGwKmUltima: asDouble(j['dist_gw_km_ultima']),
      posicionTelefono: PosicionTelefono.tryParse(j['posicion_telefono']),
      gatewayUltimo: asString(asMap(j['gateway_ultimo'])?['id']),
    );
  }
}

/// Ultima posicion del telefono registrada en la sesion (D-65).
class PosicionTelefono {
  final double lat;
  final double lon;
  final double? precisionM;
  final String? iso;

  const PosicionTelefono(this.lat, this.lon, {this.precisionM, this.iso});

  static PosicionTelefono? tryParse(Object? raw) {
    final j = asMap(raw);
    if (j == null) return null;
    final lat = asDouble(j['lat']);
    final lon = asDouble(j['lon']);
    if (lat == null || lon == null) return null;
    return PosicionTelefono(lat, lon,
        precisionM: asDouble(j['precision_m']), iso: asString(j['iso']));
  }
}

/// Metricas por rafaga de la corrida VUELO (docs/VUELO-ESPEC.md, «Metricas»):
/// rafagas completas (3 de 3), parciales (1–2) y perdidas (0), y recibidos por
/// tipo de paquete.
///
/// Forma que manda el microservicio (null en corridas no VUELO):
/// `{por_tipo: {posicion, ambiente, navegacion}, rafagas_completas,
/// rafagas_parciales, rafagas_perdidas, rafaga_max, rafagas_objetivo}`.
/// Por tolerancia se aceptan tambien variantes sin el prefijo `rafagas_` y
/// claves `P1`/`P2`/`P3`. Todo campo que falte queda null.
class MetricsVuelo {
  final int? completas;
  final int? parciales;
  final int? perdidas;
  final int? rafagaUltima; // 0..54 (`rafaga_max` del microservicio)
  final int? rafagasObjetivo; // 55
  final int? p1;
  final int? p2;
  final int? p3;

  const MetricsVuelo({
    this.completas,
    this.parciales,
    this.perdidas,
    this.rafagaUltima,
    this.rafagasObjetivo,
    this.p1,
    this.p2,
    this.p3,
  });

  /// Null si [v] no es un mapa (clave ausente, null o de otro tipo).
  static MetricsVuelo? tryParse(dynamic v) {
    final j = asMap(v);
    if (j == null) return null;
    dynamic k(List<String> claves) {
      for (final c in claves) {
        if (j[c] != null) return j[c];
      }
      return null;
    }

    final tipos = asMap(k(['por_tipo', 'tipos', 'paquetes_por_tipo'])) ??
        const <String, dynamic>{};
    int? tipo(List<String> claves) {
      for (final c in claves) {
        final n = asInt(tipos[c] ?? j[c]);
        if (n != null) return n;
      }
      return null;
    }

    return MetricsVuelo(
      completas: asInt(k(['rafagas_completas', 'completas'])),
      parciales: asInt(k(['rafagas_parciales', 'parciales'])),
      perdidas: asInt(k(['rafagas_perdidas', 'perdidas'])),
      rafagaUltima:
          asInt(k(['rafaga_max', 'rafaga_ultima', 'ultima_rafaga', 'rafaga'])),
      rafagasObjetivo: asInt(k(['rafagas_objetivo', 'target_rafagas'])),
      p1: tipo(['P1', 'p1', 'posicion']),
      p2: tipo(['P2', 'p2', 'ambiente']),
      p3: tipo(['P3', 'p3', 'navegacion']),
    );
  }
}
