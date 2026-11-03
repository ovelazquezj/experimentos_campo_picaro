import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';

import '../app_state.dart';
import '../api/campo_api.dart';
import '../models/models.dart';
import '../theme.dart';
import '../utils/geo.dart';
import 'graficos.dart';
import 'mapa.dart';

/// Replay de una sesion GUARDADA: pide sus uplinks y sus metricas al servidor
/// una sola vez y redibuja el mapa y las graficas con los mismos widgets que la
/// vista en vivo (MapPanel / ChartsPanel).
///
/// Es una FOTO FIJA a proposito: NO escucha el WebSocket, asi que si arranca una
/// sesion nueva mientras la miras, no altera este replay (se actualizan las
/// pestanas en vivo, no esta). El boton de refrescar vuelve a pedir los datos
/// por si estas revisando una sesion que aun captura.
class ReplayScreen extends StatefulWidget {
  final int id;
  final String runLabel;
  final int initialTab; // 0 = Mapa, 1 = Graficos

  const ReplayScreen({
    super.key,
    required this.id,
    required this.runLabel,
    this.initialTab = 0,
  });

  @override
  State<ReplayScreen> createState() => _ReplayScreenState();
}

class _ReplayData {
  final SessionDetail detail;
  final List<Uplink> uplinks;
  _ReplayData(this.detail, this.uplinks);
}

class _ReplayScreenState extends State<ReplayScreen> {
  late Future<_ReplayData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_ReplayData> _load() async {
    final api = context.read<AppState>().api;
    if (api == null) throw ApiException(0, 'Sin configuración');
    // Detalle (trae las metricas) + uplinks (para los puntos y las series).
    final detail = await api.getSession(widget.id);
    final ups = await api.getUplinks(widget.id);
    return _ReplayData(detail, ups);
  }

  void _refresh() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final cfg = context.read<AppState>().config;
    final gw = cfg.hasGateway ? LatLng(cfg.gwLat!, cfg.gwLon!) : null;

    return DefaultTabController(
      length: 2,
      initialIndex: widget.initialTab.clamp(0, 1),
      child: Scaffold(
        appBar: AppBar(
          title: Text(widget.runLabel.isNotEmpty
              ? widget.runLabel
              : 'Sesión ${widget.id}'),
          actions: [
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: 'Volver a pedir los datos',
              onPressed: _refresh,
            ),
          ],
          bottom: const TabBar(
            tabs: [Tab(text: 'Mapa'), Tab(text: 'Gráficos')],
          ),
        ),
        body: FutureBuilder<_ReplayData>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return _CenteredError(
                  message: snap.error.toString(), onRetry: _refresh);
            }
            final data = snap.data!;
            if (data.uplinks.isEmpty) {
              return const _CenteredMessage(
                  'Esta sesión no capturó ningún uplink.');
            }
            // VUELO: solo los P1 con fix aportan punto (ver puntosConFix).
            final points = puntosConFix(data.uplinks);
            return TabBarView(
              children: [
                MapPanel(points: points, gateway: gw),
                ChartsPanel(uplinks: data.uplinks, metrics: data.detail.metrics),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _CenteredMessage extends StatelessWidget {
  final String text;
  const _CenteredMessage(this.text);
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(text,
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textDim)),
        ),
      );
}

class _CenteredError extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _CenteredError({required this.message, required this.onRetry});
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, color: AppColors.textDim, size: 40),
              const SizedBox(height: 12),
              Text(message,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.textDim)),
              const SizedBox(height: 12),
              OutlinedButton(
                  onPressed: onRetry, child: const Text('Reintentar')),
            ],
          ),
        ),
      );
}
