// ============================================================================
//  flujo_rejoin.dart  -  Re-join automático tras el 409 del gate de clase
// ============================================================================
//  Contexto (CONTRATO-CAMPO §15.1, D-60): ChirpStack congela la clase efectiva
//  del device en el JOIN. Si `POST /session/start` la encuentra desajustada
//  responde 409 — pero ese mismo start YA dejó puesto el perfil correcto en el
//  servidor, así que el arreglo es un JOIN nuevo de la sonda. Antes eso era
//  «apaga y enciende la sonda»; ahora la app lo ordena por BLE (op 0x03).
//
//  Esta clase es SOLO la máquina de estados de esa recuperación:
//
//      enviar re-join ──> esperar SIN_ENLACE (0x06) ──> esperar CONFIG (0x00)
//
//  con espera acotada (el join en el cerro puede tardar) y **cancelable** por
//  el operador. No sabe nada de BLE real ni del microservicio: recibe la orden
//  y el stream de estados por inyección, que es lo que la hace testeable sin
//  una sonda delante. Quién reintenta el `start` después es AppState.
// ============================================================================

import 'dart:async';

import 'ble_client.dart';

/// Cómo terminó el intento de re-join.
enum RejoinDesenlace {
  /// La sonda volvió a CONFIG tras pasar por SIN_ENLACE: join nuevo hecho.
  ok,

  /// No llegó CONFIG dentro del plazo. La sonda puede seguir uniéndose.
  timeout,

  /// El operador canceló la espera. OJO: la orden ya se envió; la sonda puede
  /// seguir haciendo el join por su cuenta.
  cancelado,

  /// ATT 131 (0x83) al escribir: firmware anterior al op 0x03. Hay que degradar
  /// al respaldo manual (apagar/encender la sonda).
  firmwareSinRejoin,

  /// La escritura falló por cualquier otra causa (sin enlace, estado que no lo
  /// admite, transporte). El mensaje trae el detalle del cliente BLE.
  fallo,
}

/// Resultado de [FlujoRejoin.ejecutar].
class RejoinFin {
  final RejoinDesenlace desenlace;

  /// Detalle en español. Solo es significativo cuando NO es [RejoinDesenlace.ok];
  /// la redacción final para el operador la compone quien llama, que conoce el
  /// contexto (el `detail` del 409, el respaldo manual…).
  final String mensaje;

  const RejoinFin(this.desenlace, [this.mensaje = '']);

  bool get ok => desenlace == RejoinDesenlace.ok;

  @override
  String toString() => 'RejoinFin($desenlace, "$mensaje")';
}

/// Orquesta UN intento de re-join. De un solo uso: se crea, se llama a
/// [ejecutar] una vez y se tira. [cancelar] puede llegar en cualquier momento
/// (incluso antes o después de terminar: es inofensivo).
class FlujoRejoin {
  /// Timeout por defecto de la espera SIN_ENLACE → CONFIG. Generoso a
  /// propósito: en el cerro un join puede tardar más de un minuto (patrón
  /// D-57: espera larga pero acotada y abortable, nunca infinita).
  static const Duration timeoutPorDefecto = Duration(seconds: 120);

  /// Envía `[0x03, 0x00]` por BLE. En producción es `BleClient.rejoin`.
  final Future<BleRespuesta> Function() enviarRejoin;

  /// Cada Estado de 6 B que llega de la sonda. En producción,
  /// `BleClient.cambiosEstado`.
  final Stream<BleSondaEstado> cambiosEstado;

  /// Lleva la sonda al menú cuando quedó en una pantalla de fin. En producción
  /// es `BleClient.abortar`, que significa «vuelve a configuración».
  ///
  /// Hace falta porque el re-join solo se acepta en CONFIG/SIN_ENLACE, y el
  /// caso más común es justo el contrario: terminar una corrida (la sonda se
  /// queda en FINALIZADA), cambiar de clase y arrancar la siguiente. Sin este
  /// paso, el caso central —encadenar corridas alternando A y C— caería en el
  /// respaldo manual, que es lo que D-62 viene a evitar.
  final Future<BleRespuesta> Function()? volverAlMenu;

  final Duration timeout;

  /// Aviso de progreso opcional, para pintar «la sonda está uniéndose…» en
  /// cuanto se ve el SIN_ENLACE. No afecta a la máquina de estados.
  final void Function(String mensaje)? alProgresar;

