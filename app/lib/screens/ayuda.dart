import 'package:flutter/material.dart';

import '../theme.dart';

/// ⑥ Ayuda: cómo se opera la campaña desde la v2, derivado del manual de campo.
/// Es la chuleta que se lee en el cerro, así que va en pasos y sin jerga.
class AyudaScreen extends StatelessWidget {
  const AyudaScreen({super.key});

  static const _steps = <_Step>[
    _Step(
      '1 · Emparejar (solo la primera vez)',
      'Menú ≡ → Dispositivo (BLE) → Buscar y conectar. En la sonda, pulsación '
          'LARGA desde el menú para abrir la ventana de emparejamiento.\n\n'
          'Al conectar, el móvil te pedirá un código y la sonda lo mostrará en '
          'su pantalla: CODIGO 123456. Son seis dígitos, ceros incluidos.\n\n'
          'Antes de que el móvil lo pida, la sonda NO enseña ningún número. Eso '
          'es normal, no es un fallo.',
    ),
    _Step(
      '2 · Conectar',
      'Una vez emparejada, la sonda se reconecta sola y sin pedir el código. '
          'El indicador de arriba se pone verde y pone «sonda»: mientras esté '
          'gris, el selector de corrida está bloqueado.',
    ),
    _Step(
      '3 · Elegir la corrida y arrancar',
      'Elige el escenario y la clase y pulsa el botón verde. Esa sola acción '
          'hace las tres cosas: ajusta el perfil del servidor, abre la sesión '
          'de captura y pone la sonda en esa corrida.\n\n'
          'Ya no hay que elegir nada en la sonda: por eso el desajuste entre '
          'app y sonda no puede ocurrir.',
    ),
    _Step(
      '4 · Vigilar los avisos',
      'El bloque SONDA confirma en verde que la corrida está corriendo de '
          'verdad en el equipo, no solo que se envió la orden.\n\n'
          'Si aparece una banda roja, léela: o la sonda corre algo distinto de '
          'la sesión, o la sonda se paró y la sesión sigue abierta sin capturar '
          'nada. Las dos se arreglan antes de seguir tomando datos.',
    ),
    _Step(
      '5 · Si te quedas sin móvil',
      'La sonda se opera entera con su botón, igual que siempre: corto cambia '
          'de corrida, doble arranca, larga aborta. La corrida en marcha NO '
          'depende del Bluetooth: si el móvil se cae o se apaga, sigue '
          'transmitiendo.\n\n'
          'Abortar desde la app funciona SIEMPRE, con Bluetooth o sin él, para '
          'que nunca te quedes con una sesión abierta que no puedas cerrar.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ayuda')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Operar una corrida',
            style: TextStyle(
                color: AppColors.gold,
                fontSize: 18,
                fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          const Text(
            'La corrida se elige en un solo sitio: aquí. La app la fija a la '
            'vez en el servidor y en la sonda, por Bluetooth. El botón de la '
            'sonda sigue funcionando como respaldo completo.',
            style: TextStyle(color: AppColors.textDim),
          ),
          const SizedBox(height: 16),
          ..._steps.map((s) => _StepCard(step: s)),
          const SizedBox(height: 16),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Regla de oro',
                      style: TextStyle(
                          color: AppColors.gold,
                          fontWeight: FontWeight.bold)),
                  SizedBox(height: 6),
                  Text(
                    'No mezcles los dos caminos en la misma corrida. O la '
                    'arrancas desde la app, o la arrancas con el botón de la '
                    'sonda.\n\n'
                    'Si arrancas con el botón, el servidor no se entera y no '
                    'habrá sesión de captura: tendrás los datos de la microSD '
                    'pero no los del servidor, y sin las dos mitades no se '
                    'puede calcular el PDR.',
                    style: TextStyle(color: AppColors.text),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Step {
  final String title;
  final String body;
  const _Step(this.title, this.body);
}

class _StepCard extends StatelessWidget {
  final _Step step;
  const _StepCard({required this.step});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(step.title,
                style: const TextStyle(
                    color: AppColors.cyan,
                    fontSize: 16,
                    fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            Text(step.body, style: const TextStyle(color: AppColors.text)),
          ],
        ),
      ),
    );
  }
}
