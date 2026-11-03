import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../app_state.dart';
import '../ble/ble_client.dart';
import '../theme.dart';
import 'acerca.dart';
import 'ayuda.dart';
import 'config_screen.dart';
import 'dispositivo.dart';
import 'graficos.dart';
import 'mapa.dart';
import 'panel.dart';
import 'sesiones.dart';

/// Contenedor con BottomNavigationBar (Panel / Mapa / Graficos), menu [≡] a la
/// izquierda (Sesiones, Acerca de, Configuracion) y boton [?] de Ayuda (§10).
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;

  static const _titles = ['Panel', 'Mapa', 'Gráficos'];

  @override
  Widget build(BuildContext context) {
    final st = context.watch<AppState>();
    final ble = context.watch<BleClient>();

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Text(_titles[_index]),
            const Spacer(),
            // Dos indicadores, no uno: el servidor y la sonda se caen por
            // separado y hay que poder distinguirlo de un vistazo. Sin BLE el
            // selector esta bloqueado (RF-7), asi que este punto explica por
            // que; se toca para ir a la pantalla de dispositivo.
            _BleDot(listo: ble.listo, conectado: ble.conectado),
            const SizedBox(width: 10),
            _ConnDot(connected: st.wsConnected),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Ayuda',
            icon: const Icon(Icons.help_outline),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const AyudaScreen()),
            ),
          ),
        ],
      ),
      drawer: const _MenuDrawer(),
      body: IndexedStack(
        index: _index,
        children: const [
          PanelScreen(),
          MapaScreen(),
          GraficosScreen(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.dashboard_outlined), label: 'Panel'),
          BottomNavigationBarItem(
              icon: Icon(Icons.map_outlined), label: 'Mapa'),
          BottomNavigationBarItem(
              icon: Icon(Icons.show_chart), label: 'Gráficos'),
        ],
      ),
    );
  }
}

/// Punto indicador del enlace BLE con la sonda, en la AppBar. Se toca para
/// abrir la pantalla de dispositivo, que es donde se empareja y se reconecta.
class _BleDot extends StatelessWidget {
  final bool listo;
  final bool conectado;
  const _BleDot({required this.listo, required this.conectado});

  @override
  Widget build(BuildContext context) {
    // Tres estados distinguibles: enlace seguro y usable, conectado pero aun
    // no seguro (emparejando), y sin sonda. El intermedio importa porque es
    // justo cuando el selector sigue bloqueado y parece un fallo.
    final Color color = listo
        ? AppColors.green
        : (conectado ? AppColors.gold : AppColors.textDim);
    final String texto = listo ? 'sonda' : (conectado ? '...' : 'sin sonda');

    return InkWell(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const DispositivoScreen()),
      ),
      child: Row(
        children: [
          Icon(listo ? Icons.bluetooth_connected : Icons.bluetooth_disabled,
              size: 16, color: color),
          const SizedBox(width: 4),
          Text(texto,
              style: const TextStyle(fontSize: 12, color: AppColors.textDim)),
        ],
      ),
    );
  }
}

/// Punto indicador del estado del WebSocket en la AppBar.
class _ConnDot extends StatelessWidget {
  final bool connected;
  const _ConnDot({required this.connected});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(
          connected ? Icons.wifi : Icons.wifi_off,
          size: 16,
          color: connected ? AppColors.green : AppColors.textDim,
        ),
        const SizedBox(width: 4),
        Text(
          connected ? 'live' : 'off',
          style: const TextStyle(fontSize: 12, color: AppColors.textDim),
        ),
      ],
    );
  }
}

class _MenuDrawer extends StatelessWidget {
  const _MenuDrawer();

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: SafeArea(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            const DrawerHeader(
              decoration: BoxDecoration(color: AppColors.night0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text('PiCARO',
                      style: TextStyle(
                          color: AppColors.gold,
                          fontSize: 26,
                          fontWeight: FontWeight.bold)),
                  Text('App de campo',
                      style: TextStyle(color: AppColors.textDim)),
                ],
              ),
            ),
            ListTile(
              leading: const Icon(Icons.bluetooth),
              title: const Text('Dispositivo (BLE)'),
              subtitle: const Text('Emparejar y conectar la sonda'),
              onTap: () => _go(context, const DispositivoScreen()),
            ),
            ListTile(
              leading: const Icon(Icons.list_alt),
              title: const Text('Sesiones'),
              onTap: () => _go(context, const SesionesScreen()),
            ),
            ListTile(
              leading: const Icon(Icons.info_outline),
              title: const Text('Acerca de'),
              onTap: () => _go(context, const AcercaScreen()),
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.settings_outlined),
              title: const Text('Configuración'),
              onTap: () => _go(context, const ConfigScreen()),
            ),
          ],
        ),
      ),
    );
  }

  void _go(BuildContext context, Widget page) {
    Navigator.of(context).pop(); // cierra el drawer
    Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => page));
  }
}
