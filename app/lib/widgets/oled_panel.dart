import 'package:flutter/material.dart';

import '../config.dart';
import '../models/models.dart';
import '../theme.dart';

/// Reproduce lo que muestra la OLED del device (§7 del manual) con los datos que
/// llegan por WebSocket: TX n/300, RSSI, SNR, GPS/sats, bateria (— si es null),
/// ultimo downlink. Estilo monoespaciado, verde/cian sobre negro.
class OledPanel extends StatelessWidget {
  final Session? session;
  final Metrics? metrics;
  final String? lastDownlink;

  /// Solo en VUELO: ultimo valor conocido de cada magnitud. Las metricas del
  /// servidor copian bateria/GPS del ULTIMO uplink, y en VUELO ese puede ser un
  /// P1 o un P3 sin bateria — se pintaria «--» cada dos de tres paquetes. Con
  /// esto se toma del ultimo paquete que la trajo. Null = corridas clasicas,
  /// sin cambios.
  final LecturaVuelo? lectura;

  const OledPanel({
    super.key,
    required this.session,
    required this.metrics,
    required this.lastDownlink,
    this.lectura,
  });

  @override
  Widget build(BuildContext context) {
    final m = metrics;
    final s = session;

    final target = s?.targetUplinks ?? kDefaultTargetUplinks;
    // TX n/300 = enviados desde el inicio de la SESION (received + gaps, §12.3
    // del contrato), igual que la OLED del device. Nunca el fCnt absoluto
    // (lastFcnt): ese no se reinicia entre corridas si la sonda no re-joinea y
    // acumulaba lo de la corrida anterior (301/300, 302/300, …).
    final tx = m?.sentEst ?? 0;
    final received = m?.received ?? 0;

    final rssi = m?.rssiLast != null
        ? '${m!.rssiLast} dBm'
        : (m?.rssiMean != null ? '${m!.rssiMean!.toStringAsFixed(0)} dBm' : '--');
    final snr = m?.snrMean != null ? '${m!.snrMean!.toStringAsFixed(1)} dB' : '--';

    final l = lectura;
    final gpsFix = l?.gpsFix?.valor ?? m?.gpsFix;
    final sats = l?.satellites?.valor ?? m?.satellites;
    final batteryPct = l?.batteryPct?.valor ?? m?.batteryPct;
    final batteryV = l?.batteryV?.valor ?? m?.batteryV;

    final gps = (gpsFix == true)
        ? (sats != null ? 'FIX  s:$sats' : 'FIX')
        : (gpsFix == false ? 'sin fix' : '--');

    // Bateria: "--" si battery_pct es null (no tratar como 0). Los mV, si hay.
    final batPct = batteryPct != null ? '$batteryPct%' : '--';
    final batMv = batteryV != null ? '${(batteryV * 1000).round()} mV' : '';

    final dl = (lastDownlink != null && lastDownlink!.isNotEmpty)
        ? lastDownlink!
        : '--';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.oledBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0x334A7DFF)),
      ),
      child: DefaultTextStyle(
        style: const TextStyle(
          fontFamily: 'monospace',
          color: AppColors.cyan,
          fontSize: 15,
          height: 1.5,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              s?.runLabel.isNotEmpty == true ? s!.runLabel : 'SIN SESIÓN',
              style: const TextStyle(
                fontFamily: 'monospace',
                color: AppColors.gold,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 6),
            _row('TX', '$tx/$target', 'RX', '$received'),
            _row('RSSI', rssi, 'SNR', snr),
            _row('GPS', gps, 'Bat', batMv.isEmpty ? batPct : '$batPct $batMv'),
            _row('PDR est', _pdr(m), 'gaps', '${m?.gaps ?? 0}'),
            _row('dist', _dist(m), 'DL', dl),
          ],
        ),
      ),
    );
  }

  String _pdr(Metrics? m) =>
      m?.pdrEst != null ? '${(m!.pdrEst! * 100).toStringAsFixed(0)}%' : '--';

  String _dist(Metrics? m) => m?.distGwKmMax != null
      ? '${m!.distGwKmMax!.toStringAsFixed(1)} km'
      : '--';

  Widget _row(String l1, String v1, String l2, String v2) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: _cell(l1, v1)),
          Expanded(child: _cell(l2, v2)),
        ],
      ),
    );
  }

  Widget _cell(String label, String value) {
    return RichText(
      text: TextSpan(
        style: const TextStyle(
            fontFamily: 'monospace', fontSize: 15, height: 1.5),
        children: [
          TextSpan(
            text: '$label ',
            style: const TextStyle(color: AppColors.textDim),
          ),
          TextSpan(
            text: value,
            style: const TextStyle(
                color: AppColors.cyan, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
