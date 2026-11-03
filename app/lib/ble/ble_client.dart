// ============================================================================
//  ble_client.dart  -  Cliente BLE de control de la sonda (Fase 3)
// ============================================================================
//  Contrato: equipo/CONTRATO-BLE.md v2 (byte `ver` = 0x01).
//
//  La seguridad la da la pila: LE Secure Connections con Passkey Entry
//  (decision I). AQUI NO HAY CRIPTOGRAFIA PROPIA y la app NO guarda ningun
//  secreto: el numero de 6 digitos lo muestra la sonda en su OLED y se teclea
//  en el dialogo del sistema de Android. Las llaves las custodia el sistema
//  operativo, no `shared_preferences` (§5.5, §10.6).
//
//  Depende de `flutter_blue_plus` y de nada mas (§10.1). No importa nada de
//  `api/`: BLE y microservicio son dos caminos independientes, y mezclarlos
//  aqui haria que un fallo de red pareciera un fallo de BLE.
//
//  ---------------------------------------------------------------------------
//  API para quien lo consume (app_state.dart / panel.dart)
//  ---------------------------------------------------------------------------
//  Es un ChangeNotifier: se registra con `provider` igual que AppState y
//  notifica en cada cambio observable. Ademas expone `cambiosEstado`, un
//  Stream de difusion con cada Estado de 6 B que llega de la sonda.
//
//    // gate de RF-7 (§10.5)
//    cliente.listo            -> conectado && enlace seguro && ver == 0x01
//    cliente.motivoGateCerrado-> texto en espanol de por que NO esta listo
//
//    // lo que dice la sonda (§10.8)
//    cliente.ver              -> byte 0 de Estado (0x01)
//    cliente.modo             -> 0..6, null si la sonda emite 0xFF
//    cliente.estadoSonda      -> 0..5, tabla BleEstadoSonda (§8.1)
//    cliente.ultCmd           -> tabla BleUltCmd (§8.2)
//
//    // ordenes
//    await cliente.seleccionar(modo)  -> escribe [0x01, modo] y espera el ACK
//    await cliente.abortar()          -> escribe [0x02, 0x00]
//    await cliente.rejoin()           -> escribe [0x03, 0x00] (gate de clase)
//
//  Todas devuelven un `BleRespuesta` con `ok`, un `mensaje` ya redactado en
//  espanol para ensenarselo al operador, y el codigo ATT crudo si lo hubo.
//  NO lanzan excepciones: el camino de error es un valor de retorno, porque
//  §10.5 obliga a deshacer el `POST /session/start` cuando la escritura falla
//  y eso no debe depender de acordarse de poner un try/catch.
// ============================================================================

import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

// ---------------------------------------------------------------------------
// Constantes del contrato (§10.2)
// ---------------------------------------------------------------------------

/// Servicio `PICARO-CAMPO`. Es el UNICO filtro del escaneo (§3.2): nunca se
/// filtra por nombre, porque el nombre viaja en el scan response.
const String bleServicioUuid = 'c9f42c00-f57d-43be-a6c4-466b08f51a3c';

/// Caracteristica Comando: write con respuesta, exactamente 2 B (§4.2).
const String bleCmdUuid = 'c9f42c03-f57d-43be-a6c4-466b08f51a3c';

/// Caracteristica Estado: read + notify, 6 B (§4.3).
const String bleEstadoUuid = 'c9f42c04-f57d-43be-a6c4-466b08f51a3c';

/// Mayor `modo` que acepta `seleccionar` (§4.2): 0..5 son las seis corridas
/// originales y 6 es VUELO-A (docs/VUELO-ESPEC.md). Un firmware anterior a
/// VUELO rechaza el 6 con ATT 131.
const int bleModoMax = 6;

/// Nombres de los modos de §4.2 sin depender de runs.dart: este fichero no
/// importa nada mas que flutter_blue_plus (§10.1). Por eso se repite aqui la
/// tabla; `test/vuelo_test.dart` comprueba que coincide con `kRuns`.
///
/// Ya NO se calcula como `escenario = m ~/ 2`, `clase = m % 2`: VUELO (6) solo
/// tiene Clase A y rompe los pares.
const List<String> bleNombresModo = [
  'URBANO-A', 'URBANO-C', // 0, 1
  'TERRAZA-A', 'TERRAZA-C', // 2, 3
  'CERRO16-A', 'CERRO16-C', // 4, 5
  'VUELO-A', // 6
];

/// Nombre legible de un `modo` («CERRO16-C», «VUELO-A»), o «modo N» si no
/// esta en la tabla.
String bleNombreModo(int m) =>
    (m >= 0 && m < bleNombresModo.length) ? bleNombresModo[m] : 'modo $m';

/// Version del protocolo que esta app sabe hablar (byte 0 de Estado).
const int bleVerEsperada = 0x01;

/// Nombre anunciado, identico en todas las sondas (§3.4).
const String bleNombre = 'PICARO-CAMPO';

/// Opcodes de Comando (§4.2).
const int _opSeleccionar = 0x01;
const int _opAbortar = 0x02;
const int _opRejoin = 0x03;

/// Errores ATT de aplicacion (§8.3): `0x80 + ult_cmd`. Android los entrega como
/// enteros crudos: 130, 131 y 132. No existe constante con nombre para ellos.
const int bleAttLongitud = 130; // 0x82
const int bleAttParametro = 131; // 0x83
const int bleAttEstado = 132; // 0x84

/// *Insufficient Authentication*, lo genera la pila de la sonda cuando se toca
/// una caracteristica protegida sin enlace seguro (§6.3). Tras haber emparejado
/// significa que el bond se perdio del lado sonda (§10.4).
const int bleAttSinAuth = 5; // 0x05

// ---------------------------------------------------------------------------
// Tablas del contrato
// ---------------------------------------------------------------------------

