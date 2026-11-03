import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../app_state.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/line_chart.dart';

/// ③ Graficos de la sesion ACTIVA. Capa fina sobre [ChartsPanel], que dibuja y
/// se reutiliza en el replay de sesiones guardadas.
class GraficosScreen extends StatelessWidget {
  const GraficosScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final st = context.watch<AppState>();
    return ChartsPanel(uplinks: st.uplinks, metrics: st.currentMetrics);
  }
}

/// Panel de graficos reutilizable: PDR estimado (etiquetado "est."),
/// RSSI/SNR/bateria vs tiempo y resumen numerico (§10). Recibe los uplinks y las
/// metricas por parametro; no depende de AppState. Todo con CustomPainter.
class ChartsPanel extends StatelessWidget {
  final List<Uplink> uplinks;
  final Metrics? metrics;
  const ChartsPanel({super.key, required this.uplinks, required this.metrics});

  @override
  Widget build(BuildContext context) {
    final rssi = <double>[
      for (final u in uplinks)
        if (u.rssi != null) u.rssi!.toDouble(),
    ];
    final snr = <double>[
      for (final u in uplinks)
        if (u.snr != null) u.snr!,
    ];
    // Solo los valores que llegaron: en VUELO un P1/P3 no trae bateria y un
    // null nunca se pinta como 0 (docs/VUELO-ESPEC.md).
    final bat = <double>[
      for (final u in uplinks)
        if (u.batteryV != null) u.batteryV!,
    ];

    // VUELO: series de los sensores que solo viajan en su paquete (P1 altitud,
    // P2 ambiente, P3 velocidad vertical). Cada serie es la secuencia de los
    // paquetes que TRAJERON la magnitud, sin huecos rellenos con 0.
    final vuelo = uplinks.any((u) => u.esVuelo);
    List<double> serie(double? Function(Uplink u) f) => <double>[
          for (final u in uplinks)
            if (f(u) != null) f(u)!,
        ];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _PdrCard(metrics: metrics),
        const SizedBox(height: 8),
        SimpleLineChart(
            title: 'RSSI vs tiempo', values: rssi, color: AppColors.cyan, unit: ' dBm'),
        SimpleLineChart(
            title: 'SNR vs tiempo', values: snr, color: AppColors.gold, unit: ' dB'),
        SimpleLineChart(
            title: 'Batería vs tiempo', values: bat, color: AppColors.green, unit: ' V'),
        if (vuelo) ...[
          SimpleLineChart(
              title: 'Altitud (P1)',
              values: serie((u) => u.altitudeM),
              color: AppColors.cyan,
              unit: ' m'),
          SimpleLineChart(
              title: 'Temperatura (P2)',
              values: serie((u) => u.temperatureC),
              color: AppColors.red,
              unit: ' °C'),
          SimpleLineChart(
              title: 'Presión (P2)',
              values: serie((u) => u.pressureHpa),
              color: AppColors.gold,
              unit: ' hPa'),
          SimpleLineChart(
              title: 'Humedad (P2)',
              values: serie((u) => u.humidityPct?.toDouble()),
              color: AppColors.blue,
              unit: ' %'),
          SimpleLineChart(
              title: 'Velocidad vertical (P3)',
              values: serie((u) => u.vspeedMs),
              color: AppColors.green,
              unit: ' m/s'),
        ],
        const SizedBox(height: 8),
        _SummaryCard(metrics: metrics),
      ],
    );
  }
}

class _PdrCard extends StatelessWidget {
  final Metrics? metrics;
  const _PdrCard({required this.metrics});

  @override
  Widget build(BuildContext context) {
    final pdr = metrics?.pdrEst;
    final pct = pdr != null ? (pdr * 100).toStringAsFixed(1) : '--';
    final progress = metrics?.progressPct;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('PDR (est.)',
                    style: TextStyle(color: AppColors.textDim, fontSize: 13)),
                Text('$pct%',
                    style: const TextStyle(
                        color: AppColors.gold,
                        fontSize: 40,
                        fontWeight: FontWeight.bold)),
                const Text('estimado sobre lo recibido',
                    style: TextStyle(color: AppColors.textDim, fontSize: 11)),
              ],
            ),
            const Spacer(),
            SizedBox(
              width: 90,
              height: 90,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 90,
                    height: 90,
                    child: CircularProgressIndicator(
                      value: progress != null
                          ? (progress / 100).clamp(0.0, 1.0)
                          : null,
                      strokeWidth: 8,
                      backgroundColor: const Color(0x22FFFFFF),
                      valueColor:
                          const AlwaysStoppedAnimation(AppColors.cyan),
                    ),
                  ),
                  Text(
                    progress != null ? '${progress.toStringAsFixed(0)}%' : '—',
                    style: const TextStyle(
                        color: AppColors.text, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final Metrics? metrics;
  const _SummaryCard({required this.metrics});

  @override
  Widget build(BuildContext context) {
    final m = metrics;
    final rows = <List<String>>[
      ['Recibidos', '${m?.received ?? 0}'],
      ['Último fCnt', '${m?.lastFcnt ?? '--'}'],
      ['Huecos (gaps)', '${m?.gaps ?? 0}'],
      ['RSSI medio', m?.rssiMean != null ? '${m!.rssiMean!.toStringAsFixed(1)} dBm' : '--'],
      ['SNR medio', m?.snrMean != null ? '${m!.snrMean!.toStringAsFixed(1)} dB' : '--'],
      ['Dist. GW máx', m?.distGwKmMax != null ? '${m!.distGwKmMax!.toStringAsFixed(1)} km' : '--'],
      ['Progreso', m?.progressPct != null ? '${m!.progressPct!.toStringAsFixed(1)} %' : '--'],
      // Bloque `vuelo` de las metricas: solo si el servidor lo manda.
      if (m?.vuelo != null) ...[
        ['Ráfagas completas', '${m!.vuelo!.completas ?? '--'}'],
        ['Ráfagas parciales', '${m.vuelo!.parciales ?? '--'}'],
        ['Ráfagas perdidas', '${m.vuelo!.perdidas ?? '--'}'],
        [
          'P1 / P2 / P3',
          '${m.vuelo!.p1 ?? '--'} / ${m.vuelo!.p2 ?? '--'} / ${m.vuelo!.p3 ?? '--'}'
        ],
      ],
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Resumen numérico',
                style: TextStyle(
                    color: AppColors.text, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            ...rows.map((r) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(r[0],
                          style: const TextStyle(color: AppColors.textDim)),
                      Text(r[1],
                          style: const TextStyle(
                              color: AppColors.text,
                              fontWeight: FontWeight.w600)),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }
}
