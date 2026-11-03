import '../runs.dart';
import 'json_utils.dart';

/// Estados de la sesion (§3/§4). El servidor los guarda en minusculas/ingles.
enum SessionState { capturing, finished, aborted, unknown }

SessionState _parseState(String? s) {
  switch (s) {
    case 'capturing':
      return SessionState.capturing;
    case 'finished':
      return SessionState.finished;
    case 'aborted':
      return SessionState.aborted;
    default:
      return SessionState.unknown;
  }
}

/// Una sesion de captura (fila de la tabla `sessions`, §4).
class Session {
  final int id;
  final String runLabel; // 20260814-CERRO16-C
  final String scenario; // URBANO | TERRAZA | CERRO16 | VUELO
  // 'class' es palabra reservada en Dart: se mapea a `sessionClass`.
  final String sessionClass; // A | C
  final int expectedFport; // 11..17
  final String profile; // terreno-a | terreno-c
  final SessionState state;
  final int targetUplinks; // 300 (165 en VUELO)
  final double? startedAt; // epoch UTC
  final double? endedAt; // epoch UTC, null si activa
  final String? notes;

  /// Sonda de la sesion (D-65): `tbeam` o `lora32`. Las sesiones anteriores
  /// y los servidores < 1.3.0 no lo mandan: eran todas de la T-Beam.
  final String sonda;

  const Session({
    required this.id,
    required this.runLabel,
    required this.scenario,
    required this.sessionClass,
    required this.expectedFport,
    required this.profile,
    required this.state,
    required this.targetUplinks,
    this.startedAt,
    this.endedAt,
    this.notes,
    this.sonda = kSondaTbeam,
  });

  factory Session.fromJson(Map<String, dynamic> j) {
    final scenario = asString(j['scenario']) ?? '';
    final cls = asString(j['class']) ?? '';
    return Session(
      id: asInt(j['id']) ?? 0,
      runLabel: asString(j['run_label']) ?? '',
      scenario: scenario,
      sessionClass: cls,
      expectedFport: asInt(j['expected_fport']) ?? 0,
      profile: asString(j['profile']) ?? '',
      state: _parseState(asString(j['state'])),
      // Respaldo por corrida si el servidor no lo manda: 300, o 165 en VUELO.
      targetUplinks: asInt(j['target_uplinks']) ??
          findRun(scenario, cls)?.targetUplinks ??
          300,
      startedAt: asDouble(j['started_at']),
      endedAt: asDouble(j['ended_at']),
      notes: asString(j['notes']),
      sonda: asString(j['sonda']) ?? kSondaTbeam,
    );
  }

  bool get isCapturing => state == SessionState.capturing;

  /// La distancia de esta sesion se mide con el GPS del telefono (la sonda no
  /// tiene GPS propio).
  bool get gpsDelTelefono => sonda == kSondaLora32;
  bool get isFinished => state == SessionState.finished;
  bool get isAborted => state == SessionState.aborted;

  /// Corrida VUELO (rafagas de 3 paquetes por fPort 17).
  bool get esVuelo => scenario == kEscenarioVuelo || expectedFport == kFportVuelo;

  /// Etiqueta legible del estado para la UI.
  String get stateLabel {
    switch (state) {
      case SessionState.capturing:
        return 'CAPTURANDO';
      case SessionState.finished:
        return 'FINALIZADA';
      case SessionState.aborted:
        return 'ABORTADA';
      case SessionState.unknown:
        return '—';
    }
  }

  /// Texto tipo menu del device: "CERRO16 · Clase C · fP16".
  String get runTitle => '$scenario · Clase $sessionClass · fP$expectedFport';
}