/// `estado` — byte 2 de la caracteristica Estado (§8.1).
abstract class BleEstadoSonda {
  static const int config = 0x00;
  static const int corriendo = 0x01;
  static const int finalizada = 0x02;
  static const int abortada = 0x03;
  static const int uniendo = 0x04; // RETIRADO (C-Fondo): el firmware no lo emite
  static const int emparejado = 0x05;
  static const int sinEnlace = 0x06; // menú operable, enlace LoRa no adquirido
  static const int esperandoEnlace = 0x07; // corrida agendada, esperando enlace

  /// Texto corto para pintar en pantalla.
  static String etiqueta(int? e) {
    switch (e) {
      case config:
        return 'En configuración';
      case corriendo:
        return 'Corriendo';
      case finalizada:
        return 'Corrida finalizada';
      case abortada:
        return 'Corrida abortada';
      case uniendo:
        return 'Uniéndose (JOIN)';
      case emparejado:
        return 'Modo emparejar';
      case sinEnlace:
        return 'Operable (uniéndose)';
      case esperandoEnlace:
        return 'Esperando enlace';
      case null:
        return '—';
      default:
        return 'Desconocido (0x${e.toRadixString(16).padLeft(2, '0')})';
    }
  }

  /// Estados en los que la sonda NO acepta ningun comando (§5.3). SIN_ENLACE y
  /// ESPERANDO_ENLACE sí aceptan (seleccionar y/o abortar), como CONFIG.
  static bool aceptaComandos(int? e) =>
      e != null && e != uniendo && e != emparejado;
}

/// `ult_cmd` — byte 4 de la caracteristica Estado (§8.2).
abstract class BleUltCmd {
  static const int ok = 0x00;
  static const int sinAuth = 0x01; // reservado, esta version no lo emite
  static const int longitud = 0x02;
  static const int parametro = 0x03;
  static const int estado = 0x04;
  static const int ninguno = 0xFF;

  static String etiqueta(int? v) {
    switch (v) {
      case ok:
        return 'OK';
      case sinAuth:
        return 'Sin autenticar';
      case longitud:
        return 'Longitud inválida';
      case parametro:
        return 'Parámetro inválido';
      case estado:
        return 'No aplicable a este estado';
      case ninguno:
        return 'Ninguno';
      case null:
        return '—';
      default:
        return '0x${v.toRadixString(16).padLeft(2, '0')}';
    }
  }
}

/// Los 6 bytes de la caracteristica Estado, ya interpretados (§4.3).
@immutable
class BleSondaEstado {
  /// Byte 0. Version del protocolo; se comprueba antes que nada.
  final int ver;

  /// Byte 1. `0x00`..`0x06` (6 = VUELO-A), o **null** si la sonda emitio `0xFF` (reservado:
  /// esta version del firmware no lo emite, pero hay que tolerarlo).
  final int? modo;

  /// Byte 2. Tabla [BleEstadoSonda].
  final int estado;

  /// Byte 4. Tabla [BleUltCmd].
  final int ultCmd;

  const BleSondaEstado({
    required this.ver,
    required this.modo,
    required this.estado,
    required this.ultCmd,
  });

  /// Devuelve null si el paquete no mide 6 B: mejor ignorarlo que interpretar
  /// bytes que no estan (una notificacion mayor que el MTU se trunca en
  /// silencio, §4.1).
  static BleSondaEstado? desdeBytes(List<int> b) {
    if (b.length < 6) return null;
    return BleSondaEstado(
      ver: b[0],
      modo: b[1] == 0xFF ? null : b[1],
      estado: b[2],
      ultCmd: b[4],
    );
  }

  bool get versionCompatible => ver == bleVerEsperada;

  @override
  bool operator ==(Object other) =>
      other is BleSondaEstado &&
      other.ver == ver &&
      other.modo == modo &&
      other.estado == estado &&
      other.ultCmd == ultCmd;

  @override
  int get hashCode => Object.hash(ver, modo, estado, ultCmd);

  @override
  String toString() =>
      'BleSondaEstado(ver:$ver modo:$modo estado:$estado ultCmd:$ultCmd)';
}

/// Una sonda vista en el escaneo.
@immutable
class BleSondaDescubierta {
  /// MAC publica, p. ej. `48:CA:43:5C:1B:2A` (la direccion es contractualmente
  /// publica, §3.3, porque el bonding se ata a ella).
  final String direccion;
  final String nombre;
  final int rssi;

  const BleSondaDescubierta({
    required this.direccion,
    required this.nombre,
    required this.rssi,
  });

  /// `PICARO-CAMPO · 1B:2A` (§3.4): el nombre es constante en todas las
  /// unidades, asi que quien las distingue es la app con los dos ultimos
  /// bytes de la MAC.
  String get etiqueta {
    final partes = direccion.split(':');
    final sufijo =
        partes.length >= 2 ? partes.sublist(partes.length - 2).join(':') : direccion;
    return '${nombre.isEmpty ? bleNombre : nombre} · $sufijo';
  }
}

/// Fase del enlace, pensada para pintarla tal cual en la pantalla de
/// dispositivo. No confundir con el estado de la SONDA ([BleEstadoSonda]):
/// son dos maquinas ortogonales (§5.1).
enum BleFase {
  /// Sin objetivo: nunca se ha pedido conectar, o se desconecto a mano.
  inactivo,
  escaneando,
  conectando,

  /// `createBond()` en curso: hay que teclear el numero del OLED en el
  /// diálogo del sistema.
  emparejando,

  /// Descubriendo servicios, suscribiendo y leyendo Estado.
  preparando,

  /// Enlace seguro y `ver == 0x01`. Es la unica fase en la que [BleClient.listo].
  listo,

  /// Enlace caido, esperando el proximo intento del backoff (§10.6).
  reconectando,

  /// `ver != 0x01`: firmware incompatible. No se envia ningun comando (§10.4).
  incompatible,

  /// La sonda esta en EMPAREJADO: la app se aparta y deja de reconectar
  /// (§10.7). Solo se sale de aqui con [BleClient.reconectar].
  apartada,

  /// Fallo que no merece reintento automatico (Bluetooth apagado, sin sonda).
  error,
}

