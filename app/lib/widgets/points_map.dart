import 'dart:math' as math;

import 'package:flutter/material.dart';
// latlong2 exporta su propio `Path` (geodesico) que colisiona con el Path del
// canvas (dart:ui). Lo ocultamos: aqui solo se usa LatLng.
import 'package:latlong2/latlong.dart' hide Path;

import '../theme.dart';
import '../utils/geo.dart';

/// Mapa de respaldo sin red: dibuja los puntos y una barra de escala en un
/// CustomPainter. Se usa cuando no hay tiles (§10: "que NUNCA rompa la app por
/// falta de red de tiles").
class OfflinePointsMap extends StatelessWidget {
  final List<LatLng> points;
  final LatLng? gateway;

  const OfflinePointsMap({super.key, required this.points, this.gateway});

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty && gateway == null) {
      return const Center(
        child: Text('Sin puntos con fix GPS todavía.',
            style: TextStyle(color: AppColors.textDim)),
      );
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        return CustomPaint(
          size: Size(constraints.maxWidth, constraints.maxHeight),
          painter: _PointsPainter(points: points, gateway: gateway),
        );
      },
    );
  }
}

class _PointsPainter extends CustomPainter {
  final List<LatLng> points;
  final LatLng? gateway;

  _PointsPainter({required this.points, this.gateway});

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = AppColors.oledBg,
    );

    final all = <LatLng>[...points];
    if (gateway != null) all.add(gateway!);
    if (all.isEmpty) return;

    // Bounding box.
    double minLat = all.first.latitude, maxLat = all.first.latitude;
    double minLon = all.first.longitude, maxLon = all.first.longitude;
    for (final p in all) {
      minLat = p.latitude < minLat ? p.latitude : minLat;
      maxLat = p.latitude > maxLat ? p.latitude : maxLat;
      minLon = p.longitude < minLon ? p.longitude : minLon;
      maxLon = p.longitude > maxLon ? p.longitude : maxLon;
    }

    const pad = 28.0;
    final w = size.width - 2 * pad;
    final h = size.height - 2 * pad;
    // Evita division por cero cuando todos los puntos coinciden.
    final spanLat = (maxLat - minLat).abs() < 1e-9 ? 1e-9 : (maxLat - minLat);
    final spanLon = (maxLon - minLon).abs() < 1e-9 ? 1e-9 : (maxLon - minLon);

    Offset project(LatLng p) {
      final x = pad + (p.longitude - minLon) / spanLon * w;
      // Latitud crece hacia arriba => invertir eje Y.
      final y = pad + (maxLat - p.latitude) / spanLat * h;
      return Offset(x, y);
    }

    // Track.
    if (points.length >= 2) {
      final path = Path()..moveTo(project(points.first).dx, project(points.first).dy);
      for (final p in points.skip(1)) {
        final o = project(p);
        path.lineTo(o.dx, o.dy);
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = AppColors.cyan.withOpacity(0.7)
          ..strokeWidth = 2
          ..style = PaintingStyle.stroke,
      );
    }

    // Puntos.
    final dot = Paint()..color = AppColors.cyan;
    for (final p in points) {
      canvas.drawCircle(project(p), 3, dot);
    }
    // Ultimo punto destacado.
    if (points.isNotEmpty) {
      canvas.drawCircle(project(points.last), 6, Paint()..color = AppColors.gold);
    }
    // Gateway.
    if (gateway != null) {
      final o = project(gateway!);
      final gw = Paint()..color = AppColors.red;
      canvas.drawCircle(o, 7, gw);
      _label(canvas, o + const Offset(9, -6), 'GW');
    }

    _drawScaleBar(canvas, size, minLat, minLon, maxLon, w, pad);
  }

  void _drawScaleBar(Canvas canvas, Size size, double lat, double minLon,
      double maxLon, double w, double pad) {
    // Metros que abarca el ancho util del lienzo.
    final totalM = haversineMeters(lat, minLon, lat, maxLon);
    if (totalM <= 0) return;
    // Elige una longitud "redonda" para la barra (<= 1/3 del ancho).
    final targetM = totalM / 3;
    final niceM = _niceNumber(targetM);
    final barPx = niceM / totalM * w;
    final y = size.height - 16;
    final x0 = pad;
    final paint = Paint()
      ..color = AppColors.text
      ..strokeWidth = 2;
    canvas.drawLine(Offset(x0, y), Offset(x0 + barPx, y), paint);
    canvas.drawLine(Offset(x0, y - 4), Offset(x0, y + 4), paint);
    canvas.drawLine(Offset(x0 + barPx, y - 4), Offset(x0 + barPx, y + 4), paint);
    _label(canvas, Offset(x0, y - 18), _fmtDist(niceM));
  }

  /// Redondea a un "numero bonito" 1/2/5 * 10^k (para la barra de escala).
  double _niceNumber(double v) {
    if (v <= 0) return 1;
    final magnitude = math.pow(10, (math.log(v) / math.ln10).floor()).toDouble();
    final norm = v / magnitude; // en [1, 10)
    final double nice;
    if (norm < 1.5) {
      nice = 1;
    } else if (norm < 3.5) {
      nice = 2;
    } else if (norm < 7.5) {
      nice = 5;
    } else {
      nice = 10;
    }
    return nice * magnitude;
  }

  String _fmtDist(double m) =>
      m >= 1000 ? '${(m / 1000).toStringAsFixed(m >= 10000 ? 0 : 1)} km' : '${m.round()} m';

  void _label(Canvas canvas, Offset at, String text) {
    final tp = TextPainter(
      text: TextSpan(
          text: text,
          style: const TextStyle(color: AppColors.text, fontSize: 11)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, at);
  }

  @override
  bool shouldRepaint(covariant _PointsPainter old) =>
      old.points != points || old.gateway != gateway;
}
