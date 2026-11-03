import 'json_utils.dart';
import 'metrics.dart';
import 'session.dart';
import 'summary.dart';

/// Respuesta de `GET /health` (§6, sin auth).
class Health {
  final String status;
  final bool mqttConnected;
  final String version;

  const Health({
    required this.status,
    required this.mqttConnected,
    required this.version,
  });

  factory Health.fromJson(Map<String, dynamic> j) => Health(
        status: asString(j['status']) ?? '?',
        mqttConnected: asBool(j['mqtt_connected']) ?? false,
        version: asString(j['version']) ?? '?',
      );

  bool get ok => status == 'ok';
}

/// Respuesta de `GET /session/current` (§6): {session, metrics} o {session:null}.
class CurrentState {
  final Session? session;
  final Metrics? metrics;
  const CurrentState({this.session, this.metrics});

  factory CurrentState.fromJson(Map<String, dynamic> j) {
    final s = asMap(j['session']);
    final m = asMap(j['metrics']);
    return CurrentState(
      session: s == null ? null : Session.fromJson(s),
      metrics: m == null ? null : Metrics.fromJson(m),
    );
  }
}

/// Item de `GET /sessions` (§6): {session, summary}.
class SessionListItem {
  final Session session;
  final SessionSummary? summary;
  const SessionListItem({required this.session, this.summary});

  factory SessionListItem.fromJson(Map<String, dynamic> j) {
    final s = asMap(j['session']) ?? j; // tolerante si viniera plano
    final sum = asMap(j['summary']);
    return SessionListItem(
      session: Session.fromJson(s),
      summary: sum == null ? null : SessionSummary.fromJson(sum),
    );
  }
}

/// Respuesta de `GET /sessions/{id}` (§6): {session, summary, metrics}.
class SessionDetail {
  final Session session;
  final SessionSummary? summary;
  final Metrics? metrics;
  const SessionDetail({required this.session, this.summary, this.metrics});

  factory SessionDetail.fromJson(Map<String, dynamic> j) {
    final s = asMap(j['session']) ?? j;
    final sum = asMap(j['summary']);
    final m = asMap(j['metrics']);
    return SessionDetail(
      session: Session.fromJson(s),
      summary: sum == null ? null : SessionSummary.fromJson(sum),
      metrics: m == null ? null : Metrics.fromJson(m),
    );
  }
}

/// Fichero CSV descargado (bytes + nombre para guardar/compartir).
class CsvFile {
  final List<int> bytes;
  final String filename;
  const CsvFile(this.bytes, this.filename);
}
