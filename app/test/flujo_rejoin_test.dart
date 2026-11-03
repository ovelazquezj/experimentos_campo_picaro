// Tests de la recuperación del gate de clase (D-62): la máquina de estados
// que ordena el re-join por BLE y espera SIN_ENLACE → CONFIG.
//
// Se prueba sin BLE real: FlujoRejoin recibe la orden y el stream de estados
// por inyección, que es justo para lo que se separó de AppState.

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:picaro_campo/ble/ble_client.dart';
import 'package:picaro_campo/ble/flujo_rejoin.dart';

/// Estado de 6 B como el que notifica la sonda, con lo que aquí importa.
BleSondaEstado _estado(int estado) =>
    BleSondaEstado.desdeBytes([0x01, 0x00, estado, 0x00, 0x00, 0x00])!;

void main() {
  group('FlujoRejoin', () {
    late StreamController<BleSondaEstado> estados;

    setUp(() => estados = StreamController<BleSondaEstado>.broadcast());
    tearDown(() => estados.close());

    test('SIN_ENLACE seguido de CONFIG es un re-join completo', () async {
      final flujo = FlujoRejoin(
        enviarRejoin: () async =>
            const BleRespuesta(BleCmdResultado.ok, 'aceptado'),
        cambiosEstado: estados.stream,
      );

      final futuro = flujo.ejecutar();
      await Future<void>.delayed(Duration.zero);
      estados.add(_estado(BleEstadoSonda.sinEnlace));
      estados.add(_estado(BleEstadoSonda.config));

      final fin = await futuro;
      expect(fin.ok, isTrue);
      expect(fin.desenlace, RejoinDesenlace.ok);
    });

    test('un CONFIG sin SIN_ENLACE previo no cuenta: es el estado viejo',
        () async {
      final flujo = FlujoRejoin(
        enviarRejoin: () async =>
            const BleRespuesta(BleCmdResultado.ok, 'aceptado'),
        cambiosEstado: estados.stream,
        timeout: const Duration(milliseconds: 120),
      );

      final futuro = flujo.ejecutar();
      await Future<void>.delayed(Duration.zero);
      estados.add(_estado(BleEstadoSonda.config)); // el de antes

      final fin = await futuro;
      expect(fin.desenlace, RejoinDesenlace.timeout,
          reason: 'aceptar ese CONFIG daría por hecho un JOIN que no ocurrió');
    });

    test('si la sonda ya estaba en SIN_ENLACE, basta con el CONFIG final',
        () async {
      // Partiendo del menú sin enlace, la sonda puede no volver a notificar
      // 0x06 al aceptar el re-join: el ACK de la escritura ya lo trae.
      final flujo = FlujoRejoin(
        enviarRejoin: () async => BleRespuesta(
          BleCmdResultado.ok,
          'aceptado',
          estado: _estado(BleEstadoSonda.sinEnlace),
        ),
        cambiosEstado: estados.stream,
        timeout: const Duration(milliseconds: 400),
      );

      final futuro = flujo.ejecutar();
      await Future<void>.delayed(const Duration(milliseconds: 20));
      estados.add(_estado(BleEstadoSonda.config));

      expect((await futuro).ok, isTrue);
    });

    test('ATT 131 se traduce a «firmware sin re-join», no a fallo genérico',
        () async {
      final flujo = FlujoRejoin(
        enviarRejoin: () async => const BleRespuesta(
            BleCmdResultado.rechazoParametro, 'no conoce la orden',
            codigoAtt: 131),
        cambiosEstado: estados.stream,
      );

      final fin = await flujo.ejecutar();
      expect(fin.desenlace, RejoinDesenlace.firmwareSinRejoin,
          reason: 'es lo que permite ofrecer el respaldo de apagar/encender');
    });

    test('desde FINALIZADA vuelve al menú y reintenta: encadenar corridas '
        'cambiando de clase no cae en el respaldo manual', () async {
      var intentos = 0;
      var volvioAlMenu = false;

      final flujo = FlujoRejoin(
        enviarRejoin: () async {
          intentos++;
          // El primero se rechaza por estado; tras el abortar, se acepta.
          return intentos == 1
              ? BleRespuesta(BleCmdResultado.rechazoEstado, 'no aplicable',
                  codigoAtt: 132,
                  estado: _estado(BleEstadoSonda.finalizada))
              : const BleRespuesta(BleCmdResultado.ok, 'aceptado');
        },
        volverAlMenu: () async {
          volvioAlMenu = true;
          return const BleRespuesta(BleCmdResultado.ok, 'en configuración');
        },
        cambiosEstado: estados.stream,
        timeout: const Duration(milliseconds: 400),
      );

      final futuro = flujo.ejecutar();
      await Future<void>.delayed(const Duration(milliseconds: 20));
      estados.add(_estado(BleEstadoSonda.sinEnlace));
      estados.add(_estado(BleEstadoSonda.config));

      expect((await futuro).ok, isTrue);
      expect(volvioAlMenu, isTrue);
      expect(intentos, 2);
    });

    test('CORRIENDO no se lleva al menú: abortar tiraría la corrida', () async {
      var volvioAlMenu = false;

      final flujo = FlujoRejoin(
        enviarRejoin: () async => BleRespuesta(
            BleCmdResultado.rechazoEstado, 'no aplicable',
            codigoAtt: 132, estado: _estado(BleEstadoSonda.corriendo)),
        volverAlMenu: () async {
          volvioAlMenu = true;
          return const BleRespuesta(BleCmdResultado.ok, 'ok');
        },
        cambiosEstado: estados.stream,
        timeout: const Duration(milliseconds: 200),
      );

      final fin = await flujo.ejecutar();
      expect(volvioAlMenu, isFalse,
          reason: 'ningún arreglo automático justifica parar una medida');
      expect(fin.desenlace, RejoinDesenlace.fallo);
    });

    test('el operador puede cancelar la espera', () async {
      final flujo = FlujoRejoin(
        enviarRejoin: () async =>
            const BleRespuesta(BleCmdResultado.ok, 'aceptado'),
        cambiosEstado: estados.stream,
        timeout: const Duration(seconds: 30),
      );

      final futuro = flujo.ejecutar();
      await Future<void>.delayed(Duration.zero);
      estados.add(_estado(BleEstadoSonda.sinEnlace));
      await Future<void>.delayed(const Duration(milliseconds: 20));
      flujo.cancelar();

      expect((await futuro).desenlace, RejoinDesenlace.cancelado);
    });

    test('la espera vence si el JOIN nunca completa', () async {
      final flujo = FlujoRejoin(
        enviarRejoin: () async =>
            const BleRespuesta(BleCmdResultado.ok, 'aceptado'),
        cambiosEstado: estados.stream,
        timeout: const Duration(milliseconds: 100),
      );

      final futuro = flujo.ejecutar();
      await Future<void>.delayed(Duration.zero);
      estados.add(_estado(BleEstadoSonda.sinEnlace));

      expect((await futuro).desenlace, RejoinDesenlace.timeout);
    });

    test('avisa del progreso al ver el SIN_ENLACE', () async {
      final avisos = <String>[];
      final flujo = FlujoRejoin(
        enviarRejoin: () async =>
            const BleRespuesta(BleCmdResultado.ok, 'aceptado'),
        cambiosEstado: estados.stream,
        timeout: const Duration(milliseconds: 200),
        alProgresar: avisos.add,
      );

      final futuro = flujo.ejecutar();
      await Future<void>.delayed(Duration.zero);
      estados.add(_estado(BleEstadoSonda.sinEnlace));
      estados.add(_estado(BleEstadoSonda.config));
      await futuro;

      expect(avisos, hasLength(1));
      expect(avisos.single, contains('JOIN'));
    });
  });
}
