import 'package:flutter/material.dart';

import '../gps/gps_telefono.dart';
import '../models/models.dart';
import '../theme.dart';

/// Distancia al gateway medida con el GPS del telefono (D-65).
///
/// Para las sondas sin GPS propio (la T3). La posicion es la del telefono, que
/// va junto a la sonda; la distancia la calcula el servidor contra el gateway
/// que recibio el ultimo paquete, y la guarda con la sesion.
class DistanciaTelefono extends StatelessWidget {
  final Metrics? metrics;

  /// Ultimo fix del telefono aun no reflejado en las metricas.
  final FixTelefono? fixLocal;
  final String? aviso;

  const DistanciaTelefono({
    super.key,
    required this.metrics,
    required this.fixLocal,
    required this.aviso,
  });

  @override
  Widget build(BuildContext context) {
    final m = metrics;
    final pos = m?.posicionTelefono;
    final lat = fixLocal?.lat ?? pos?.lat;
    final lon = fixLocal?.lon ?? pos?.lon;
    final prec = fixLocal?.precisionM ?? pos?.precisionM;

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
          Text(
            m?.distGwKmUltima != null
                ? '${m!.distGwKmUltima!.toStringAsFixed(2)} km al gateway'
                : '-- km al gateway',
            style: const TextStyle(
                fontFamily: 'monospace',
                color: AppColors.gold,
                fontSize: 16,
                fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          _fila('Máxima', m?.distGwKmMax != null
              ? '${m!.distGwKmMax!.toStringAsFixed(1)} km'
              : '--'),
          _fila('Gateway', m?.gatewayUltimo ?? '--'),
          _fila('Teléfono', lat != null && lon != null
              ? '${lat.toStringAsFixed(5)}, ${lon.toStringAsFixed(5)}'
              : '--'),
          _fila('Precisión', prec != null ? '±${prec.toStringAsFixed(0)} m' : '--'),
          if (aviso != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(aviso!,
                  style: const TextStyle(color: AppColors.gold, fontSize: 12)),
            ),
        ],
      ),
    );
  }

  Widget _fila(String etiqueta, String valor) => Padding(
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
          ],
        ),
      );
}
