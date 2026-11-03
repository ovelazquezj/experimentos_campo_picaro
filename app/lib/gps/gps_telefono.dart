import 'dart:async';

import 'package:geolocator/geolocator.dart';

/// Un fix del GPS del telefono, en la forma que espera el microservicio
/// (`POST /session/{id}/posicion`, CONTRATO-CAMPO §17).
class FixTelefono {
  final double lat;
  final double lon;
  final double? altM;
  final double? precisionM;
  final DateTime ts;

  const FixTelefono({
    required this.lat,
    required this.lon,
    this.altM,
    this.precisionM,
    required this.ts,
  });

  Map<String, dynamic> toJson() => {
        'lat': lat,
        'lon': lon,
        if (altM != null) 'alt_m': altM,
        if (precisionM != null) 'precision_m': precisionM,
        'ts': ts.millisecondsSinceEpoch / 1000.0,
      };
}

/// GPS del telefono para las sondas sin GPS propio (D-65: la T3).
///
/// Escucha el flujo de posiciones del sistema y entrega por [alFix] como mucho
/// un fix cada [cadencia]: la sonda manda un paquete cada 20 s y una posicion
/// cada 30 s basta para emparejar cada uplink con donde estaba el telefono,
/// sin gastar bateria ni datos de mas.
class GpsTelefono {
  final void Function(FixTelefono fix) alFix;
  final void Function(String? aviso) alCambiarAviso;
  final Duration cadencia;

  GpsTelefono({
    required this.alFix,
    required this.alCambiarAviso,
    this.cadencia = const Duration(seconds: 30),
  });

  StreamSubscription<Position>? _sub;
  DateTime? _ultimoEnvio;
  FixTelefono? _ultimo;

  bool get activo => _sub != null;

  /// Ultimo fix recibido del sistema (se haya enviado o no).
  FixTelefono? get ultimo => _ultimo;

  /// Pide permiso si hace falta y empieza a escuchar. Si el GPS esta apagado o
  /// el permiso se niega, lo dice por [alCambiarAviso] y no escucha.
  Future<void> iniciar() async {
    if (_sub != null) return;
    if (!await Geolocator.isLocationServiceEnabled()) {
      alCambiarAviso('La ubicación del teléfono está apagada: '
          'sin ella no se mide la distancia al gateway.');
      return;
    }
    var permiso = await Geolocator.checkPermission();
    if (permiso == LocationPermission.denied) {
      permiso = await Geolocator.requestPermission();
    }
    if (permiso == LocationPermission.denied ||
        permiso == LocationPermission.deniedForever) {
      alCambiarAviso('Sin permiso de ubicación: '
          'no se mide la distancia al gateway.');
      return;
    }
    alCambiarAviso(null);
    _ultimoEnvio = null;
    _sub = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 0,
      ),
    ).listen(_alPosicion, onError: (Object e) {
      alCambiarAviso('GPS del teléfono: $e');
    });
  }

  void _alPosicion(Position p) {
    final fix = FixTelefono(
      lat: p.latitude,
      lon: p.longitude,
      altM: p.altitude,
      precisionM: p.accuracy,
      ts: p.timestamp,
    );
    _ultimo = fix;
    final ahora = DateTime.now();
    final previo = _ultimoEnvio;
    if (previo != null && ahora.difference(previo) < cadencia) return;
    _ultimoEnvio = ahora;
    alFix(fix);
  }

  Future<void> detener() async {
    await _sub?.cancel();
    _sub = null;
  }
}
