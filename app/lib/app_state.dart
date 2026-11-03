import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api/campo_api.dart';
import 'api/campo_ws.dart';
import 'ble/ble_client.dart';
import 'ble/flujo_rejoin.dart';
import 'config.dart';
import 'gps/gps_telefono.dart';
import 'models/models.dart';
import 'runs.dart';

/// Aviso de desajuste de fPort recibido por WS (§7 `warning`).
class FportWarning {
  final int expected;
  final int got;
  final DateTime at;
  FportWarning(this.expected, this.got) : at = DateTime.now();
}

/// Gravedad del resultado de una accion fundida.
enum NivelFusion { ok, aviso, error }

/// Resultado de una accion que toca las dos mitades del sistema.
///
/// Ni [AppState.arrancarFundido] ni [AppState.abortarFundido] lanzan: en campo
/// lo que hace falta saber no es «falló», sino **qué quedó hecho y qué no**. Un
/// `throw` colapsa esa distincion en un solo bit y obliga a acordarse de un
/// try/catch justo donde mas caro sale olvidarlo.
class ResultadoFusion {
  final NivelFusion nivel;
  final String mensaje;
  const ResultadoFusion(this.nivel, this.mensaje);

  bool get ok => nivel == NivelFusion.ok;
}

/// Estado global de la app. Mantiene la config, el cliente REST y el WebSocket,
/// y expone la sesion/metricas/uplinks en vivo. Gestion ligera (ChangeNotifier).
///
/// En la v2 es ademas donde vive la **selección fundida** (RF-3): una sola
/// accion fija el perfil A/C en ChirpStack, abre la sesion de captura y arranca
/// la sonda por BLE, en el orden que fija §10.5 del CONTRATO-BLE.
///
/// El estado del enlace NO se copia aqui: se delega en [BleClient], que es su
/// dueno (§10.8). Dos copias del mismo dato que pueden divergir es exactamente
/// el problema que la v2 viene a eliminar; no se reintroduce dentro de la app.
/// Resultado de abrir la sesion de captura: o la sesion, o el fallo ya
/// redactado. Exactamente uno de los dos es no nulo.
class _Apertura {
  final Session? sesion;
  final ResultadoFusion? fallo;

  const _Apertura.ok(Session this.sesion) : fallo = null;
  const _Apertura.error(ResultadoFusion this.fallo) : sesion = null;
}

class AppState extends ChangeNotifier {
  AppConfig config = const AppConfig();
  bool initialized = false;

  CampoApi? _api;
  CampoWs? _ws;

  bool wsConnected = false;
  bool mqttConnected = false;
  String? serverVersion;

  Session? currentSession;
  Metrics? currentMetrics;
  final List<Uplink> uplinks = <Uplink>[]; // de la sesion activa
  FportWarning? warning;
  String? lastDownlink; // "ping #12"

  /// Aviso persistente de que el sistema quedo **a medias** tras una accion
  /// fundida (p. ej. sesion abierta en el servidor sin corrida en la sonda).
  /// Es el mas importante de los avisos: describe trabajo pendiente, no un
  /// error que ya paso. Descartable.
  String? avisoFusion;

  /// Aviso de que el enlace se cayo con una corrida en marcha. Lo pone
  /// `AppState` y no [BleClient] porque el cliente BLE no sabe —ni debe saber—
  /// si hay una sesion de captura abierta.
  String? avisoBle;

  /// Progreso del re-join automatico tras el 409 del gate de clase (§15.1);
  /// null si no hay ninguno en curso. Mientras no es null, el panel pinta la
  /// banda de progreso con su boton «Cancelar»: la espera del join es larga
  /// (patron D-57) y tiene que poder abortarse.
  String? progresoRejoin;
  FlujoRejoin? _flujoRejoin;

  /// Momento del ultimo `warning {kind:"class_mismatch"}` del WS. Es la senal
  /// secundaria de deteccion del gate de clase (la primaria es el prefijo del
  /// `detail` del 409, que el contrato garantiza).
  DateTime? _ultimoClassMismatchWs;

  /// Cancela la espera del re-join en curso (boton de la banda de progreso).
  /// Inofensivo si no hay ninguno. No des-hace el re-join: la orden ya viajo.
  void cancelarRejoin() => _flujoRejoin?.cancelar();

  // Seleccion del panel (corrida a arrancar).
  String selectedScenario = 'URBANO';
  String selectedClass = 'A';

  CampoApi? get api => _api;

  /// Sonda conectada por BLE (D-65): `tbeam` o `lora32`. Decide que corridas
  /// se ofrecen y a que device abre la sesion el servidor.
  String get sonda => _ble?.sonda ?? kSondaTbeam;