  FlujoRejoin({
    required this.enviarRejoin,
    required this.cambiosEstado,
    this.volverAlMenu,
    this.timeout = timeoutPorDefecto,
    this.alProgresar,
  });

  final Completer<RejoinFin> _fin = Completer<RejoinFin>();
  bool _ejecutado = false;

  /// Cancela la espera (no el join: la orden ya viajó y la sonda no se
  /// interrumpe). Seguro llamarlo en cualquier momento.
  void cancelar() => _terminar(const RejoinFin(RejoinDesenlace.cancelado,
      'Espera del re-join cancelada por el operador.'));

  void _terminar(RejoinFin fin) {
    if (!_fin.isCompleted) _fin.complete(fin);
  }

  /// Ejecuta el intento completo: escribir el 0x03 y esperar SIN_ENLACE →
  /// CONFIG. No lanza: el camino de error es el [RejoinFin], igual que en el
  /// resto del flujo fundido.
  Future<RejoinFin> ejecutar() async {
    assert(!_ejecutado, 'FlujoRejoin es de un solo uso');
    _ejecutado = true;

    // Cancelado antes de empezar: no se envía nada.
    if (_fin.isCompleted) return _fin.future;

    // Se acepta CONFIG solo DESPUÉS de haber visto SIN_ENLACE: una
    // notificación de CONFIG anterior al re-join (la sonda parte de menú, que
    // ES CONFIG cuando hay enlace) no es el join nuevo, es el estado viejo.
    var vioSinEnlace = false;

    // Suscribirse ANTES de escribir, para no perder el SIN_ENLACE inmediato
    // (mismo criterio que el paso 8 de §10.3: primero notify, luego leer).
    final sub = cambiosEstado.listen((e) {
      if (e.estado == BleEstadoSonda.sinEnlace) {
        if (!vioSinEnlace) {
          vioSinEnlace = true;
          alProgresar?.call('La sonda está haciendo el JOIN nuevo; puede '
              'tardar un par de minutos.');
        }
      } else if (vioSinEnlace && e.estado == BleEstadoSonda.config) {
        _terminar(const RejoinFin(RejoinDesenlace.ok));
      }
    });
    final temporizador = Timer(timeout, () {
      _terminar(RejoinFin(
          RejoinDesenlace.timeout,
          'La sonda no completó el re-join en ${timeout.inSeconds} s.'));
    });

    try {
      var r = await enviarRejoin();

      // Rechazado por estado (ATT 132) estando en una pantalla de fin: la
      // sonda acaba de terminar o abortar una corrida y el re-join solo se
      // acepta en menú. «Abortar» significa volver a configuración, así que
      // sirve para llevarla allí, y se reintenta UNA vez.
      //
      // Solo desde FINALIZADA/ABORTADA: en CORRIENDO o ESPERANDO_ENLACE un
      // abortar pararía una medida en marcha o agendada, y ningún arreglo
      // automático justifica tirar una corrida.
      if (r.resultado == BleCmdResultado.rechazoEstado && volverAlMenu != null) {
        final est = r.estado?.estado;
        if (est == BleEstadoSonda.finalizada || est == BleEstadoSonda.abortada) {
          alProgresar?.call('Llevando la sonda al menú para rehacer el JOIN…');
          final vuelta = await volverAlMenu!();
          if (vuelta.aceptado) r = await enviarRejoin();
        }
      }

      if (r.resultado == BleCmdResultado.rechazoParametro) {
        // ATT 131 con op 0x03 = firmware viejo, no un bug de la app.
        _terminar(RejoinFin(RejoinDesenlace.firmwareSinRejoin, r.mensaje));
      } else if (!r.aceptado) {
        _terminar(RejoinFin(RejoinDesenlace.fallo, r.mensaje));
      } else if (r.estado?.estado == BleEstadoSonda.sinEnlace) {
        // La sonda partía de SIN_ENLACE (menú sin enlace): puede no volver a
        // notificar 0x06 al aceptar el re-join. Cuenta como visto, o el CONFIG
        // final se descartaría como «estado viejo» y la espera vencería.
        vioSinEnlace = true;
      }
      return await _fin.future;
    } finally {
      temporizador.cancel();
      await sub.cancel();
    }
  }
}