/// Resultado de escribir en la caracteristica Comando.
enum BleCmdResultado {
  /// Escrito y aceptado por la sonda. Cuando se pidio confirmacion (lo normal
  /// en [BleClient.seleccionar]), ademas llegó la notificacion esperada.
  ok,

  /// Escrito y aceptado, pero la notificacion esperada no llego en el plazo.
  /// **No es motivo para deshacer el `POST /session/start`**: el comando SI se
  /// aceptó. Se re-leyó Estado y [BleRespuesta.estado] trae lo que hay de
  /// verdad en la sonda (§10.5, paso 5).
  sinConfirmacion,

  /// No hay enlace listo. La escritura ni se intentó.
  sinEnlace,

  /// ATT 130: longitud != 2. **Bug de la app**, hay que registrarlo (§10.4).
  rechazoLongitud,

  /// ATT 131: `modo` fuera de rango. **Bug de la app** (§10.4).
  rechazoParametro,

  /// ATT 132: la sonda esta en un estado que no admite el comando (§5.3).
  /// No es un bug: es el error que vera el operador.
  rechazoEstado,

  /// ATT 5: hay que volver a emparejar (el bond se perdio del lado sonda).
  sinBond,

  /// Cualquier otro fallo de transporte.
  fallo,
}

/// Lo que devuelven [BleClient.seleccionar] y [BleClient.abortar].
@immutable
class BleRespuesta {
  final BleCmdResultado resultado;

  /// Texto en espanol, ya redactado para ensenarselo al operador.
  final String mensaje;

  /// Codigo ATT crudo tal cual lo entrega Android, si lo hubo.
  final int? codigoAtt;

  /// Estado de la sonda conocido justo despues de la operacion.
  final BleSondaEstado? estado;

  const BleRespuesta(this.resultado, this.mensaje, {this.codigoAtt, this.estado});

  /// true si el comando se aceptó (confirmado o no). El unico caso que obliga
  /// a deshacer el paso 1 de §10.5 es `!aceptado`.
  bool get aceptado =>
      resultado == BleCmdResultado.ok ||
      resultado == BleCmdResultado.sinConfirmacion;

  /// true solo si ademas la sonda confirmó por notificacion.
  bool get ok => resultado == BleCmdResultado.ok;

  @override
  String toString() => 'BleRespuesta($resultado, "$mensaje", att:$codigoAtt)';
}

// ---------------------------------------------------------------------------
// El cliente
// ---------------------------------------------------------------------------

/// Cliente BLE de la sonda. Uno solo por app (la sonda acepta **una** conexion,
/// §5.4). Registrar con `provider` y llamar a [dispose] al cerrar.
class BleClient extends ChangeNotifier {
  BleClient();

  // --- backoff de reconexion (§10.6): 1 → 2 → 4 → 8 → 15 → 15 … -----------
  static const List<int> _backoff = [1, 2, 4, 8, 15];

  // Plazos del orden de operaciones (§10.3).
  static const Duration _tEscaneo = Duration(seconds: 10);
  static const Duration _tConexion = Duration(seconds: 15);
  static const int _tBondSegundos = 60;
  static const Duration _tConfirmacion = Duration(seconds: 2);

  // --- estado observable ---------------------------------------------------
  BleFase _fase = BleFase.inactivo;
  bool _escaneando = false;
  final List<BleSondaDescubierta> _encontradas = [];
  bool _conectado = false;
  bool _seguro = false;
  bool _emparejando = false;
  String? _direccion;
  String? _nombre;
  BleSondaEstado? _estado;
  String? _aviso;
  int _intento = 0;

  // --- interno -------------------------------------------------------------
  BluetoothDevice? _dev;
  BluetoothCharacteristic? _cmd;
  BluetoothCharacteristic? _est;
  StreamSubscription<List<ScanResult>>? _subEscaneo;
  StreamSubscription<BluetoothConnectionState>? _subConexion;
  StreamSubscription<List<int>>? _subEstado;
  Timer? _timerReconexion;
  final StreamController<BleSondaEstado> _ctrlEstado =
      StreamController<BleSondaEstado>.broadcast();
  bool _dispuesto = false;
  bool _abriendo = false;

  /// La reconexion automatica esta suspendida hasta que el usuario la pida
  /// (fase [BleFase.apartada] o desconexion manual).
  bool _pausada = true;

  // --- lo que ve quien consume --------------------------------------------

  /// Fase del enlace, para pintar. Ver [BleFase].
  BleFase get fase => _fase;

  bool get escaneando => _escaneando;

  /// Sondas vistas en el ultimo escaneo, ordenadas por RSSI descendente.
  List<BleSondaDescubierta> get encontradas => List.unmodifiable(_encontradas);

  bool get conectado => _conectado;

  /// Enlace cifrado y autenticado. Se deriva de que las operaciones sobre las
  /// caracteristicas protegidas funcionen, que con LE Secure Connections
  /// equivale a «el bond esta hecho y el enlace cifrado». La app no lee
  /// `authenticated` directamente: **quien lo verifica es la sonda** (§5.1,
  /// §10.5), y la sonda no sale de EMPAREJADO sin el.
  bool get seguro => _seguro;

  /// `createBond()` en curso: la pantalla debe pedir que se teclee el numero.
  bool get emparejando => _emparejando;

  /// MAC de la sonda con la que se trabaja, p. ej. `48:CA:43:5C:1B:2A`.
  String? get direccion => _direccion;

  /// Nombre que anuncia la sonda: `PICARO-CAMPO` (T-Beam) o `PICARO-LORA32`.
  String? get nombre => _nombre;

  /// Sonda para el microservicio (D-65): `lora32` si la sonda se anuncia como
  /// PICARO-LORA32, `tbeam` en cualquier otro caso.
  String get sonda =>
      (_nombre ?? '').toUpperCase().contains('LORA32') ? 'lora32' : 'tbeam';

  /// Ultimo Estado leido o notificado, entero.
  BleSondaEstado? get estado => _estado;

  int? get ver => _estado?.ver;
  int? get modo => _estado?.modo;
  int? get estadoSonda => _estado?.estado;
  int? get ultCmd => _estado?.ultCmd;

