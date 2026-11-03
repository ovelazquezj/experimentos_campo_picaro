/// Las corridas de la campana (§5). Mismas opciones que el menu del device.
///
/// **El indice en [kRuns] ES el `modo` del contrato BLE (§4.2)**: 0..5 son las
/// seis corridas originales (escenario × clase A/C) y 6 es VUELO, que solo
/// existe en Clase A (docs/VUELO-ESPEC.md). Nunca reordenar: la sonda y la app
/// tienen que hablar del mismo numero.
class RunDef {
  final String scenario; // URBANO | TERRAZA | CERRO16 | VUELO
  final String cls; // A | C
  final int fPort; // 11..17
  final String profile; // terreno-a | terreno-c
  final String radio; // "DR1/SF9"
  final int payloadBytes;

  /// Uplinks que cierran la corrida (`target_uplinks`). El servidor manda el
  /// real por sesion; esto es solo el respaldo mientras no llega.
  final int targetUplinks;

  /// Paquetes por lectura. 1 en las corridas clasicas; en VUELO cada lectura
  /// viaja en una **rafaga** de 3 (P1 posicion, P2 ambiente, P3 navegacion),
  /// asi que un uplink suelto trae solo parte de la lectura.
  final int paquetesPorRafaga;

  const RunDef(
    this.scenario,
    this.cls,
    this.fPort,
    this.profile,
    this.radio,
    this.payloadBytes, {
    this.targetUplinks = 300,
    this.paquetesPorRafaga = 1,
  });

  String get label => '$scenario $cls';
  String get subtitle => esRafagas
      ? 'fP$fPort · $radio · $rafagasObjetivo ráfagas'
      : 'fP$fPort · $radio';

  /// Corrida por rafagas (VUELO): cada uplink es un trozo de la lectura.
  bool get esRafagas => paquetesPorRafaga > 1;

  /// Rafagas que completan la corrida (55 en VUELO = 165 / 3).
  int get rafagasObjetivo => targetUplinks ~/ paquetesPorRafaga;
}

/// Escenario de la corrida por rafagas (docs/VUELO-ESPEC.md).
const String kEscenarioVuelo = 'VUELO';

/// fPort de VUELO: todos los paquetes de la rafaga (P1, P2 y P3) van por el 17.
const int kFportVuelo = 17;

const List<RunDef> kRuns = [
  RunDef('URBANO', 'A', 11, 'terreno-a', 'DR1/SF9', 14), // modo 0
  RunDef('URBANO', 'C', 12, 'terreno-c', 'DR1/SF9', 14), // modo 1
  RunDef('TERRAZA', 'A', 13, 'terreno-a', 'DR3/SF7', 14), // modo 2
  RunDef('TERRAZA', 'C', 14, 'terreno-c', 'DR3/SF7', 14), // modo 3
  RunDef('CERRO16', 'A', 15, 'terreno-a', 'DR0/SF10', 11), // modo 4
  RunDef('CERRO16', 'C', 16, 'terreno-c', 'DR0/SF10', 11), // modo 5
  // modo 6 — solo Clase A. 55 rafagas × 3 paquetes = 165 uplinks.
  RunDef(kEscenarioVuelo, 'A', kFportVuelo, 'terreno-a', 'DR0/SF10', 11,
      targetUplinks: 165, paquetesPorRafaga: 3),
];

/// Sondas que conoce el microservicio (D-65). La T-Beam corre todas las
/// corridas; la T3 (LoRa32) no tiene sensores, su firmware esta fijo en
/// VUELO-A y el servidor rechaza cualquier otra corrida para ella.
const String kSondaTbeam = 'tbeam';
const String kSondaLora32 = 'lora32';

/// ¿Puede la [sonda] correr [r]?
bool corridaAdmitida(RunDef r, String sonda) =>
    sonda != kSondaLora32 || (r.scenario == kEscenarioVuelo && r.cls == 'A');

RunDef? findRun(String scenario, String cls) {
  for (final r in kRuns) {
    if (r.scenario == scenario && r.cls == cls) return r;
  }
  return null;
}

/// Indice de la corrida en [kRuns], que es su `modo` BLE (§4.2). Null si no
/// existe (p. ej. `VUELO C`).
int? modoDeCorrida(String scenario, String cls) {
  for (var i = 0; i < kRuns.length; i++) {
    if (kRuns[i].scenario == scenario && kRuns[i].cls == cls) return i;
  }
  return null;
}

/// Corrida de un `modo` BLE, o null si esta fuera de la tabla.
RunDef? corridaDeModo(int? modo) =>
    (modo == null || modo < 0 || modo >= kRuns.length) ? null : kRuns[modo];

/// Escenarios en el orden del menu, sin repetir. La UI agrupa por escenario:
/// no todos tienen A y C (VUELO solo A), asi que no se puede suponer pares.
List<String> get escenariosEnOrden {
  final out = <String>[];
  for (final r in kRuns) {
    if (!out.contains(r.scenario)) out.add(r.scenario);
  }
  return out;
}
