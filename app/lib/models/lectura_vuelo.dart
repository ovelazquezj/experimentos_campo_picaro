import 'uplink.dart';

/// Un valor con la rafaga y el paquete que lo trajeron. Sirve para que la UI
/// pueda decir de cuando es el dato, no solo cual es.
class Ultimo<T> {
  final T valor;
  final int? rafaga;
  final TipoPaquete? tipo;
  const Ultimo(this.valor, this.rafaga, this.tipo);
}

/// **Ultimo valor conocido de cada magnitud** a partir de una secuencia de
/// uplinks (docs/VUELO-ESPEC.md, «Consecuencia para quien consume»).
///
/// En VUELO cada uplink trae solo un trozo de la lectura: P1 la posicion, P2 el
/// ambiente y la energia, P3 la navegacion. Lo que un paquete no trae llega como
/// null, y ese null significa «este paquete no lo lleva», **no** «el valor es
/// 0». Aqui cada magnitud se queda con el ultimo paquete que la trajo de verdad;
/// si nunca llego, queda null y la UI pinta «--».
///
/// Es una funcion pura sobre la lista (≤ 2000 uplinks en memoria): se recalcula
/// en cada build sin estado que se pueda desincronizar.
class LecturaVuelo {
  Ultimo<double>? latitude; // lat y lon siempre juntas (de un P1 con fix)
  Ultimo<double>? longitude;
  Ultimo<double>? altitudeM;
  Ultimo<bool>? gpsFix;
  Ultimo<int>? satellites;
  Ultimo<double>? batteryV;
  Ultimo<int>? batteryPct;
  Ultimo<bool>? charging;
  Ultimo<bool>? usbPowered;
  Ultimo<double>? temperatureC;
  Ultimo<double>? pressureHpa;
  Ultimo<int>? humidityPct;
  Ultimo<double>? speedKmh;
  Ultimo<double>? headingDeg;
  Ultimo<double>? hdop;
  Ultimo<double>? vspeedMs;
  Ultimo<int>? uptimeS;

  /// Rafaga y tipo del ULTIMO uplink recibido (lo que se esta oyendo ahora).
  int? rafagaActual;
  TipoPaquete? tipoActual;

  /// Paquetes distintos (por fCnt) vistos en cada rafaga. Solo se llena si el
  /// servidor expone `rafaga`; sirve de respaldo cuando las metricas no traen
  /// el bloque `vuelo`.
  final Map<int, Set<int>> _paquetesPorRafaga = {};

  LecturaVuelo._();

  factory LecturaVuelo.desde(Iterable<Uplink> uplinks) {
    final l = LecturaVuelo._();
    for (final u in uplinks) {
      l._aplicar(u);
    }
    return l;
  }

  void _aplicar(Uplink u) {
    final r = u.rafaga;
    final t = u.tipoEfectivo;
    Ultimo<T>? nuevo<T>(T? v, Ultimo<T>? previo) =>
        v == null ? previo : Ultimo<T>(v, r, t);

    // Posicion: solo de un punto valido. Un P1 sin fix trae lat/lon null y
    // un 0,0 nunca es un dato: se conserva la ultima posicion buena.
    if (u.hasFixPoint) {
      latitude = Ultimo(u.latitude!, r, t);
      longitude = Ultimo(u.longitude!, r, t);
    }
    altitudeM = nuevo(u.altitudeM, altitudeM);
    gpsFix = nuevo(u.gpsFix, gpsFix);
    satellites = nuevo(u.satellites, satellites);
    batteryV = nuevo(u.batteryV, batteryV);
    batteryPct = nuevo(u.batteryPct, batteryPct);
    charging = nuevo(u.charging, charging);
    usbPowered = nuevo(u.usbPowered, usbPowered);
    temperatureC = nuevo(u.temperatureC, temperatureC);
    pressureHpa = nuevo(u.pressureHpa, pressureHpa);
    humidityPct = nuevo(u.humidityPct, humidityPct);
    speedKmh = nuevo(u.speedKmh, speedKmh);
    headingDeg = nuevo(u.headingDeg, headingDeg);
    hdop = nuevo(u.hdop, hdop);
    vspeedMs = nuevo(u.vspeedMs, vspeedMs);
    uptimeS = nuevo(u.uptimeS, uptimeS);

    rafagaActual = r ?? rafagaActual;
    tipoActual = t;
    if (r != null) {
      (_paquetesPorRafaga[r] ??= <int>{}).add(u.fCnt ?? u.hashCode);
    }
  }

  /// Rafagas con los 3 paquetes recibidos (calculo local, ver
  /// [_paquetesPorRafaga]). Null si el servidor no expone `rafaga`.
  int? get rafagasCompletasLocal => _paquetesPorRafaga.isEmpty
      ? null
      : _paquetesPorRafaga.values.where((s) => s.length >= 3).length;

  /// Rafagas con 1 o 2 paquetes recibidos (calculo local).
  int? get rafagasParcialesLocal => _paquetesPorRafaga.isEmpty
      ? null
      : _paquetesPorRafaga.values.where((s) => s.length < 3).length;
}