  /// Ultimo aviso legible (fallo de emparejado, firmware incompatible…).
  String? get aviso => _aviso;

  /// La reconexion automatica esta suspendida y solo la reanuda [reconectar].
  bool get reconexionPausada => _pausada;

  /// Numero de intentos de reconexion encadenados sin exito.
  int get intentoReconexion => _intento;

  /// **El gate de RF-7** (§10.5). Con esto se habilitan el selector de corrida
  /// y el boton Arrancar. *Abortar* NO debe mirarlo (decision G).
  bool get listo => _conectado && _seguro && ver == bleVerEsperada;

  /// Por que el gate esta cerrado, en espanol. null si [listo]. Un control
  /// deshabilitado sin explicacion, en campo, se interpreta como que la app
  /// esta rota (§10.5).
  String? get motivoGateCerrado {
    if (listo) return null;
    switch (_fase) {
      case BleFase.incompatible:
        return 'Firmware BLE incompatible (v$ver, se esperaba v$bleVerEsperada).';
      case BleFase.apartada:
        return 'La sonda está en modo emparejar. Pulsa corto en la sonda y '
            'reconecta desde la pantalla de dispositivo.';
      case BleFase.emparejando:
        return 'Emparejando: teclea en el móvil el número que ves en la sonda.';
      case BleFase.conectando:
      case BleFase.preparando:
        return 'Conectando con la sonda…';
      case BleFase.reconectando:
        return 'Enlace BLE caído; reintentando.';
      case BleFase.escaneando:
        return 'Buscando la sonda…';
      default:
        return 'Conecta la sonda por Bluetooth para elegir corrida.';
    }
  }

  /// Cada Estado de 6 B que llega (leido o notificado). Sirve para la
  /// comprobacion de §10.8: si `estadoSonda == CORRIENDO` y el `modo` no
  /// coincide con el de la sesion abierta, avisar en rojo en el acto.
  Stream<BleSondaEstado> get cambiosEstado => _ctrlEstado.stream;

  // =========================================================================
  // Escaneo (§10.3, pasos 1-3)
  // =========================================================================

  /// Escanea filtrando **solo** por el UUID de servicio, nunca por nombre
  /// (§3.2). Termina sola a los 10 s. No reintenta en bucle: gasta bateria y
  /// el usuario no ve por que (§10.4).
  Future<void> escanear({Duration timeout = _tEscaneo}) async {
    if (_escaneando) return;

    final problema = await _comprobarAdaptador();
    if (problema != null) {
      _aviso = problema;
      _fase = BleFase.error;
      notifyListeners();
      return;
    }

    _encontradas.clear();
    _escaneando = true;
    _aviso = null;
    if (_fase == BleFase.inactivo || _fase == BleFase.error) {
      _fase = BleFase.escaneando;
    }
    notifyListeners();

    await _subEscaneo?.cancel();
    _subEscaneo = FlutterBluePlus.onScanResults.listen(
      (resultados) {
        _encontradas
          ..clear()
          ..addAll(resultados.map((r) => BleSondaDescubierta(
                direccion: r.device.remoteId.str,
                nombre: r.advertisementData.advName.isNotEmpty
                    ? r.advertisementData.advName
                    : r.device.platformName,
                rssi: r.rssi,
              )));
        _encontradas.sort((a, b) => b.rssi.compareTo(a.rssi));
        notifyListeners();
      },
      onError: (Object e) => _log('escaneo: $e'),
    );

    try {
      await FlutterBluePlus.startScan(
        withServices: [Guid(bleServicioUuid)],
        timeout: timeout,
        // El manifiesto declara BLUETOOTH_SCAN con `neverForLocation`: no se
        // pide ACCESS_FINE_LOCATION en Android 12+.
        androidUsesFineLocation: false,
      );
      // OJO: startScan vuelve en cuanto la pila ARRANCA el escaneo, no cuando
      // expira el `timeout`. Hay que esperar a que se dé por terminado, o se
      // cancelaria la suscripcion de resultados en el acto y la lista saldria
      // siempre vacia.
      await FlutterBluePlus.isScanning.where((s) => s == false).first;
    } catch (e) {
      _aviso = 'No se pudo escanear: ${_texto(e)}';
      _fase = BleFase.error;
    } finally {
      await _subEscaneo?.cancel();
      _subEscaneo = null;
      _escaneando = false;
      if (_fase == BleFase.escaneando) {
        _fase = _encontradas.isEmpty ? BleFase.error : BleFase.inactivo;
        if (_encontradas.isEmpty) {
          _aviso = 'No se encuentra la sonda. Comprueba que está encendida y '
              'que no hay otro móvil conectado a ella.';
        }
      }
      notifyListeners();
    }
  }

  /// Corta el escaneo antes de tiempo.
  Future<void> pararEscaneo() async {
    if (!_escaneando) return;
    try {
      await FlutterBluePlus.stopScan();
    } catch (_) {}
  }

  // =========================================================================
  // Conexion (§10.3, pasos 4-11)
  // =========================================================================

  /// Conecta con la sonda de [direccion] y deja el enlace en regimen. A partir
  /// de aqui la reconexion automatica queda activa (§10.6) hasta que se llame
  /// a [desconectar] o hasta que la sonda entre en EMPAREJADO (§10.7).
  ///
  /// Devuelve true si el enlace quedó [listo].
  Future<bool> conectar(String direccion) async {
    await pararEscaneo();
    if (direccion != _direccion) _nombre = null;
    _direccion = direccion;
    // El nombre sale del escaneo; si no esta (reconexion), se completa con el
    // que recuerda el sistema al abrir el enlace.
    for (final s in _encontradas) {
      if (s.direccion == direccion && s.nombre.isNotEmpty) _nombre = s.nombre;
    }
    _pausada = false;
    _intento = 0;
    return _abrirEnlace();
  }

  /// Reanuda la reconexion tras [desconectar] o tras haberse apartado por
  /// EMPAREJADO (§10.7). Es el «botón explícito de reconectar» que exige el
  /// contrato: la app no vuelve sola de ese estado.
  Future<bool> reconectar() async {
    final d = _direccion;
    if (d == null) return false;
    return conectar(d);
  }