  /// Cambia la corrida seleccionada en el panel.
  void selectRun(String scenario, String cls) {
    final r = findRun(scenario, cls);
    if (r != null && !corridaAdmitida(r, sonda)) return;
    selectedScenario = scenario;
    selectedClass = cls;
    notifyListeners();
  }

  Future<void> init() async {
    config = await AppConfig.load();
    initialized = true;
    if (config.isValid) {
      _setupClients();
      // Backfill inicial sin bloquear el arranque.
      unawaited(refreshCurrent());
    }
    notifyListeners();
  }

  void _setupClients() {
    _ws?.dispose();
    _api?.close();
    _api = CampoApi(config);
    _ws = CampoWs(
      config,
      onMessage: _onWsMessage,
      onState: (c) {
        wsConnected = c;
        notifyListeners();
      },
    );
    _ws!.connect();
  }

  Future<void> saveConfig(AppConfig c) async {
    config = c;
    await c.save();
    // Cambiar de servidor invalida la sesion en memoria.
    currentSession = null;
    currentMetrics = null;
    uplinks.clear();
    warning = null;
    lastDownlink = null;
    wsConnected = false;
    avisoFusion = null;
    if (c.isValid) {
      _setupClients();
      unawaited(refreshCurrent());
    } else {
      _ws?.dispose();
      _ws = null;
      _api?.close();
      _api = null;
    }
    notifyListeners();
  }

  /// Sincroniza la sesion activa desde REST (verdad autoritativa) y rellena el
  /// buffer de uplinks para el mapa/graficos.
  Future<void> refreshCurrent() async {
    final api = _api;
    if (api == null) return;
    try {
      final res = await api.getCurrent();
      currentSession = res.session;
      currentMetrics = res.metrics;
      uplinks.clear();
      final s = currentSession;
      if (s != null) {
        try {
          uplinks.addAll(await api.getUplinks(s.id));
        } catch (_) {}
      }
      notifyListeners();
    } catch (_) {
      // Silencioso: el WS reintenta y actualiza igualmente.
    }
  }

  void _onWsMessage(Map<String, dynamic> m) {
    switch (m['type']?.toString()) {
      case 'hello':
        serverVersion = asString(m['version']);
        mqttConnected = asBool(m['mqtt_connected']) ?? false;
        final s = asMap(m['session']);
        currentSession = s == null ? null : Session.fromJson(s);
        notifyListeners();
        // Rellena uplinks/metricas de la sesion activa tras (re)conectar.
        unawaited(refreshCurrent());
        break;

      case 'session':
        final prev = currentSession?.id;
        currentSession = Session.fromJson(m);
        // Sesion nueva capturando: limpia buffer, avisos y METRICAS previas.
        // Sin el reset de metricas, el contador de la corrida anterior (RX 300)
        // seguia en pantalla hasta el primer uplink de la nueva — que en
        // C-Fondo (esperando enlace) puede tardar minutos.
        if (currentSession!.isCapturing && currentSession!.id != prev) {
          uplinks.clear();
          warning = null;
          currentMetrics = null;
        }
        notifyListeners();
        break;

      case 'uplink':
        uplinks.add(Uplink.fromJson(m));
        // Evita crecer sin limite en corridas largas (300 uplinks x N).
        if (uplinks.length > 2000) uplinks.removeRange(0, uplinks.length - 2000);
        notifyListeners();
        break;

      case 'metrics':
        currentMetrics = Metrics.fromJson(m);
        notifyListeners();
        break;

      case 'warning':
        final kind = asString(m['kind']);
        if (kind == 'fport_mismatch') {
          warning = FportWarning(asInt(m['expected']) ?? 0, asInt(m['got']) ?? 0);
          notifyListeners();
        } else if (kind == 'class_mismatch') {
          // Senal secundaria del gate de clase (§15.1). La primaria es el 409
          // de `startSession`, que llega por el camino de la peticion y es el
          // que dispara el re-join; esta solo deja constancia de que el
          // servidor tambien lo vio, para no depender de un unico canal.
          _ultimoClassMismatchWs = DateTime.now();
        }
        break;

      case 'ping_ack':
        final seq = asInt(m['seq']);
        if (seq != null) {
          lastDownlink = 'ping #$seq';
          notifyListeners();
        }
        break;
    }
  }

  // =========================================================================
  // BLE — el enlace con la sonda (§10.8)
  // =========================================================================
  //
  // `AppState` no reimplementa nada de BLE: el dueno del enlace es `BleClient`
  // y aqui solo se reexpone lo que las pantallas necesitan, mas las dos cosas
  // que el cliente no puede saber porque no conoce la sesion de captura: el
  // aviso de «BLE caido, la corrida sigue» y la comprobacion de desajuste.

