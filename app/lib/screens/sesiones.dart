import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

import '../app_state.dart';
import '../api/campo_api.dart';
import '../models/models.dart';
import '../theme.dart';
import 'replay.dart';

/// ④ Sesiones: lista con resumen (GET /sessions); al tocar, detalle; boton para
/// descargar y compartir el CSV (§10).
class SesionesScreen extends StatefulWidget {
  const SesionesScreen({super.key});

  @override
  State<SesionesScreen> createState() => _SesionesScreenState();
}

class _SesionesScreenState extends State<SesionesScreen> {
  late Future<List<SessionListItem>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<SessionListItem>> _load() {
    final api = context.read<AppState>().api;
    if (api == null) return Future.value(const []);
    return api.getSessions();
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sesiones')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<SessionListItem>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return _ErrorView(
                  message: snap.error.toString(), onRetry: _refresh);
            }
            final items = snap.data ?? const [];
            if (items.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 120),
                  Center(
                    child: Text('No hay sesiones todavía.',
                        style: TextStyle(color: AppColors.textDim)),
                  ),
                ],
              );
            }
            return ListView.separated(
              itemCount: items.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) =>
                  _SessionTile(item: items[i], onChanged: _refresh),
            );
          },
        ),
      ),
    );
  }
}

class _SessionTile extends StatelessWidget {
  final SessionListItem item;
  final VoidCallback onChanged;
  const _SessionTile({required this.item, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final s = item.session;
    final sum = item.summary;
    final pdr = sum?.pdrEst != null
        ? '${(sum!.pdrEst! * 100).toStringAsFixed(0)}% est.'
        : '';
    return ListTile(
      leading: _StateBadge(state: s.stateLabel, color: _stateColor(s)),
      title: Text(s.runLabel.isNotEmpty ? s.runLabel : 'sesión ${s.id}'),
      subtitle: Text(
        '${s.runTitle}'
        '${sum?.received != null ? ' · ${sum!.received} rx' : ''}'
        '${pdr.isNotEmpty ? ' · $pdr' : ''}',
        style: const TextStyle(color: AppColors.textDim),
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: () async {
        // Si el detalle informa un cambio (p. ej. la sesion se borro), se
        // refresca la lista al volver.
        final changed = await Navigator.of(context).push<bool>(
          MaterialPageRoute(
              builder: (_) =>
                  SesionDetalleScreen(id: s.id, runLabel: s.runLabel)),
        );
        if (changed == true) onChanged();
      },
    );
  }

  Color _stateColor(Session s) {
    if (s.isCapturing) return AppColors.green;
    if (s.isFinished) return AppColors.blue;
    if (s.isAborted) return AppColors.red;
    return AppColors.textDim;
  }
}

class _StateBadge extends StatelessWidget {
  final String state;
  final Color color;
  const _StateBadge({required this.state, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 12,
      height: 12,
      margin: const EdgeInsets.only(top: 6),
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

/// Detalle de una sesion + descarga de CSV.
class SesionDetalleScreen extends StatefulWidget {
  final int id;
  final String runLabel;
  const SesionDetalleScreen({super.key, required this.id, required this.runLabel});

  @override
  State<SesionDetalleScreen> createState() => _SesionDetalleScreenState();
}

class _SesionDetalleScreenState extends State<SesionDetalleScreen> {
  late Future<SessionDetail> _future;
  bool _downloading = false;
  bool _deleting = false;

  @override
  void initState() {
    super.initState();
    final api = context.read<AppState>().api;
    _future = api != null
        ? api.getSession(widget.id)
        : Future.error(ApiException(0, 'Sin configuración'));
  }

  Future<void> _download() async {
    final api = context.read<AppState>().api;
    if (api == null) return;
    setState(() => _downloading = true);
    try {
      final csv = await api.downloadCsv(widget.id,
          fallbackName:
              '${widget.runLabel.isNotEmpty ? widget.runLabel : 'sesion_${widget.id}'}.csv');
      final dir = await getApplicationDocumentsDirectory();
      final path = '${dir.path}/${csv.filename}';
      await File(path).writeAsBytes(csv.bytes);
      await Share.shareXFiles([XFile(path)],
          text: 'CSV sesión ${widget.runLabel}');
    } on ApiException catch (e) {
      _snack(e.toString());
    } catch (e) {
      _snack('Error al descargar: $e');
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg)));
  }

  String get _label =>
      widget.runLabel.isNotEmpty ? widget.runLabel : 'sesión ${widget.id}';

  void _openReplay(int tab) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => ReplayScreen(
          id: widget.id, runLabel: widget.runLabel, initialTab: tab),
    ));
  }

