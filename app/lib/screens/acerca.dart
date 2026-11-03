import 'package:flutter/material.dart';

import '../config.dart';
import '../theme.dart';

/// ⑤ Acerca de (§10).
class AcercaScreen extends StatelessWidget {
  const AcercaScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Acerca de')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const SizedBox(height: 12),
          Center(
            child: Image.asset(
              'assets/icon/icon.png',
              width: 120,
              height: 120,
              // Si por lo que sea el asset no cargara, no romper la pantalla.
              errorBuilder: (_, __, ___) =>
                  const Icon(Icons.hub, size: 120, color: AppColors.cyan),
            ),
          ),
          const SizedBox(height: 20),
          const Center(
            child: Text(
              'PiCARO — App de campo',
              style: TextStyle(
                  color: AppColors.text,
                  fontSize: 22,
                  fontWeight: FontWeight.bold),
            ),
          ),
          const SizedBox(height: 6),
          const Center(
            child: Text('Versión $kAppVersion',
                style: TextStyle(color: AppColors.textDim)),
          ),
          const SizedBox(height: 28),
          const _Line('© 2026 Omar Velázquez'),
          const _Line('Licencia MIT'),
          const _Line('ovelazquezj@gmail.com'),
          const SizedBox(height: 24),
          const Center(
            child: Text(
              'Herramienta open source para las pruebas de campo del proyecto '
              'radiosonda PiCARO (LoRaWAN Clase A vs C).',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textDim),
            ),
          ),
        ],
      ),
    );
  }
}

class _Line extends StatelessWidget {
  final String text;
  const _Line(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Center(
        child: Text(text,
            style: const TextStyle(color: AppColors.text, fontSize: 15)),
      ),
    );
  }
}