  BleClient? _ble;
  BleClient? get ble => _ble;
  bool _bleEstabaConectado = false;

  /// Id de la sesion cuya corrida se llego a ver VIVA en la sonda: CORRIENDO o
  /// ESPERANDO_ENLACE. Se guarda el id y no un booleano para que el dato no se
  /// arrastre a la sesion siguiente. Incluir ESPERANDO_ENLACE (C-Fondo) es lo
  /// que permite detectar el aborto desde el boton cuando la corrida aun
  /// esperaba enlace; antes solo contaba CORRIENDO y ese aborto pasaba inadvertido.
  int? _sesionVistaActiva;

  /// La corrida esta VIVA en la sonda: corriendo, o agendada esperando enlace.
  static bool _corridaViva(int? estadoSonda) =>
      estadoSonda == BleEstadoSonda.corriendo ||
      estadoSonda == BleEstadoSonda.esperandoEnlace;

  /// Engancha el cliente BLE. Lo llama quien lo crea (la pantalla de
  /// dispositivo o el `provider` de arranque). Es idempotente.
  void adjuntarBle(BleClient cliente) {
    if (identical(_ble, cliente)) return;
    _ble?.removeListener(_alCambiarBle);
    _ble = cliente;
    cliente.addListener(_alCambiarBle);
    _bleEstabaConectado = cliente.conectado;
    notifyListeners();
  }

  void desadjuntarBle() {
    _ble?.removeListener(_alCambiarBle);
    _ble = null;
    _bleEstabaConectado = false;
    notifyListeners();
  }

  void _alCambiarBle() {
    final c = _ble;
    if (c == null) return;

    // §10.4 — desconexion inesperada con corrida en marcha. El operador NO debe
    // pensar que se le paro la sonda: no se paro (RNF-2), la corrida es
    // autonoma y el BLE solo es control.
    final s = currentSession;
    if (_bleEstabaConectado && !c.conectado && s != null && s.isCapturing) {
      avisoBle = 'Bluetooth caído. La corrida sigue en la sonda: la app '
          'reconecta sola y vuelve a leer el estado. Abortar sigue disponible.';
    }
    _bleEstabaConectado = c.conectado;

    // La T3 solo corre VUELO-A (D-65): al conectarla, el panel se coloca ahi.
    final sel = corridaSeleccionada;
    if (sel == null || !corridaAdmitida(sel, c.sonda)) {
      selectedScenario = kEscenarioVuelo;
      selectedClass = 'A';
    }

    // Se anota que ESTA sesion llego a verse VIVA en la sonda (corriendo o
    // esperando enlace). Es lo que distingue "aun no ha arrancado" de "arranco
    // y se paro", y sin esa distincion el aviso de [avisoSondaParada] saltaria
    // en el segundo que va entre abrir la sesion y el primer Estado vivo.
    if (s != null && s.isCapturing && _corridaViva(c.estadoSonda)) {
      _sesionVistaActiva = s.id;
    }
    notifyListeners();
  }

  // --- lo que ve la interfaz (§10.8) ---------------------------------------

  bool get bleEscaneando => _ble?.escaneando ?? false;
  bool get bleConectado => _ble?.conectado ?? false;
  bool get bleSeguro => _ble?.seguro ?? false;
  bool get bleEmparejando => _ble?.emparejando ?? false;
  String? get bleDireccion => _ble?.direccion;
  int? get bleVer => _ble?.ver; // byte 0 de Estado
  int? get bleModo => _ble?.modo; // 0..6, null si 0xFF
  int? get bleEstadoSonda => _ble?.estadoSonda; // §8.1
  int? get bleUltCmd => _ble?.ultCmd; // §8.2

  /// **El gate de RF-7** (§10.5): cierra el selector y Arrancar. **Nunca**
  /// Abortar (decision G).
  bool get bleListo => _ble?.listo ?? false;

  /// Por que esta cerrado el gate. Un control deshabilitado sin explicacion,
  /// en campo, se interpreta como que la app esta rota (§10.5).
  String? get bleMotivoBloqueo => _ble == null
      ? 'Bluetooth no iniciado. Ve a «Dispositivo» y conecta la sonda para '
          'poder elegir corrida.'
      : _ble!.motivoGateCerrado;

  bool get bleVerIncompatible => bleVer != null && bleVer != bleVerEsperada;

  /// Version de protocolo que esta app sabe hablar (§10.2), para pintarla.
  int get bleVerQueEspera => bleVerEsperada;

  /// Etiquetas de los bytes de Estado, para que las pantallas no tengan que
  /// importar `ble_client.dart` solo para traducir dos enteros.
  String get bleEstadoTexto => BleEstadoSonda.etiqueta(bleEstadoSonda);
  String get bleUltCmdTexto => BleUltCmd.etiqueta(bleUltCmd);