  /// §10.7, **regla obligatoria**: se desconecta y **deja de reconectar** hasta
  /// que el usuario pulse [reconectar]. Es lo que hay que llamar en cuanto se
  /// vea `estadoSonda == BleEstadoSonda.emparejado`.
  ///
  /// No es cortesía: con una sola conexión admitida, un móvil ya emparejado
  /// que se reconecta solo ocupa la única ranura y **bloquea el emparejamiento
  /// del móvil nuevo** (§5.4). El cliente ya lo hace por su cuenta al ver ese
  /// estado; llamarla otra vez desde fuera es inofensivo.
  Future<void> desconectarYNoReconectar() => _apartarse();

  /// Desconexion explicita. Obligatoria al salir de la pantalla de dispositivo
  /// y al cerrar la app: Android a veces mantiene la conexion GATT tras cerrar
  /// la app, y entonces la sonda queda invisible para los demas (§5.4, §10.8).
  Future<void> desconectar() async {
    _pausada = true;
    _timerReconexion?.cancel();
    _timerReconexion = null;
    await _cerrarEnlace();
    _fase = BleFase.inactivo;
    notifyListeners();
  }

  /// Orden de operaciones de §10.3. Cada paso esta numerado igual que alli.
  Future<bool> _abrirEnlace() async {
    if (_dispuesto || _abriendo) return false;
    final direccion = _direccion;
    if (direccion == null) return false;

    _abriendo = true;
    try {
      // (1) Bluetooth encendido y permisos.
      final problema = await _comprobarAdaptador();
      if (problema != null) {
        _aviso = problema;
        _fase = BleFase.error;
        notifyListeners();
        return false;
      }

      await _cerrarEnlace(silencioso: true);

      _fase = BleFase.conectando;
      _aviso = null;
      notifyListeners();

      final dev = BluetoothDevice.fromId(direccion);
      _dev = dev;
      if ((_nombre ?? '').isEmpty && dev.platformName.isNotEmpty) {
        _nombre = dev.platformName;
      }

      // (4) connect. `mtu: null` porque el MTU se pide en el paso 6, DESPUES
      //     del bond: en algunos telefonos una peticion de MTU en pleno
      //     emparejamiento se pierde (§10.3).
      try {
        await dev.connect(timeout: _tConexion, autoConnect: false, mtu: null);
      } catch (e) {
        _aviso = 'No se pudo conectar con la sonda: ${_texto(e)}';
        return _fallo(reintentar: true);
      }

      _conectado = true;
      notifyListeners();

      // Vigilar caidas desde ya.
      await _subConexion?.cancel();
      _subConexion = dev.connectionState.listen((s) {
        if (s == BluetoothConnectionState.disconnected) _alDesconectar();
      });

      // (5) Bond explicito. Con el implicito (dejar que falle la lectura y que
      //     Android empareje solo) habria que reintentar la operacion, y
      //     Android no siempre la reejecuta: el orden deja de ser determinista.
      if (!await _asegurarBond(dev)) return false;

      // (6) MTU: BEST EFFORT. Todo el protocolo cabe con el MTU por defecto
      //     (§4.1); un requestMtu fallido NO es un error del enlace.
      if (!kIsWeb && Platform.isAndroid) {
        try {
          await dev.requestMtu(247);
        } catch (e) {
          _log('requestMtu (ignorado): ${_texto(e)}');
        }
      }

      _fase = BleFase.preparando;
      notifyListeners();

      // (7) Descubrir servicios y localizar las dos caracteristicas.
      if (!await _descubrir(dev)) return false;

      // (8) Suscribirse ANTES de la primera lectura, para no perder ninguna
      //     notificacion que llegue entre medias (§10.3).
      try {
        await _est!.setNotifyValue(true);
        await _subEstado?.cancel();
        _subEstado = _est!.onValueReceived.listen(_alLlegarEstado);
        dev.cancelWhenDisconnected(_subEstado!);
      } catch (e) {
        _aviso = 'No se pudo suscribir al estado de la sonda: ${_texto(e)}';
        return _fallo(reintentar: true);
      }

      // (9) Leer Estado y comprobar el byte de version antes de nada mas.
      final BleSondaEstado? est;
      try {
        est = BleSondaEstado.desdeBytes(await _est!.read());
      } catch (e) {
        if (_codigoAtt(e) == bleAttSinAuth) {
          _aviso = 'Hay que volver a emparejar: la sonda ya no reconoce este '
              'móvil. Pon la sonda en modo emparejar (pulsación larga) e '
              'inténtalo otra vez.';
          return _fallo(reintentar: false);
        }
        _aviso = 'No se pudo leer el estado de la sonda: ${_texto(e)}';
        return _fallo(reintentar: true);
      }

      if (est == null) {
        _aviso = 'La sonda devolvió un Estado de longitud inesperada.';
        return _fallo(reintentar: true);
      }

      // El enlace funciona sobre caracteristicas protegidas => es seguro.
      _seguro = true;
      _aplicarEstado(est);

      if (!est.versionCompatible) {
        _aviso = 'Firmware BLE incompatible (v${est.ver}, se esperaba '
            'v$bleVerEsperada). No se enviará ningún comando.';
        _fase = BleFase.incompatible;
        _pausada = true;
        await _cerrarEnlace(silencioso: true);
        notifyListeners();
        return false;
      }

      // (10) Si la sonda esta en EMPAREJADO, apartarse (§10.7). Con
      //      MAX_CONNECTIONS = 1 este movil ocuparia la unica ranura y
      //      bloquearia el emparejamiento del telefono nuevo.
      if (est.estado == BleEstadoSonda.emparejado) {
        await _apartarse();
        return false;
      }

      // (11) Regimen.
      _intento = 0;
      _fase = BleFase.listo;
      notifyListeners();
      return true;
    } finally {
      _abriendo = false;
    }
  }

