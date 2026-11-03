import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app_state.dart';
import 'ble/ble_client.dart';
import 'screens/config_screen.dart';
import 'screens/home.dart';
import 'theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    // Dos proveedores independientes a proposito (v2):
    //   AppState  -> el servidor (REST + WebSocket), que es la v1 sin cambios
    //   BleClient -> el enlace con la sonda, que puede caerse sin arrastrar al
    //                otro (RNF-2: si el BLE se cae, la corrida sigue)
    // panel.dart los une en la seleccion fundida; no se fusionan aqui.
    MultiProvider(
      providers: [
        ChangeNotifierProvider<AppState>(create: (_) => AppState()..init()),
        ChangeNotifierProvider<BleClient>(create: (_) => BleClient()),
      ],
      child: const PicaroApp(),
    ),
  );
}

class PicaroApp extends StatelessWidget {
  const PicaroApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PiCARO Campo',
      debugShowCheckedModeBanner: false,
      theme: buildDarkTheme(),
      home: const _Root(),
    );
  }
}

/// Enruta segun el estado: sin config valida -> pantalla de configuracion.
class _Root extends StatelessWidget {
  const _Root();

  @override
  Widget build(BuildContext context) {
    final st = context.watch<AppState>();
    if (!st.initialized) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!st.config.isValid) {
      return const ConfigScreen(firstRun: true);
    }
    return const HomeScreen();
  }
}