  /// Resumen del enlace para la linea de estado del panel.
  String get bleResumen {
    final c = _ble;
    if (c == null) return 'BLE sin iniciar';
    if (!c.listo) return 'BLE: ${c.motivoGateCerrado ?? "no disponible"}';
    return 'Sonda ${BleEstadoSonda.etiqueta(bleEstadoSonda).toLowerCase()}'
        '${_etiquetaModo(bleModo)}';
  }

  /// Advertencia previa al comando: el enlace esta listo pero la sonda no va a
  /// aceptar un `seleccionar` (§5.3). NO cierra el gate —el contrato fija la
  /// formula de [bleListo]— pero evita que el operador se coma un rechazo 132
  /// sin haber sido avisado.
  String? get bleAvisoPrevioArranque {
    if (!bleListo) return null;
    switch (bleEstadoSonda) {
      case BleEstadoSonda.corriendo:
        return 'La sonda ya está corriendo${_etiquetaModo(bleModo)}. '
            'Abórtala antes de arrancar otra.';
      case BleEstadoSonda.esperandoEnlace:
        return 'La sonda ya tiene una corrida esperando enlace. '
            'Abórtala antes de arrancar otra.';
      // SIN_ENLACE no avisa: arrancar sin enlace es el flujo normal en C-Fondo.
      // La sonda entra en "esperando enlace" y arranca sola en cuanto une.
      default:
        return null;
    }
  }

  /// La sonda confirmo la corrida que hay abierta en el servidor: es el ACK de
  /// la decision B2 visto de punta a punta, no solo «se envió el comando».
  bool get bleCorridaConfirmada {
    final s = currentSession;
    if (s == null || !s.isCapturing) return false;
    if (bleEstadoSonda != BleEstadoSonda.corriendo) return false;
    final r = _runDeModo(bleModo);
    return r != null && r.scenario == s.scenario && r.cls == s.sessionClass;
  }

  /// **La comprobacion que justifica la v2** (§10.8): con la sonda CORRIENDO y
  /// una sesion abierta, si el modo de la sonda no es el de la sesion se ve
  /// aqui **antes** de que el desajuste de fPort llegue por el camino largo del
  /// servidor. No deberia ocurrir nunca; si ocurre, esta es la unica mitad del
  /// sistema que puede verlo en el acto.
  String? get avisoDesajusteBle {
    final s = currentSession;
    if (s == null || !s.isCapturing) return null;
    if (bleEstadoSonda != BleEstadoSonda.corriendo) return null;
    final r = _runDeModo(bleModo);
    if (r == null) return null;
    if (r.scenario == s.scenario && r.cls == s.sessionClass) return null;
    return 'Desajuste: la sonda corre ${r.label} (fP${r.fPort}) y la sesión es '
        '${s.scenario} ${s.sessionClass} (fP${s.expectedFport}). '
        'Aborta y vuelve a arrancar.';
  }

  /// La otra mitad del desajuste, y la que faltaba: **la sonda se paró y la
  /// sesión sigue abierta**.
  ///
  /// Pasa siempre que se aborta con el botón —con Bluetooth o sin él— y hasta
  /// ahora no se veía en ninguna parte: la sesión seguía abierta grabando nada.
  /// Eso reintroduce justo la divergencia que la v2 elimina, y además falsea la
  /// duración de la sesión, que es la ventana temporal con la que `cruzar.py`
  /// acota el cruce contra la microSD.
  ///
  /// Sólo se avisa si esta sesión **llegó a verse viva** (corriendo o esperando
  /// enlace): si no, lo que hay es un arranque en curso, no una parada. Y sólo
  /// con enlace seguro, porque sin él el estado que se lee no es de fiar.
  ///
  /// NO cierra la sesión sola a propósito. Es el mismo criterio que se aplica
  /// cuando no llega el ACK: no destruir nada por inferencia. Cerrar una sesión
  /// no se deshace, y un estado leído mal mataría una captura viva.
  String? get avisoSondaParada {
    final s = currentSession;
    if (s == null || !s.isCapturing) return null;
    if (!bleListo) return null;
    if (_sesionVistaActiva != s.id) return null;
    // Mientras la corrida siga viva (corriendo o esperando enlace) no es una
    // parada. El aviso es para cuando la sonda VUELVE a reposo con la sesión aún
    // abierta -- incluido el aborto desde el botón durante la espera (C-Fondo).
    if (_corridaViva(bleEstadoSonda)) return null;

    final estado = BleEstadoSonda.etiqueta(bleEstadoSonda).toLowerCase();
    return 'La sonda ya no tiene la corrida en marcha ($estado) pero la sesión '
        '#${s.id} sigue abierta y no está capturando nada.';
  }

