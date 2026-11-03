import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';

import '../app_state.dart';
import '../theme.dart';
import '../utils/geo.dart';
import '../widgets/points_map.dart';

/// ② Mapa: puntos de la sesion ACTIVA sobre OpenStreetMap (sin API key). Es una
/// capa fina sobre [MapPanel], que es el que de verdad dibuja y se reutiliza en
/// el replay de sesiones guardadas.
class MapaScreen extends StatelessWidget {
  const MapaScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final st = context.watch<AppState>();
    // VUELO: solo los P1 con fix aportan punto (ver puntosConFix).
    final points = puntosConFix(st.uplinks);
    final gw = st.config.hasGateway
        ? LatLng(st.config.gwLat!, st.config.gwLon!)
        : null;
    return MapPanel(points: points, gateway: gw);
  }
}

/// Panel de mapa reutilizable: recibe los puntos y (opcional) el gateway, y no
/// depende de AppState. Lo usan tanto la pantalla en vivo como el replay. Si no
/// hay tiles (sin red), el conmutador Offline dibuja con CustomPainter y nunca
/// rompe (§10).
class MapPanel extends StatefulWidget {
  final List<LatLng> points;
  final LatLng? gateway;
  const MapPanel({super.key, required this.points, this.gateway});

  @override
  State<MapPanel> createState() => _MapPanelState();
}

class _MapPanelState extends State<MapPanel> {
  // 0 = OpenStreetMap (tiles), 1 = respaldo offline (CustomPainter).
  int _mode = 0;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(8),
          child: Row(
            children: [
              ToggleButtons(
                isSelected: [_mode == 0, _mode == 1],
                onPressed: (i) => setState(() => _mode = i),
                borderRadius: BorderRadius.circular(8),
                children: const [
                  Padding(
                      padding: EdgeInsets.symmetric(horizontal: 12),
                      child: Text('OSM')),
                  Padding(
                      padding: EdgeInsets.symmetric(horizontal: 12),
                      child: Text('Offline')),
                ],
              ),
              const Spacer(),
              Text('${widget.points.length} pts',
                  style: const TextStyle(color: AppColors.textDim)),
            ],
          ),
        ),
        Expanded(
          child: _mode == 0
              ? _OsmMap(points: widget.points, gateway: widget.gateway)
              : OfflinePointsMap(points: widget.points, gateway: widget.gateway),
        ),
      ],
    );
  }
}

class _OsmMap extends StatelessWidget {
  final List<LatLng> points;
  final LatLng? gateway;
  const _OsmMap({required this.points, this.gateway});

  @override
  Widget build(BuildContext context) {
    // Centro: ultimo punto, o gateway, o un fallback generico.
    final center = points.isNotEmpty
        ? points.last
        : (gateway ?? const LatLng(19.4326, -99.1332));

    final markers = <Marker>[
      if (gateway != null)
        Marker(
          point: gateway!,
          width: 44,
          height: 44,
          child: const Icon(Icons.cell_tower, color: AppColors.red, size: 32),
        ),
      if (points.isNotEmpty)
        Marker(
          point: points.last,
          width: 28,
          height: 28,
          child: const Icon(Icons.my_location, color: AppColors.gold, size: 24),
        ),
    ];

    return FlutterMap(
      options: MapOptions(
        initialCenter: center,
        initialZoom: points.isEmpty && gateway == null ? 4 : 13,
        maxZoom: 18,
        minZoom: 2,
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'org.pi_caro.campo',
        ),
        if (points.length >= 2)
          PolylineLayer(
            polylines: [
              Polyline(
                points: points,
                color: AppColors.cyan,
                strokeWidth: 3,
              ),
            ],
          ),
        MarkerLayer(markers: markers),
      ],
    );
  }
}
