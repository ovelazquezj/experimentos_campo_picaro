import 'dart:math' as math;

import 'package:latlong2/latlong.dart';

import '../models/uplink.dart';

/// Puntos del track: solo uplinks con posicion valida ([Uplink.hasFixPoint]).
/// En VUELO los P2/P3 no traen posicion y un P1 sin fix trae null: ninguno
/// aporta punto, asi que el track une las posiciones REALES de los P1 y el
/// ultimo punto es la ultima posicion conocida. Nunca se pinta un 0,0.
List<LatLng> puntosConFix(Iterable<Uplink> uplinks) => <LatLng>[
      for (final u in uplinks)
        if (u.hasFixPoint) LatLng(u.latitude!, u.longitude!),
    ];

/// Distancia haversine en metros entre dos puntos (lat/lon en grados).
/// Se usa en el mapa de respaldo (CustomPainter) para dibujar la barra de escala.
double haversineMeters(double lat1, double lon1, double lat2, double lon2) {
  const r = 6371000.0; // radio terrestre medio (m)
  final dLat = _rad(lat2 - lat1);
  final dLon = _rad(lon2 - lon1);
  final a = math.sin(dLat / 2) * math.sin(dLat / 2) +
      math.cos(_rad(lat1)) *
          math.cos(_rad(lat2)) *
          math.sin(dLon / 2) *
          math.sin(dLon / 2);
  final c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
  return r * c;
}

double _rad(double deg) => deg * math.pi / 180.0;