  void descartarAvisoBle() {
    avisoBle = null;
    notifyListeners();
  }

  void descartarAvisoFusion() {
    avisoFusion = null;
    notifyListeners();
  }

  /// Indice 0..6 de una corrida, que es exactamente el `modo` del contrato
  /// (§4.2): `kRuns` y la tabla de modos coinciden por construccion. OJO: ya
  /// no vale `escenario = modo / 2`, `clase = modo % 2` — VUELO (modo 6) solo
  /// tiene Clase A. La tabla manda.
  int? modoDe(String scenario, String cls) => modoDeCorrida(scenario, cls);

  int? get modoSeleccionado => modoDe(selectedScenario, selectedClass);

  RunDef? _runDeModo(int? modo) => corridaDeModo(modo);

  /// Corrida seleccionada en el panel (null si la combinacion no existe).
  RunDef? get corridaSeleccionada =>
      findRun(selectedScenario, selectedClass);

  String _etiquetaModo(int? modo) {
    final r = _runDeModo(modo);
    return r == null ? '' : ' ${r.label}';
  }

  // =========================================================================
  // Acciones fundidas (RF-3 / RF-5, §10.5)
  // =========================================================================

  /// ¿Es este fallo el 409 del gate de clase (§15.1)? Se mira el codigo **y**
  /// el `detail`, que el contrato fija: el 409 tambien lo usa «ya hay una
  /// sesion abierta», que no se arregla con un re-join. Si el texto no cuadra
  /// se acepta la senal del WS recibida hace un instante, para no depender de
  /// una redaccion exacta del servidor.
  bool _esClaseDesajustada(Object e) {
    if (e is! ApiException || e.statusCode != 409) return false;
    if (e.message.contains('clase desajustada')) return true;
    final ws = _ultimoClassMismatchWs;
    return ws != null &&
        DateTime.now().difference(ws) < const Duration(seconds: 10);
  }

  /// Abre la sesion, recuperandose del gate de clase si hace falta.
  ///
  /// ChirpStack congela la clase efectiva en el JOIN, asi que cambiar el perfil
  /// no basta: hace falta un JOIN nuevo. El `start` que acaba de fallar **ya
  /// dejo puesto el perfil correcto**, de modo que la recuperacion completa es
  /// ordenar el re-join por BLE (op 0x03) y repetir el `start` una sola vez.
  /// Antes esto era «apaga y enciende la sonda»: cambiar de clase A↔C es el
  /// caso de uso central de la app, y resolverlo a mano reintroducia el error
  /// humano que la v2 vino a eliminar (D-62).
  Future<_Apertura> _abrirSesion(CampoApi api, BleClient cliente) async {
    try {
      return _Apertura.ok(await api.startSession(
          selectedScenario, selectedClass,
          sonda: cliente.sonda));
    } catch (e) {
      if (!_esClaseDesajustada(e)) {
        // Nada que deshacer: la sonda no se ha tocado.
        return _Apertura.error(ResultadoFusion(NivelFusion.error,
            'No se abrió la sesión: ${_texto(e)}. La sonda no se ha tocado.'));
      }

      // --- Recuperacion: re-join por BLE y un unico reintento --------------
      final flujo = FlujoRejoin(
        enviarRejoin: cliente.rejoin,
        cambiosEstado: cliente.cambiosEstado,
        volverAlMenu: cliente.abortar,
        alProgresar: (msg) {
          progresoRejoin = msg;
          notifyListeners();
        },
      );
      _flujoRejoin = flujo;
      progresoRejoin = 'La clase del servidor no coincide; pidiendo a la sonda '
          'un JOIN nuevo…';
      notifyListeners();

      final RejoinFin fin;
      try {
        fin = await flujo.ejecutar();
      } finally {
        _flujoRejoin = null;
        progresoRejoin = null;
        notifyListeners();
      }

      if (!fin.ok) {
        // El respaldo manual sigue existiendo y hay que nombrarlo: sin el, el
        // operador se queda mirando un error sin salida en mitad del campo.
        const respaldo = 'Apaga y enciende la sonda y vuelve a arrancar.';
        final detalle = fin.desenlace == RejoinDesenlace.firmwareSinRejoin
            ? '${fin.mensaje} $respaldo'
            : '${fin.mensaje} Si no completa el JOIN, $respaldo';
        return _Apertura.error(
            ResultadoFusion(NivelFusion.error, 'No se abrió la sesión: '
                'la clase de ChirpStack no coincidía con la corrida. $detalle'));
      }

      // JOIN nuevo hecho: ChirpStack ya tiene congelada la clase correcta.
      try {
        return _Apertura.ok(await api.startSession(
            selectedScenario, selectedClass,
            sonda: cliente.sonda));
      } catch (e2) {
        // Un segundo 409 NO se reintenta: si tras un JOIN nuevo la clase sigue
        // sin cuadrar, el problema esta en el perfil del servidor, y repetir el
        // ciclo solo alargaria el fallo sin cambiar nada.
        return _Apertura.error(ResultadoFusion(
            NivelFusion.error,
            'La sonda rehízo el JOIN, pero la sesión siguió sin abrirse: '
            '${_texto(e2)}'));
      }
    }
  }