  Future<bool> _asegurarBond(BluetoothDevice dev) async {
    if (kIsWeb || !Platform.isAndroid) return true; // solo Android tiene bond

    BluetoothBondState actual;
    try {
      actual = await dev.bondState.first;
    } catch (e) {
      _log('bondState: ${_texto(e)}');
      return true; // sin dato: se sigue, el paso 9 dira la verdad
    }
    if (actual == BluetoothBondState.bonded) return true;

    _emparejando = true;
    _fase = BleFase.emparejando;
    _aviso = 'Teclea en el móvil el número que ves en la pantalla de la sonda.';
    notifyListeners();

    try {
      await dev.createBond(timeout: _tBondSegundos);
      return true;
    } catch (e) {
      // Las dos causas se parecen desde la app: ventana de emparejamiento
      // cerrada (§6.6, la sonda corta la conexion) y passkey mal tecleado. El
      // mensaje menciona las dos; el OLED de la sonda es el que desambigua.
      _aviso = 'No se pudo emparejar. Comprueba que la sonda está en modo '
          'emparejar (pulsación larga en el menú) y que tecleaste bien el '
          'número de 6 dígitos que muestra su pantalla.';
      return _fallo(reintentar: false);
    } finally {
      _emparejando = false;
    }
  }

  Future<bool> _descubrir(BluetoothDevice dev) async {
    try {
      final servicios = await dev.discoverServices();
      final svc = _buscar(servicios, bleServicioUuid);
      if (svc == null) {
        _aviso = 'Este dispositivo no expone el servicio PICARO-CAMPO.';
        return _fallo(reintentar: false);
      }
      _cmd = _buscarCar(svc, bleCmdUuid);
      _est = _buscarCar(svc, bleEstadoUuid);
      if (_cmd == null || _est == null) {
        _aviso = 'Faltan características en el servicio PICARO-CAMPO: '
            'el firmware no cumple el contrato.';
        return _fallo(reintentar: false);
      }
      return true;
    } catch (e) {
      _aviso = 'No se pudieron descubrir los servicios: ${_texto(e)}';
      return _fallo(reintentar: true);
    }
  }

  static BluetoothService? _buscar(List<BluetoothService> ss, String uuid) {
    final g = Guid(uuid);
    for (final s in ss) {
      if (s.uuid == g) return s;
    }
    return null;
  }

  static BluetoothCharacteristic? _buscarCar(BluetoothService s, String uuid) {
    final g = Guid(uuid);
    for (final c in s.characteristics) {
      if (c.uuid == g) return c;
    }
    return null;
  }

  // =========================================================================
  // Comandos (§4.2)
  // =========================================================================

  /// `seleccionar(modo)` — escribe `[0x01, modo]`. **Seleccionar es tambien
  /// arrancar** (RF-4): equivale a la doble pulsacion del boton.
  ///
  /// Con [esperarConfirmacion] (por defecto) espera la notificacion de Estado
  /// con `estado == CORRIENDO` y `modo == el pedido`, 2 s (§10.5 paso 5). Si no
  /// llega, re-lee Estado y devuelve [BleCmdResultado.sinConfirmacion] con lo
  /// que hay realmente en la sonda — que **no** es motivo para deshacer la
  /// sesion del servidor.
  Future<BleRespuesta> seleccionar(
    int modo, {
    bool esperarConfirmacion = true,
    Duration timeoutConfirmacion = _tConfirmacion,
  }) async {
    if (modo < 0 || modo > bleModoMax) {
      // Se corta aqui: mandarlo daria ATT 131 y seria un bug de la app.
      return const BleRespuesta(BleCmdResultado.rechazoParametro,
          'Modo fuera de rango (0..$bleModoMax).');
    }

    final r = await _escribir([_opSeleccionar, modo]);
    if (r.resultado == BleCmdResultado.rechazoParametro && modo == 6) {
      // Con 0..5 el ATT 131 es un bug de la app; con 6 lo normal es un
      // firmware anterior a VUELO. Se dice asi para que el operador sepa que
      // lo que hay que actualizar es la sonda, no la app.
      return BleRespuesta(
        BleCmdResultado.rechazoParametro,
        'El firmware de la sonda no conoce la corrida VUELO (modo 6): '
        'actualiza el firmware.',
        codigoAtt: r.codigoAtt,
        estado: r.estado,
      );
    }
    if (!r.aceptado || !esperarConfirmacion) return r;

    // C-Fondo: sin enlace LoRa la sonda no arranca en el acto -- pasa a
    // ESPERANDO_ENLACE y arranca sola en cuanto une. Los DOS estados cuentan
    // como confirmacion de que el comando surtio efecto; no es un timeout.
    final conf = await _esperarEstado(
      (e) =>
          e.modo == modo &&
          (e.estado == BleEstadoSonda.corriendo ||
              e.estado == BleEstadoSonda.esperandoEnlace),
      timeoutConfirmacion,
    );
    if (conf != null) {
      final esperando = conf.estado == BleEstadoSonda.esperandoEnlace;
      return BleRespuesta(
        BleCmdResultado.ok,
        esperando
            ? 'La sonda espera enlace: arrancará en cuanto una a la red.'
            : 'Corrida en marcha.',
        estado: conf,
      );
    }

    final real = await leerEstado();
    return BleRespuesta(
      BleCmdResultado.sinConfirmacion,
      'La sonda aceptó la orden pero no confirmó a tiempo. Ahora mismo está: '
      '${BleEstadoSonda.etiqueta(real?.estado)}.',
      estado: real,
    );
  }

  /// `abortar` — escribe `[0x02, 0x00]`. El segundo byte se ignora pero **debe
  /// estar presente** (§4.2). En CONFIG y ABORTADA es un no-op que devuelve OK,
  /// no un error: «abortar» significa «quiero que estés en configuración», y si
  /// ya lo estás, lo pedido se cumplió (§5.3).
  ///
  /// Quien llama **no debe** condicionar el `POST /session/{id}/abort` al
  /// resultado: abortar del lado servidor está SIEMPRE disponible (decision G,
  /// §10.5).
  Future<BleRespuesta> abortar() => _escribir([_opAbortar, 0x00]);

