import 'json_utils.dart';
import 'metrics.dart';

/// Resumen de una sesion cerrada (§6). Se acepta `duration_s` o `duracion_s`.
class SessionSummary {
  final int? received;
  final double? pdrEst;
  final double? rssiMean;
  final double? snrMean;
  final double? distGwKmMax;
  final double? durationS;
  final String? runLabel;
  final String? state;

  /// Rafagas de VUELO (null en las demas corridas o si el servidor no lo manda).
  final MetricsVuelo? vuelo;

  const SessionSummary({
    this.received,
    this.pdrEst,
    this.rssiMean,
    this.snrMean,
    this.distGwKmMax,
    this.durationS,
    this.runLabel,
    this.state,
    this.vuelo,
  });

  factory SessionSummary.fromJson(Map<String, dynamic> j) {
    return SessionSummary(
      received: asInt(j['received']),
      pdrEst: asDouble(j['pdr_est']),
      rssiMean: asDouble(j['rssi_mean']),
      snrMean: asDouble(j['snr_mean']),
      distGwKmMax: asDouble(j['dist_gw_km_max']),
      durationS: asDouble(j['duration_s']) ?? asDouble(j['duracion_s']),
      runLabel: asString(j['run_label']),
      state: asString(j['state']),
      vuelo: MetricsVuelo.tryParse(j['vuelo']),
    );
  }
}
