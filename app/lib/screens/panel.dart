import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../app_state.dart';
import '../ble/ble_client.dart';
import '../models/models.dart';
import '../runs.dart';
import '../theme.dart';
import '../widgets/big_button.dart';
import '../widgets/distancia_telefono.dart';
import '../widgets/oled_panel.dart';
import '../widgets/run_selector.dart';
import '../widgets/vuelo_panel.dart';
import '../widgets/warning_banner.dart';

/// ① Panel: selector de corrida, boton grande de accion, datos tipo OLED en vivo,
/// banda de aviso por desajuste de fPort y boton de ping (§10 CONTRATO-CAMPO).
///
/// En la v2 este es el sitio donde vive la **selección fundida** (RF-3): elegir
/// una corrida y pulsar Arrancar fija el perfil A/C en ChirpStack, abre la
/// sesión de captura y arranca la sonda por BLE, en ese orden (§10.5 del
/// CONTRATO-BLE). El selector y Arrancar están cerrados si la sonda no está
/// conectada con enlace seguro (RF-7); **Abortar nunca se cierra** (decisión G).
class PanelScreen extends StatefulWidget {
  const PanelScreen({super.key});

  @override
  State<PanelScreen> createState() => _PanelScreenState();
}

class _PanelScreenState extends State<PanelScreen> {
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    // El `BleClient` lo registra `main.dart` con `provider` y lo maneja la
    // pantalla de dispositivo. Aquí se engancha a `AppState`, que es quien
    // funde las dos mitades: sin este enganche `AppState` no vería el enlace y
    // el gate de RF-7 quedaría cerrado para siempre. Va en un post-frame para
    // no llamar a `notifyListeners()` en mitad de una construcción.
    WidgetsBinding.instance.addPostFrameCallback((_) => _engancharBle());
  }

  /// Idempotente: `adjuntarBle` sale sola si ya está enganchado ese cliente.
  void _engancharBle() {
    if (!mounted) return;
    try {
      context.read<AppState>().adjuntarBle(context.read<BleClient>());
    } catch (_) {
      // `BleClient` todavía no está en el árbol de providers. No es fatal: el
      // gate queda cerrado y `bleMotivoBloqueo` explica por qué.
    }
  }

  /// Ejecuta una acción fundida. No hay `catch`: ni `arrancarFundido` ni
  /// `abortarFundido` lanzan — devuelven qué quedó hecho y qué no, que es lo
  /// que hace falta saber en campo.
  Future<void> _fundido(Future<ResultadoFusion> Function() accion) async {
    setState(() => _busy = true);
    ResultadoFusion res;
    try {
      res = await accion();
    } catch (e) {
      // Red de seguridad: un fallo no previsto no debe dejar el botón girando.
      res = ResultadoFusion(NivelFusion.error, 'Error inesperado: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
    _avisar(res);
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
    } catch (e) {
      // `ApiException.toString()` ya dice «HTTP 409: …» o «Sin conexión: …».
      _snack('$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _avisar(ResultadoFusion res) {
    if (!mounted) return;
    final Color fondo;
    final Duration dura;
    switch (res.nivel) {
      case NivelFusion.ok:
        fondo = AppColors.green;
        dura = const Duration(seconds: 4);
        break;
      case NivelFusion.aviso:
        fondo = AppColors.gold;
        dura = const Duration(seconds: 9);
        break;
      case NivelFusion.error:
        fondo = AppColors.red;
        dura = const Duration(seconds: 12);
        break;
    }
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
        content: Text(res.mensaje,
            style: const TextStyle(
                color: Colors.white, fontWeight: FontWeight.w600)),
        backgroundColor: fondo,
        duration: dura,
      ));
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<bool> _confirm(String title, String body, String ok) async {
    final res = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true), child: Text(ok)),
        ],
      ),
    );
    return res ?? false;
  }

  @override
  Widget build(BuildContext context) {
    final st = context.watch<AppState>();
    final s = st.currentSession;
    final capturing = s != null && s.isCapturing;
    final finished = s != null && s.isFinished;
    final desajusteBle = st.avisoDesajusteBle;
    final sondaParada = st.avisoSondaParada;
    // VUELO: la lectura se reconstruye con el ultimo valor conocido de cada
    // magnitud (cada uplink trae solo un trozo). Corridas clasicas: null, y el
    // panel se comporta exactamente como antes.
    final esVuelo = s != null && s.esVuelo;
    final lectura = esVuelo
        ? LecturaVuelo.desde(st.uplinks.where((u) => u.esVuelo))
        : null;

    return Column(
      children: [
        // --- Avisos, del más urgente al más informativo --------------------
        if (desajusteBle != null)
          // No es descartable a propósito: es el desajuste que la v2 existe
          // para evitar, y mientras dure hay un dato contaminándose.
          _Aviso(message: desajusteBle),
        if (sondaParada != null)
          // Tampoco descartable, y por el mismo motivo: la sesión está abierta
          // grabando nada. El arreglo es cerrarla, así que se ofrece aquí.
          // No se cierra sola: cerrar una sesión no se deshace (ver el getter).
          _Aviso(
            message: sondaParada,
            icon: Icons.stop_circle_outlined,
            accionTexto: 'Cerrar sesión',
            onAccion: _busy
                ? null
                : () async {
                    final ok = await _confirm(
                        'Cerrar la sesión',
                        'La sonda ya no transmite. Se cerrará la sesión de '
                            'captura en el servidor. No se puede deshacer.',
                        'Cerrar');
                    if (ok) {
                      await _fundido(
                          () => context.read<AppState>().abortarFundido());
                    }
                  },
          ),
        // Re-join en curso (D-62): la sonda está rehaciendo el JOIN para que
        // ChirpStack congele la clase correcta. Va primero porque describe algo
        // que está pasando AHORA y que retiene el arranque; y lleva «Cancelar»
        // porque la espera puede ser larga y nunca debe quedar sin salida.
        if (st.progresoRejoin != null)
          _Aviso(
            message: st.progresoRejoin!,
            color: AppColors.night1,
            icon: Icons.autorenew,
            accionTexto: 'Cancelar',
            onAccion: () => context.read<AppState>().cancelarRejoin(),
          ),
        if (st.warning != null)
          WarningBanner(
            message:
                'Desajuste de fPort: recibido ${st.warning!.got}, esperado ${st.warning!.expected}',
            onDismiss: () => context.read<AppState>().dismissWarning(),
          ),
        if (st.avisoFusion != null)
          _Aviso(
            message: st.avisoFusion!,
            onDismiss: () => context.read<AppState>().descartarAvisoFusion(),
          ),
        if (st.avisoBle != null)
          _Aviso(
            message: st.avisoBle!,
            color: AppColors.night1,
            icon: Icons.bluetooth_disabled,
            onDismiss: () => context.read<AppState>().descartarAvisoBle(),
          ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // --- Selector de corrida ---------------------------------------
              // Cerrado si se está capturando (v1) o si la sonda no está lista
              // por BLE (RF-7): las dos mitades se fijan juntas o ninguna.
              const _SectionTitle('Corrida'),
              RunSelector(
                scenario: st.selectedScenario,
                cls: st.selectedClass,
                enabled: st.bleListo && !capturing && !_busy,
                sonda: st.sonda,
                onSelect: (scenario, cls) =>
                    context.read<AppState>().selectRun(scenario, cls),
              ),
              _motivoSelector(st, capturing),
              const SizedBox(height: 20),

              // --- Boton grande de accion -----------------------------------
              Center(child: _buildBigButton(st, capturing, finished)),
              const SizedBox(height: 8),
              Center(child: _profileHint(st, capturing)),
              if (capturing) ...[
                const SizedBox(height: 4),
                Center(
                  child: TextButton.icon(
                    icon: const Icon(Icons.flag_outlined),
                    label: const Text('Marcar finalizada'),
                    // Si la sonda sigue transmitiendo hay que decirlo y parar
                    // las dos mitades juntas: cerrar solo la sesión dejaba a la
                    // sonda midiendo sin nadie que la capturara. Si ya había
                    // terminado sola, no hay nada que preguntar.
                    onPressed: _busy
                        ? null
                        : () async {
                            final estado = context.read<AppState>();
                            if (estado.sondaSigueCorriendo &&
                                !await _confirm(
                                    'La sonda sigue corriendo',
                                    'Vas a dar la corrida por finalizada, pero '
                                        'la sonda todavía está transmitiendo.\n\n'
                                        '¿Paro también la sonda?',
                                    'Parar y finalizar')) {
                              return;
                            }
                            await _fundido(estado.finalizarFundido);
                          },
                  ),
                ),
              ],
              const SizedBox(height: 16),

              // --- Estado de la sonda por BLE (el ACK, B2) ------------------
              const _SectionTitle('Sonda (BLE)'),
              _SondaPanel(st: st),
              const SizedBox(height: 16),

              // --- Datos OLED en vivo ---------------------------------------
              const _SectionTitle('En vivo'),
              OledPanel(
                session: s,
                metrics: st.currentMetrics,
                lastDownlink: st.lastDownlink,
                lectura: lectura,
              ),
              if (lectura != null) ...[
                const SizedBox(height: 16),
                const _SectionTitle('Vuelo · última lectura'),
                VueloPanel(
                  lectura: lectura,
                  metrics: st.currentMetrics,
                  rafagasObjetivo: _rafagasObjetivo(s!),
                ),
              ],
              // Sonda sin GPS (T3, D-65): distancia desde el telefono.
              if (s != null && s.gpsDelTelefono) ...[
                const SizedBox(height: 16),
                const _SectionTitle('Distancia · GPS del teléfono'),
                DistanciaTelefono(
                  metrics: st.currentMetrics,
                  fixLocal: st.fixTelefono,
                  aviso: st.avisoGps,
                ),
              ],
              const SizedBox(height: 16),

              // --- Ping -----------------------------------------------------
              OutlinedButton.icon(
                icon: const Icon(Icons.wifi_tethering),
                label: const Text('Ping (downlink fPort 98)'),
                onPressed: _busy
                    ? null
                    : () => _run(() async {
                          final seq = await context.read<AppState>().ping();
                          _snack('Ping encolado · seq $seq');
                        }),
              ),
              const SizedBox(height: 8),
              _statusLine(st),
            ],
          ),
        ),
      ],
    );
  }

  /// Por qué está cerrado el selector. Un control deshabilitado sin explicación,
  /// en campo, se interpreta como que la app está rota (§10.5).
  Widget _motivoSelector(AppState st, bool capturing) {
    final String? texto;
    if (capturing) {
      texto = 'La corrida no se cambia con una sesión en marcha.';
    } else {
      texto = st.bleMotivoBloqueo;
    }
    if (texto == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(capturing ? Icons.lock_outline : Icons.bluetooth_disabled,
              size: 14, color: AppColors.textDim),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              texto,
              style: const TextStyle(color: AppColors.textDim, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBigButton(AppState st, bool capturing, bool finished) {
    if (capturing) {
      // Decisión G: Abortar NUNCA depende del BLE. Si el enlace se cayó con una
      // corrida en marcha, la sesión de captura se tiene que poder cerrar igual.
      return BigActionButton(
        label: 'Abortar',
        icon: Icons.stop_circle_outlined,
        color: AppColors.red,
        busy: _busy,
        onPressed: _busy
            ? null
            : () async {
                final ok = await _confirm(
                    'Abortar sesión',
                    st.bleListo
                        ? 'Se para la sonda y se cierra la sesión. Los datos '
                            'capturados se conservan.'
                        : 'Sin Bluetooth: se cerrará la sesión en el servidor, '
                            'pero la sonda puede seguir transmitiendo. Párala '
                            'con el botón (pulsación larga).',
                    'Abortar');
                if (ok) {
                  await _fundido(
                      () => context.read<AppState>().abortarFundido());
                }
              },
      );
    }
    if (finished) {
      return BigActionButton(
        label: 'Finalizado',
        icon: Icons.check_circle_outline,
        color: AppColors.blue,
        busy: _busy,
        onPressed: () => context.read<AppState>().clearFinished(),
      );
    }
    // Sin sesion activa (o abortada): Arrancar. Gate de RF-7.
    return BigActionButton(
      label: 'Arrancar',
      icon: Icons.play_circle_outline,
      color: AppColors.green,
      busy: _busy,
      onPressed: st.bleListo && !_busy
          ? () async {
              final previo = st.bleAvisoPrevioArranque;
              if (previo != null) {
                final ok = await _confirm(
                    'La sonda no está en reposo', '$previo\n\n¿Intentarlo igual?',
                    'Intentar');
                if (!ok) return;
              }
              await _fundido(() => context.read<AppState>().arrancarFundido());
            }
          : null,
    );
  }

  Widget _profileHint(AppState st, bool capturing) {
    if (capturing) return const SizedBox.shrink();
    final run = findRun(st.selectedScenario, st.selectedClass);
    if (run == null) return const SizedBox.shrink();
    return Text(
      'Arrancar fija el perfil "${run.profile}", abre la sesión y arranca '
      'la sonda · ${run.subtitle}',
      textAlign: TextAlign.center,
      style: const TextStyle(color: AppColors.textDim, fontSize: 12),
    );
  }

  /// Rafagas de la sesion: `target_uplinks` / 3 (55 para 165).
  static int _rafagasObjetivo(Session s) {
    final run = findRun(s.scenario, s.sessionClass);
    final porRafaga = run?.paquetesPorRafaga ?? 3;
    return s.targetUplinks ~/ porRafaga;
  }

  Widget _statusLine(AppState st) {
    final parts = <String>[
      st.wsConnected ? 'WS conectado' : 'WS desconectado',
      st.mqttConnected ? 'MQTT ok' : 'MQTT ?',
      st.bleResumen,
      if (st.serverVersion != null) 'v${st.serverVersion}',
    ];
    return Text(
      parts.join(' · '),
      style: const TextStyle(color: AppColors.textDim, fontSize: 11),
    );
  }
}

/// Bloque de ACK (decisión B2): que el usuario vea que el cambio **surtió
/// efecto en la sonda**, no sólo que se envió. Lee los bytes 1, 2 y 4 de la
/// característica Estado (§4.3) tal como los expone `AppState` (§10.8).
class _SondaPanel extends StatelessWidget {
  final AppState st;
  const _SondaPanel({required this.st});

  @override
  Widget build(BuildContext context) {
    final modo = st.bleModo;

    // Confirmado = la sonda dice CORRIENDO y su modo es el de la sesión
    // abierta. Es el ACK de la decisión B2 visto de punta a punta: no «se envió
    // el comando», sino «el cambio surtió efecto en la sonda».
    final confirmado = st.bleCorridaConfirmada;

    final Color acento;
    final IconData icono;
    final String titulo;
    if (!st.bleConectado) {
      acento = AppColors.textDim;
      icono = Icons.bluetooth_disabled;
      titulo = 'Sin conexión con la sonda';
    } else if (!st.bleListo) {
      acento = AppColors.gold;
      icono = Icons.bluetooth_searching;
      titulo = st.bleEmparejando ? 'Emparejando…' : 'Enlace no operativo';
    } else if (confirmado) {
      acento = AppColors.green;
      icono = Icons.verified_outlined;
      titulo = 'Confirmado por la sonda';
    } else {
      acento = AppColors.cyan;
      icono = Icons.bluetooth_connected;
      titulo = 'Enlace seguro';
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.oledBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: acento.withOpacity(0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icono, size: 18, color: acento),
              const SizedBox(width: 8),
              Expanded(
                child: Text(titulo,
                    style: TextStyle(
                        color: acento,
                        fontWeight: FontWeight.bold,
                        fontSize: 13)),
              ),
              if (st.bleDireccion != null)
                Text(st.bleDireccion!,
                    style: const TextStyle(
                        color: AppColors.textDim,
                        fontSize: 11,
                        fontFamily: 'monospace')),
            ],
          ),
          const SizedBox(height: 8),
          _fila('Estado', st.bleEstadoTexto),
          _fila(
              'Modo',
              modo != null && modo >= 0 && modo < kRuns.length
                  ? '${kRuns[modo].label} · fP${kRuns[modo].fPort}'
                  : '—'),
          _fila('Último comando', st.bleUltCmdTexto),
          if (st.bleVerIncompatible)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                'Firmware BLE incompatible (v${st.bleVer}, se esperaba '
                'v${st.bleVerQueEspera}). No se enviará ningún comando.',
                style: const TextStyle(color: AppColors.red, fontSize: 12),
              ),
            ),
        ],
      ),
    );
  }

  Widget _fila(String etiqueta, String valor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(
            width: 130,
            child: Text(etiqueta,
                style:
                    const TextStyle(color: AppColors.textDim, fontSize: 12)),
          ),
          Expanded(
            child: Text(valor,
                style: const TextStyle(
                    color: AppColors.text,
                    fontSize: 13,
                    fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

/// Banda de aviso del panel. Como [WarningBanner] pero con `onDismiss`
/// opcional: hay avisos que no se pueden descartar porque describen una
/// situación que sigue ocurriendo.
class _Aviso extends StatelessWidget {
  final String message;
  final VoidCallback? onDismiss;
  final Color color;
  final IconData icon;

  /// Accion correctiva opcional. Cuando el aviso describe algo que tiene un
  /// arreglo evidente, obligar a navegar a otra parte para aplicarlo es
  /// gratuito: se ofrece aqui mismo, a un toque.
  final String? accionTexto;
  final VoidCallback? onAccion;

  const _Aviso({
    required this.message,
    this.onDismiss,
    this.color = AppColors.red,
    this.icon = Icons.warning_amber_rounded,
    this.accionTexto,
    this.onAccion,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color,
      child: Padding(
        padding: EdgeInsets.only(
            left: 12, right: onDismiss == null ? 12 : 0, top: 8, bottom: 8),
        child: Row(
          children: [
            Icon(icon, color: Colors.white),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message,
                style: const TextStyle(
                    color: Colors.white, fontWeight: FontWeight.w600),
              ),
            ),
            if (accionTexto != null && onAccion != null)
              TextButton(
                onPressed: onAccion,
                style: TextButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white70),
                ),
                child: Text(accionTexto!),
              ),
            if (onDismiss != null)
              IconButton(
                icon: const Icon(Icons.close, color: Colors.white),
                onPressed: onDismiss,
                tooltip: 'Descartar',
              ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        text.toUpperCase(),
        style: const TextStyle(
          color: AppColors.gold,
          fontSize: 12,
          fontWeight: FontWeight.bold,
          letterSpacing: 1.2,
        ),
      ),
    );
  }
}
