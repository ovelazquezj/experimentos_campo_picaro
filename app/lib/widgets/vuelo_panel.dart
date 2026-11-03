import 'package:flutter/material.dart';

import '../models/models.dart';
import '../theme.dart';

/// Bloque del panel para la corrida VUELO (docs/VUELO-ESPEC.md).
///
/// Cada uplink de VUELO trae solo un trozo de la lectura (P1 posicion, P2
/// ambiente/energia, P3 navegacion). Aqui se pinta la **lectura reconstruida**:
/// cada magnitud con el ultimo valor que la trajo, y a su lado de que rafaga
/// es, para que se vea si un dato se ha quedado viejo (p. ej. se pierden todos
/// los P1 y la posicion sigue siendo la de la rafaga 3). Nunca se pinta un null
/// como 0: lo que no ha llegado nunca es «--».
class VueloPanel extends StatelessWidget {
  final LecturaVuelo lectura;
  final Metrics? metrics;

  /// Rafagas que cierran la corrida (55).
  final int rafagasObjetivo;

  const VueloPanel({
    super.key,
    required this.lectura,
    required this.metrics,
    required this.rafagasObjetivo,
  });

  @override
  Widget build(BuildContext context) {
    final l = lectura;
    final mv = metrics?.vuelo;

    // Rafaga en curso: la del ultimo uplink (0..54, se pinta 1..55). Si el
    // servidor no expone `rafaga`, se estima con los enviados (3 por rafaga) y
    // se marca con «≈».
    String rafagaTxt;
    final r = l.rafagaActual ?? mv?.rafagaUltima;
    if (r != null) {
      rafagaTxt = '${r + 1}/$rafagasObjetivo';
    } else if ((metrics?.sentEst ?? 0) > 0) {
      rafagaTxt = '≈${(metrics!.sentEst - 1) ~/ 3 + 1}/$rafagasObjetivo';
    } else {
      rafagaTxt = '--/$rafagasObjetivo';
    }
    final tipoTxt = l.tipoActual != null ? ' · ${etiquetaTipo(l.tipoActual)}' : '';

    // Completas / parciales: del servidor si manda el bloque `vuelo`; si no,
    // el calculo local (solo posible si el servidor expone `rafaga`).
    final completas = mv?.completas ?? l.rafagasCompletasLocal;
    final parciales = mv?.parciales ?? l.rafagasParcialesLocal;
    final origen = mv != null ? '' : ' (app)';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.oledBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0x334A7DFF)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('ráfaga $rafagaTxt$tipoTxt',
              style: const TextStyle(
                  fontFamily: 'monospace',
                  color: AppColors.gold,
                  fontSize: 16,
                  fontWeight: FontWeight.bold)),
          if (completas != null || parciales != null || mv?.perdidas != null)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                'completas ${completas ?? '--'} · parciales ${parciales ?? '--'}'
                '${mv?.perdidas != null ? ' · perdidas ${mv!.perdidas}' : ''}'
                '$origen',
                style: const TextStyle(
                    fontFamily: 'monospace',
                    color: AppColors.textDim,
                    fontSize: 12),
              ),
            ),
          if (mv != null && (mv.p1 != null || mv.p2 != null || mv.p3 != null))
            Text(
              'P1 ${mv.p1 ?? '--'} · P2 ${mv.p2 ?? '--'} · P3 ${mv.p3 ?? '--'}',
              style: const TextStyle(
                  fontFamily: 'monospace',
                  color: AppColors.textDim,
                  fontSize: 12),
            ),
          const SizedBox(height: 8),
          _fila('Posición', _pos(l), l.latitude),
          _fila('Altitud', _num(l.altitudeM, 0, ' m'), l.altitudeM),
          _fila('Temp.', _num(l.temperatureC, 1, ' °C'), l.temperatureC),
          _fila('Presión', _num(l.pressureHpa, 1, ' hPa'), l.pressureHpa),
          _fila('Humedad', _num(l.humidityPct, 0, ' %'), l.humidityPct),
          _fila('Vel. vert.', _vspeed(l.vspeedMs), l.vspeedMs),
          _fila('Rumbo', _num(l.headingDeg, 0, '°'), l.headingDeg),
          _fila('Velocidad', _num(l.speedKmh, 1, ' km/h'), l.speedKmh),
          _fila('HDOP', _num(l.hdop, 1, ''), l.hdop),
        ],
      ),
    );
  }

  static String _pos(LecturaVuelo l) {
    final lat = l.latitude?.valor;
    final lon = l.longitude?.valor;
    if (lat == null || lon == null) return '--';
    return '${lat.toStringAsFixed(5)}, ${lon.toStringAsFixed(5)}';
  }

  static String _num(Ultimo<num>? u, int dec, String unidad) =>
      u == null ? '--' : '${u.valor.toStringAsFixed(dec)}$unidad';

  static String _vspeed(Ultimo<double>? u) {
    if (u == null) return '--';
    final v = u.valor;
    final signo = v > 0 ? '+' : '';
    return '$signo${v.toStringAsFixed(1)} m/s';
  }

  /// Fila con el valor y, a la derecha, el paquete y la rafaga de origen.
  Widget _fila(String etiqueta, String valor, Ultimo<Object>? origen) {
    final r = origen?.rafaga;
    final de = origen == null
        ? ''
        : '${etiquetaTipo(origen.tipo)}${r != null ? ' r${r + 1}' : ''}';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        children: [
          SizedBox(
            width: 92,
            child: Text(etiqueta,
                style: const TextStyle(
                    fontFamily: 'monospace',
                    color: AppColors.textDim,
                    fontSize: 13)),
          ),
          Expanded(
            child: Text(valor,
                style: const TextStyle(
                    fontFamily: 'monospace',
                    color: AppColors.cyan,
                    fontSize: 14,
                    fontWeight: FontWeight.w600)),
          ),
          Text(de,
              style: const TextStyle(
                  fontFamily: 'monospace',
                  color: AppColors.textDim,
                  fontSize: 11)),
        ],
      ),
    );
  }
}