  Future<void> _confirmDelete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Descartar sesión'),
        content: Text(
          'Vas a borrar «$_label» y todos sus datos del servidor '
          '(uplinks y resumen).\n\nEsta acción es IRREVERSIBLE.',
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Borrar'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    if (!mounted) return;   // el dialogo es un async gap: revalida el contexto
    final api = context.read<AppState>().api;
    if (api == null) return;
    setState(() => _deleting = true);
    try {
      await api.deleteSession(widget.id);
      // Vuelve a la lista con `true` para que se refresque sin la sesion.
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      _snack(e.toString());
      if (mounted) setState(() => _deleting = false);
    } catch (e) {
      _snack('Error al borrar: $e');
      if (mounted) setState(() => _deleting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.runLabel.isNotEmpty
            ? widget.runLabel
            : 'Sesión ${widget.id}'),
      ),
      body: FutureBuilder<SessionDetail>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return _ErrorView(message: snap.error.toString());
          }
          final d = snap.data!;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _kv('Estado', d.session.stateLabel),
              _kv('Corrida', d.session.runTitle),
              _kv('Perfil', d.session.profile),
              _kv('Objetivo', '${d.session.targetUplinks} uplinks'),
              const Divider(),
              if (d.summary != null) ..._summaryRows(d.summary!),
              if (d.metrics != null) ..._metricsRows(d.metrics!),
              const SizedBox(height: 20),
              // Replay: redibuja el mapa y las graficas de esta sesion guardada.
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.map_outlined),
                      label: const Text('Ver mapa'),
                      onPressed: () => _openReplay(0),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.show_chart),
                      label: const Text('Ver gráficos'),
                      onPressed: () => _openReplay(1),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                icon: _downloading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: AppColors.night0))
                    : const Icon(Icons.download),
                label: const Text('Descargar CSV'),
                onPressed: _downloading ? null : _download,
              ),
              const SizedBox(height: 24),
              // Borrado: irreversible, con confirmacion. Deshabilitado mientras
              // la sesion captura (el servidor tambien lo rechaza con 409).
              OutlinedButton.icon(
                icon: _deleting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: AppColors.red))
                    : const Icon(Icons.delete_outline, color: AppColors.red),
                label: const Text('Descartar sesión',
                    style: TextStyle(color: AppColors.red)),
                style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: AppColors.red)),
                onPressed: (_deleting || d.session.isCapturing)
                    ? null
                    : _confirmDelete,
              ),
              if (d.session.isCapturing)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text(
                    'No se puede borrar una sesión en captura. Abórtala primero.',
                    style: TextStyle(color: AppColors.textDim, fontSize: 12),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  List<Widget> _summaryRows(SessionSummary s) => [
        if (s.received != null) _kv('Recibidos', '${s.received}'),
        if (s.pdrEst != null)
          _kv('PDR (est.)', '${(s.pdrEst! * 100).toStringAsFixed(1)}%'),
        if (s.rssiMean != null)
          _kv('RSSI medio', '${s.rssiMean!.toStringAsFixed(1)} dBm'),
        if (s.snrMean != null)
          _kv('SNR medio', '${s.snrMean!.toStringAsFixed(1)} dB'),
        if (s.distGwKmMax != null)
          _kv('Dist. GW máx', '${s.distGwKmMax!.toStringAsFixed(1)} km'),
        if (s.durationS != null)
          _kv('Duración', _fmtDuration(s.durationS!)),
        if (s.vuelo != null) ..._vueloRows(s.vuelo!),
        const Divider(),
      ];

  /// Rafagas de VUELO: completas (3/3), parciales (1–2) y perdidas (0).
  List<Widget> _vueloRows(MetricsVuelo v) => [
        _kv('Ráfagas completas',
            '${v.completas ?? '--'}${v.rafagasObjetivo != null ? ' / ${v.rafagasObjetivo}' : ''}'),
        _kv('Ráfagas parciales', '${v.parciales ?? '--'}'),
        _kv('Ráfagas perdidas', '${v.perdidas ?? '--'}'),
        _kv('P1 / P2 / P3',
            '${v.p1 ?? '--'} / ${v.p2 ?? '--'} / ${v.p3 ?? '--'}'),
      ];

  List<Widget> _metricsRows(Metrics m) => [
        if (m.lastFcnt != null) _kv('Último fCnt', '${m.lastFcnt}'),
        _kv('Huecos (gaps)', '${m.gaps}'),
        if (m.batteryV != null)
          _kv('Batería', '${(m.batteryV! * 1000).round()} mV'
              '${m.batteryPct != null ? ' · ${m.batteryPct}%' : ' · --'}'),
      ];

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(k, style: const TextStyle(color: AppColors.textDim)),
            Flexible(
              child: Text(v,
                  textAlign: TextAlign.right,
                  style: const TextStyle(
                      color: AppColors.text, fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      );

  String _fmtDuration(double s) {
    final total = s.round();
    final m = total ~/ 60;
    final sec = total % 60;
    return '${m}m ${sec}s';
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final Future<void> Function()? onRetry;
  const _ErrorView({required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
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
            if (onRetry != null) ...[
              const SizedBox(height: 12),
              OutlinedButton(
                  onPressed: () => onRetry!(), child: const Text('Reintentar')),
            ],
          ],
        ),
      ),
    );
  }
}