  /// `re-join` — escribe `[0x03, 0x00]` (gate de clase, D-60). El segundo byte
  /// se ignora pero debe estar presente, como en `abortar`.
  ///
  /// Solo es válido con la sonda **en menú**: CONFIG o SIN_ENLACE (§5.3). Al
  /// aceptarlo, la sonda publica SIN_ENLACE (0x06) de inmediato y CONFIG (0x00)
  /// al completar el join nuevo. Aquí NO se espera esa secuencia: el join en el
  /// cerro puede tardar minutos, y esa espera —acotada y cancelable— es de
  /// quien orquesta el flujo ([FlujoRejoin]), no del transporte.
  ///
  /// Un firmware anterior al op 0x03 rechaza la escritura con ATT 131 (0x83,
  /// «parámetro inválido»). Con `seleccionar`/`abortar` ese código es un bug de
  /// la app; aquí significa **firmware sin re-join**, así que se reescribe el
  /// mensaje para que quien llama pueda degradar al respaldo manual
  /// (apagar/encender la sonda).
  Future<BleRespuesta> rejoin() async {
    final r = await _escribir([_opRejoin, 0x00]);
    if (r.resultado == BleCmdResultado.rechazoParametro) {
      return BleRespuesta(
        BleCmdResultado.rechazoParametro,
        'El firmware de la sonda no conoce la orden de re-join.',
        codigoAtt: r.codigoAtt,
        estado: r.estado,
      );
    }
    return r;
  }

  Future<BleRespuesta> _escribir(List<int> bytes) async {
    final c = _cmd;
    if (!listo || c == null) {
      return BleRespuesta(
          BleCmdResultado.sinEnlace,
          motivoGateCerrado ??
              'Sin enlace BLE con la sonda: no se envió el comando.');
    }
    try {
      // Write WITH response siempre: sin respuesta no se distingue «lo
      // escribí» de «lo aceptó» (§4.1).
      await c.write(bytes, withoutResponse: false);
      return BleRespuesta(BleCmdResultado.ok, 'Comando aceptado.',
          estado: _estado);
    } catch (e) {
      return _interpretarErrorEscritura(e);
    }
  }

  /// Mapea los codigos ATT de §8.3 a mensajes. Android los entrega como enteros
  /// crudos (130, 131, 132): no existe una constante con nombre para ellos.
  BleRespuesta _interpretarErrorEscritura(Object e) {
    final att = _codigoAtt(e);
    switch (att) {
      case bleAttLongitud:
        _log('BUG: escritura de longitud != 2 (ATT 130)');
        return const BleRespuesta(BleCmdResultado.rechazoLongitud,
            'Error interno de la app: longitud de comando inválida.',
            codigoAtt: bleAttLongitud);

      case bleAttParametro:
        _log('BUG: modo fuera de rango (ATT 131)');
        return const BleRespuesta(BleCmdResultado.rechazoParametro,
            'Error interno de la app: parámetro de comando inválido.',
            codigoAtt: bleAttParametro);

      case bleAttEstado:
        // No es un bug: la sonda esta en un estado que no lo admite (§5.3).
        // Se re-lee Estado para poder decir DONDE esta.
        return BleRespuesta(
          BleCmdResultado.rechazoEstado,
          _mensajeRechazoEstado(_estado),
          codigoAtt: bleAttEstado,
          estado: _estado,
        );

      case bleAttSinAuth:
        _seguro = false;
        _aviso = 'Hay que volver a emparejar la sonda.';
        notifyListeners();
        return const BleRespuesta(
            BleCmdResultado.sinBond,
            'La sonda ya no reconoce este móvil: hay que volver a emparejar. '
            'Pon la sonda en modo emparejar (pulsación larga en el menú).',
            codigoAtt: bleAttSinAuth);

      default:
        return BleRespuesta(BleCmdResultado.fallo,
            'No se pudo enviar el comando: ${_texto(e)}',
            codigoAtt: att);
    }
  }

  String _mensajeRechazoEstado(BleSondaEstado? e) {
    switch (e?.estado) {
      case BleEstadoSonda.corriendo:
        final n = e?.modo;
        final cual = n == null ? 'una corrida' : 'la corrida ${bleNombreModo(n)}';
        return 'La sonda está corriendo $cual: abórtala primero.';
      case BleEstadoSonda.esperandoEnlace:
        return 'La sonda ya tiene una corrida esperando enlace: abórtala primero.';
      case BleEstadoSonda.uniendo:
        return 'La sonda está haciendo el JOIN: espera a que termine.';
      case BleEstadoSonda.emparejado:
        return 'La sonda está en modo emparejar: sal con una pulsación corta.';
      default:
        return 'La sonda no admite ese comando en su estado actual '
            '(${BleEstadoSonda.etiqueta(e?.estado)}).';
    }
  }

  /// Re-lee la caracteristica Estado. Es lo que hay que hacer al reconectar y
  /// tras un rechazo: **la verdad está en la sonda** (§10.6).
  Future<BleSondaEstado?> leerEstado() async {
    final c = _est;
    if (c == null || !_conectado) return _estado;
    try {
      final e = BleSondaEstado.desdeBytes(await c.read());
      if (e != null) _aplicarEstado(e);
      return e ?? _estado;
    } catch (e) {
      _log('releerEstado: ${_texto(e)}');
      return _estado;
    }
  }

  // =========================================================================
  // Estado entrante
  // =========================================================================

  void _alLlegarEstado(List<int> bytes) {
    final e = BleSondaEstado.desdeBytes(bytes);
    if (e == null) {
      _log('Estado de ${bytes.length} B, ignorado');
      return;
    }
    _aplicarEstado(e);

    // §10.7: si la sonda entra en EMPAREJADO estando nosotros conectados, hay
    // que soltar la ranura para que el telefono nuevo pueda emparejarse.
    if (e.estado == BleEstadoSonda.emparejado && _fase != BleFase.apartada) {
      unawaited(_apartarse());
    }
  }