  /// **RF-3 — arrancar: servidor primero, BLE después.**
  ///
  /// El orden no es estetico; lo fija la asimetria de los dos fallos posibles:
  ///
  /// - *BLE primero y falla el servidor*: la sonda **esta transmitiendo** con
  ///   un perfil de ChirpStack que puede ser el equivocado. Una Clase C contra
  ///   un perfil de Clase A no encola los downlinks inmediatos y produce una
  ///   medida **silenciosamente falsa**, que se parece mucho a «la Clase C no
  ///   funciona» — justo el error que la v2 viene a hacer imposible.
  /// - *Servidor primero y falla el BLE*: queda una sesion vacia, evidente al
  ///   instante, y el paso 4 la cierra sola.
  ///
  /// Se elige el fallo visible y reversible sobre el invisible que contamina un
  /// dato. Ademas el paso 1 es **una sola llamada** que hace las dos cosas del
  /// lado servidor (perfil A/C y sesion), asi que no hay estado intermedio que
  /// deshacer a medias.
  Future<ResultadoFusion> arrancarFundido() async {
    final api = _api;
    if (api == null) {
      return const ResultadoFusion(
          NivelFusion.error, 'Sin configuración válida del servidor.');
    }

    final modo = modoSeleccionado;
    if (modo == null) {
      return ResultadoFusion(NivelFusion.error,
          'Corrida desconocida: $selectedScenario $selectedClass.');
    }

    final cliente = _ble;
    if (cliente == null || !cliente.listo) {
      // El gate de RF-7 ya deberia impedir llegar aqui; se comprueba igual
      // porque el enlace puede caerse entre el toque y este `await`.
      return ResultadoFusion(NivelFusion.error,
          bleMotivoBloqueo ?? 'La sonda no está lista por Bluetooth.');
    }

    // --- 1. Servidor: perfil A/C + sesion de captura, en una sola llamada ---
    //        Si el gate de clase (§15.1) la rechaza, aqui dentro se rehace el
    //        JOIN por BLE y se reintenta: para el operador es un solo toque.
    final apertura = await _abrirSesion(api, cliente);
    if (apertura.fallo != null) return apertura.fallo!;
    final sesion = apertura.sesion!;

    currentSession = sesion;
    currentMetrics = null;
    warning = null;
    uplinks.clear();
    avisoFusion = null;
    notifyListeners();

    // --- 3. BLE: seleccionar(modo). Seleccionar es tambien arrancar (RF-4).
    //        El cliente ya espera dentro el ACK del paso 5 (§10.5).
    final r = await cliente.seleccionar(modo);

    if (!r.aceptado) {
      // --- 4. Deshacer el paso 1 -------------------------------------------
      try {
        currentSession = await api.abortSession(sesion.id);
        notifyListeners();
        return ResultadoFusion(
            NivelFusion.error,
            '${r.mensaje} Se cerró la sesión #${sesion.id}: '
            'no queda nada a medias.');
      } catch (e2) {
        // El unico caso realmente feo: sesion abierta en el servidor y sonda
        // parada. Va a aviso persistente porque es trabajo pendiente, no un
        // error que ya paso.
        avisoFusion =
            'Quedó la sesión #${sesion.id} (${sesion.runLabel}) ABIERTA en el '
            'servidor sin corrida en la sonda. Ciérrala con «Abortar» en '
            'cuanto vuelva la red.';
        notifyListeners();
        return ResultadoFusion(
            NivelFusion.error,
            '${r.mensaje} Y tampoco se pudo cerrar la sesión: '
            '${_texto(e2)}.');
      }
    }

    // --- 5. Aceptado. Con o sin confirmacion, NO se deshace nada ------------
    //
    // Sin ACK no se revierte, y es deliberado: la escritura fue *with response*
    // y la sonda la acepto, asi que lo mas probable es que este corriendo y
    // solo se haya perdido la notificacion. Abortar aqui cerraria la captura de
    // una corrida que si esta en marcha — peor que un aviso.
    if (r.ok) {
      final run = kRuns[modo]; // modo validado arriba: indice de kRuns
      // C-Fondo: si la sonda aún no tiene enlace, aceptó el arranque y quedó
      // ESPERANDO_ENLACE; arrancará sola al unir. Es un resultado OK, no un
      // fallo: la sesión queda abierta a propósito.
      if (r.estado?.estado == BleEstadoSonda.esperandoEnlace) {
        return ResultadoFusion(
            NivelFusion.ok,
            'Sesión abierta. La sonda espera enlace y arrancará ${run.label} '
            '(fP${run.fPort}) en cuanto una a la red.');
      }
      return ResultadoFusion(NivelFusion.ok,
          'Corriendo ${run.label} (fP${run.fPort}) · confirmado por la sonda.');
    }
    return ResultadoFusion(
        NivelFusion.aviso, '${r.mensaje} La sesión sigue abierta.');
  }

