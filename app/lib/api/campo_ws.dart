import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as ws_status;

import '../config.dart';

typedef WsMessageHandler = void Function(Map<String, dynamic> msg);
typedef WsStateHandler = void Function(bool connected);

/// Cliente WebSocket (§7): `wss://host/ws?token=...`. El token va por query param
/// porque los clientes WS no siempre permiten cabeceras. Reconexion con backoff
/// exponencial y keepalive con {"type":"pong"}.
class CampoWs {
  final AppConfig config;
  final WsMessageHandler onMessage;
  final WsStateHandler onState;

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  Timer? _reconnectTimer;
  Timer? _heartbeat;
  int _attempt = 0;
  bool _disposed = false;

  // Backoff: 1, 2, 4, 8, 16, 30 s (tope).
  static const List<int> _backoff = [1, 2, 4, 8, 16, 30];

  CampoWs(this.config, {required this.onMessage, required this.onState});

  void connect() {
    _disposed = false;
    _open();
  }

  void _open() {
    _teardownSocket();
    try {
      final ch = WebSocketChannel.connect(config.wsUri());
      _channel = ch;
      _sub = ch.stream.listen(
        _onData,
        onError: (_) => _scheduleReconnect(),
        onDone: _scheduleReconnect,
        cancelOnError: true,
      );
      // `ready` confirma que el socket abrio de verdad (paquete >= 2.3.0).
      ch.ready.then((_) {
        if (_disposed) return;
        _attempt = 0;
        onState(true);
        _startHeartbeat();
      }).catchError((_) {
        _scheduleReconnect();
      });
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _onData(dynamic data) {
    if (data is! String) return;
    try {
      final decoded = jsonDecode(data);
      if (decoded is Map<String, dynamic>) onMessage(decoded);
    } catch (_) {
      // Mensaje no-JSON: se ignora.
    }
  }

  void _startHeartbeat() {
    _heartbeat?.cancel();
    _heartbeat = Timer.periodic(const Duration(seconds: 30), (_) {
      try {
        _channel?.sink.add(jsonEncode({'type': 'pong'}));
      } catch (_) {}
    });
  }

  void _scheduleReconnect() {
    onState(false);
    _teardownSocket();
    if (_disposed) return;
    if (_reconnectTimer != null) return; // ya hay uno programado
    final idx = _attempt.clamp(0, _backoff.length - 1);
    final delay = Duration(seconds: _backoff[idx]);
    if (_attempt < _backoff.length - 1) _attempt++;
    _reconnectTimer = Timer(delay, () {
      _reconnectTimer = null;
      if (!_disposed) _open();
    });
  }

  void _teardownSocket() {
    _heartbeat?.cancel();
    _heartbeat = null;
    _sub?.cancel();
    _sub = null;
    try {
      _channel?.sink.close(ws_status.normalClosure);
    } catch (_) {}
    _channel = null;
  }

  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _teardownSocket();
  }
}