  void _aplicarEstado(BleSondaEstado e) {
    _estado = e;
    if (!_ctrlEstado.isClosed) _ctrlEstado.add(e);
    notifyListeners();
  }

  Future<BleSondaEstado?> _esperarEstado(
      bool Function(BleSondaEstado) cuando, Duration timeout) {
    final actual = _estado;
    if (actual != null && cuando(actual)) return Future.value(actual);

    final c = Completer<BleSondaEstado?>();
    late final StreamSubscription<BleSondaEstado> sub;
    final t = Timer(timeout, () {
      if (!c.isCompleted) {
        c.complete(null);
        sub.cancel();
      }
    });
    sub = _ctrlEstado.stream.listen((e) {
      if (cuando(e) && !c.isCompleted) {
        t.cancel();
        c.complete(e);
        sub.cancel();
      }
    });
    return c.future;
  }

  // =========================================================================
  // Caidas y reconexion (§10.6)
  // =========================================================================

  void _alDesconectar() {
    if (_dispuesto) return;
    final estabaConectado = _conectado;
    _conectado = false;
    _seguro = false;
    _cmd = null;
    _est = null;
    if (!estabaConectado && _fase == BleFase.inactivo) return;

    if (_pausada) {
      if (_fase != BleFase.apartada && _fase != BleFase.incompatible) {
        _fase = BleFase.inactivo;
      }
      notifyListeners();
      return;
    }

    _fase = BleFase.reconectando;
    notifyListeners();
    _programarReconexion();
  }

  void _programarReconexion() {
    if (_dispuesto || _pausada || _timerReconexion != null) return;
    final idx = _intento.clamp(0, _backoff.length - 1);
    final espera = Duration(seconds: _backoff[idx]);
    if (_intento < _backoff.length - 1) _intento++;
    _timerReconexion = Timer(espera, () async {
      _timerReconexion = null;
      if (_dispuesto || _pausada) return;
      // Regla dura: al reconectar NO se reenvia ningun comando pendiente.
      // Nunca. Mientras el BLE estaba caido, la corrida siguio corriendo
      // (RNF-2); el trabajo de la app al reconectar es LEER la sonda, no
      // imponerse (§10.6).
      final ok = await _abrirEnlace();
      if (!ok && !_pausada && _fase != BleFase.incompatible) {
        _fase = BleFase.reconectando;
        notifyListeners();
        _programarReconexion();
      }
    });
  }

  /// Devuelve false siempre; centraliza el «esto falló» para que cada camino
  /// de error sea una linea.
  ///
  /// Suelta SIEMPRE la conexion: la sonda solo admite un central (§5.4), asi
  /// que un intento fallido a medias —conectado pero sin bond, o sin haber
  /// encontrado el servicio— le ocuparia la unica ranura y dejaria a los demas
  /// sin poder ni verla.
  Future<bool> _fallo({required bool reintentar}) async {
    await _cerrarEnlace(silencioso: true);
    _fase = reintentar ? BleFase.reconectando : BleFase.error;
    if (!reintentar) _pausada = true;
    notifyListeners();
    if (reintentar) _programarReconexion();
    return false;
  }

  /// §10.7: la sonda esta en EMPAREJADO. Nos desconectamos y dejamos de
  /// reconectar hasta que el usuario pulse «reconectar».
  Future<void> _apartarse() async {
    _pausada = true;
    _timerReconexion?.cancel();
    _timerReconexion = null;
    _aviso = 'La sonda está en modo emparejar. Este móvil se ha desconectado '
        'para dejarle sitio al que estás emparejando.';
    await _cerrarEnlace(silencioso: true);
    _fase = BleFase.apartada;
    notifyListeners();
  }

  Future<void> _cerrarEnlace({bool silencioso = false}) async {
    await _subEstado?.cancel();
    _subEstado = null;
    await _subConexion?.cancel();
    _subConexion = null;
    final dev = _dev;
    _cmd = null;
    _est = null;
    if (dev != null) {
      try {
        await dev.disconnect();
      } catch (e) {
        _log('disconnect: ${_texto(e)}');
      }
    }
    _dev = null;
    _conectado = false;
    _seguro = false;
    _emparejando = false;
    if (!silencioso) notifyListeners();
  }

  // =========================================================================
  // Utilidades
  // =========================================================================

  /// null si todo bien; si no, el motivo en espanol.
  Future<String?> _comprobarAdaptador() async {
    try {
      if (!await FlutterBluePlus.isSupported) {
        return 'Este dispositivo no tiene Bluetooth LE.';
      }
      final st = await FlutterBluePlus.adapterState.first;
      if (st == BluetoothAdapterState.unauthorized) {
        return 'Falta el permiso de Bluetooth. Concédelo en los ajustes de la '
            'aplicación.';
      }
      if (st != BluetoothAdapterState.on) {
        return 'El Bluetooth está apagado: enciéndelo para hablar con la sonda.';
      }
      return null;
    } catch (e) {
      return 'No se pudo consultar el Bluetooth: ${_texto(e)}';
    }
  }

  /// Codigo ATT/GATT crudo de una excepcion de flutter_blue_plus, o null.
  static int? _codigoAtt(Object e) =>
      e is FlutterBluePlusException && e.platform != ErrorPlatform.fbp
          ? e.code
          : null;

  static String _texto(Object e) {
    if (e is FlutterBluePlusException) {
      return e.description ?? 'error ${e.code ?? "?"}';
    }
    return e.toString();
  }

  static void _log(String msg) {
    if (kDebugMode) debugPrint('[ble] $msg');
  }

  @override
  void dispose() {
    _dispuesto = true;
    _pausada = true;
    _timerReconexion?.cancel();
    _timerReconexion = null;
    _subEscaneo?.cancel();
    _subEscaneo = null;
    // Desconexion explicita al cerrar la app (§5.4): si no, Android puede
    // mantener la conexion GATT y la sonda queda invisible para los demas.
    unawaited(_cerrarEnlace(silencioso: true));
    _ctrlEstado.close();
    super.dispose();
  }
}