  /// **RF-5 + decisión G — abortar: BLE primero, servidor SIEMPRE.**
  ///
  /// BLE primero porque parar la transmision es lo urgente y es local. Y el
  /// servidor **sin condicion**: el gate «sin BLE no se opera» aplica a
  /// seleccionar/arrancar, nunca a abortar. Si el Bluetooth se cae con una
  /// corrida en marcha, el operador tiene que poder cerrar la sesion de captura
  /// igualmente (decision G, T-39).
  Future<ResultadoFusion> abortarFundido() async {
    // --- 1. BLE si lo hay. Si falla, SE SIGUE: no bloquea el paso 2. --------
    final cliente = _ble;
    final rBle = cliente == null ? null : await cliente.abortar();
    final seIntentoBle =
        rBle != null && rBle.resultado != BleCmdResultado.sinEnlace;

    // --- 2. Servidor: SIEMPRE, haya BLE o no -------------------------------
    final api = _api;
    final s = currentSession;
    String? falloServidor;
    if (api == null) {
      falloServidor = 'no hay configuración válida del servidor';
    } else if (s != null) {
      try {
        currentSession = await api.abortSession(s.id);
        notifyListeners();
      } catch (e) {
        falloServidor = _texto(e);
      }
    }

    // --- Que se le cuenta al operador --------------------------------------
    if (falloServidor != null) {
      if (s != null) {
        avisoFusion =
            'No se pudo cerrar la sesión #${s.id} en el servidor. Reintenta '
            '«Abortar» cuando vuelva la red.';
      }
      notifyListeners();
      final sonda = seIntentoBle && rBle.aceptado
          ? 'La sonda sí recibió el aborto. '
          : '';
      return ResultadoFusion(
          NivelFusion.error, '${sonda}No se cerró la sesión: $falloServidor.');
    }

    if (!seIntentoBle) {
      // El caso de la decision G y de T-39: sin BLE la sesion se cierra igual,
      // pero hay que decir que la sonda puede seguir transmitiendo.
      return const ResultadoFusion(
          NivelFusion.aviso,
          'Sesión cerrada en el servidor. Sin Bluetooth no se pudo parar la '
          'sonda: párala con el botón (pulsación larga) si sigue '
          'transmitiendo.');
    }

    if (!rBle.aceptado) {
      return ResultadoFusion(
          NivelFusion.aviso,
          'Sesión cerrada, pero la sonda no confirmó el aborto: '
          '${rBle.mensaje} Párala con el botón si hace falta.');
    }

    return const ResultadoFusion(
        NivelFusion.ok, 'Sesión cerrada y sonda de vuelta a configuración.');
  }

  /// `ApiException.toString()` ya da «HTTP 409: …» o «Sin conexión: …», que es
  /// lo que hay que ensenar tal cual.
  static String _texto(Object e) => e.toString();

  // --- acciones de servidor (§6) -------------------------------------------

  /// ¿Sigue la sonda corriendo la corrida que se va a dar por finalizada? Lo
  /// usa el panel para preguntar antes de pararla.
  bool get sondaSigueCorriendo => _corridaViva(bleEstadoSonda);

  /// **Marcar finalizada: sonda primero, servidor siempre.** Mismo orden que
  /// abortar, y por el mismo motivo: lo urgente es que la sonda deje de
  /// transmitir, y es lo único que se resuelve sin red.
  ///
  /// Hasta aquí este gesto cerraba **solo la contabilidad del servidor** y la
  /// sonda seguía midiendo sin nadie que la capturara: uplinks huérfanos,
  /// batería gastada y el fCnt de la corrida siguiente contaminado. El
  /// operador tenía que acordarse de pararla a mano con el botón.
  ///
  /// Si la sonda ya había terminado sola, no se le manda nada: solo se cierra
  /// la sesión, que es el caso para el que nació el botón (la sonda llega a
  /// `target_uplinks` pero el servidor no se entera porque se perdieron
  /// uplinks por el camino).
  ///
  /// OJO: cortada antes de tiempo, la corrida queda registrada como FINALIZADA
  /// aunque sea parcial. El análisis puede distinguirla igualmente —su cuenta
  /// de uplinks se queda corta frente a `target_uplinks`—, pero conviene
  /// saberlo al leer los resultados.
  Future<ResultadoFusion> finalizarFundido() async {
    // --- 1. Parar la sonda si sigue corriendo. Si falla, SE SIGUE ----------
    final cliente = _ble;
    final sondaViva = sondaSigueCorriendo;
    final rBle = (sondaViva && cliente != null) ? await cliente.abortar() : null;
    final paro = rBle != null && rBle.aceptado;

    // --- 2. Servidor: cerrar como FINALIZADA -------------------------------
    final api = _api;
    final s = currentSession;
    if (api == null || s == null) {
      return const ResultadoFusion(
          NivelFusion.error, 'No hay ninguna sesión que finalizar.');
    }
    try {
      currentSession = await api.finishSession(s.id);
      notifyListeners();
    } catch (e) {
      if (paro) {
        avisoFusion = 'La sonda se paró, pero la sesión #${s.id} sigue ABIERTA '
            'en el servidor. Ciérrala cuando vuelva la red.';
      }
      notifyListeners();
      return ResultadoFusion(
          NivelFusion.error,
          '${paro ? 'La sonda se paró. ' : ''}'
          'No se cerró la sesión: ${_texto(e)}.');
    }

    // --- 3. Que se le cuenta al operador -----------------------------------
    if (sondaViva && !paro) {
      // Es justo el fallo que este camino viene a evitar, así que se dice sin
      // rodeos y con el remedio manual al lado.
      final porque = rBle == null ? ' (sin Bluetooth)' : ': ${rBle.mensaje}';
      return ResultadoFusion(
          NivelFusion.aviso,
          'Sesión finalizada, pero la sonda NO confirmó la parada$porque. '
          'Párala con el botón: pulsación larga.');
    }
    return ResultadoFusion(
        NivelFusion.ok,
        sondaViva
            ? 'Corrida finalizada y sonda parada.'
            : 'Corrida finalizada.');
  }

  Future<int> ping() async {
    final api = _api;
    if (api == null) throw ApiException(0, 'Sin configuración válida');
    final seq = await api.ping();
    lastDownlink = 'ping #$seq';
    notifyListeners();
    return seq;
  }

  void dismissWarning() {
    warning = null;
    notifyListeners();
  }

  /// Al pulsar el boton azul "Finalizado": limpia la sesion terminada en memoria
  /// para volver a habilitar "Arrancar".
  void clearFinished() {
    final s = currentSession;
    if (s != null && !s.isCapturing) {
      currentSession = null;
      currentMetrics = null;
      notifyListeners();
    }
  }

  // =========================================================================
  // GPS del telefono (D-65): la distancia de las sondas sin GPS propio
  // =========================================================================

  GpsTelefono? _gps;
  int? _gpsSesion;

  /// Problema con el GPS del telefono (apagado, sin permiso, fallo al enviar).
  String? avisoGps;

  /// Ultimo fix del telefono, enviado o no (para pintarlo al instante).
  FixTelefono? get fixTelefono => _gps?.ultimo;

  /// Toda transicion de sesion pasa por aqui, asi el GPS sigue a la sesion sin
  /// tener que tocar cada camino que la abre o la cierra: se enciende con una
  /// sesion de la T3 capturando y se apaga en cuanto deja de haberla.
  @override
  void notifyListeners() {
    _sincronizarGps();
    super.notifyListeners();
  }

  void _sincronizarGps() {
    final s = currentSession;
    final api = _api;
    final quiere = s != null && s.isCapturing && s.gpsDelTelefono && api != null;
    if (!quiere) {
      if (_gps != null) {
        _gps!.detener();
        _gps = null;
        _gpsSesion = null;
        avisoGps = null;
      }
      return;
    }
    if (_gpsSesion == s.id) return;
    _gps?.detener();
    final id = s.id;
    _gpsSesion = id;
    _gps = GpsTelefono(
      alFix: (fix) async {
        try {
          await api.postPosicion(id, fix.toJson());
          if (avisoGps != null && avisoGps!.startsWith('No se pudo')) {
            avisoGps = null;
          }
        } catch (e) {
          avisoGps = 'No se pudo enviar la posición: ${_texto(e)}';
        }
        super.notifyListeners();
      },
      alCambiarAviso: (aviso) {
        avisoGps = aviso;
        super.notifyListeners();
      },
    );
    _gps!.iniciar();
  }

  @override
  void dispose() {
    _gps?.detener();
    _ble?.removeListener(_alCambiarBle);
    _ws?.dispose();
    _api?.close();
    super.dispose();
  }
}
