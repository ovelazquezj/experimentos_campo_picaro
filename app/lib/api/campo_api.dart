import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';
import '../models/models.dart';

/// Error de API con codigo HTTP y detalle ({"detail": "..."} del contrato, §6).
/// statusCode == 0 se usa para fallos de red/transporte (sin respuesta HTTP).
class ApiException implements Exception {
  final int statusCode;
  final String message;
  ApiException(this.statusCode, this.message);

  @override
  String toString() =>
      statusCode == 0 ? 'Sin conexión: $message' : 'HTTP $statusCode: $message';
}

/// Cliente REST del microservicio de campo (§6). Cabecera Bearer en todo salvo
/// /health.
class CampoApi {
  final AppConfig config;
  final http.Client _client;

  CampoApi(this.config, {http.Client? client})
      : _client = client ?? http.Client();

  Map<String, String> get _authHeaders => {
        'Authorization': 'Bearer ${config.token}',
        'Accept': 'application/json',
      };

  Map<String, String> get _jsonHeaders => {
        ..._authHeaders,
        'Content-Type': 'application/json',
      };

  // --- helpers de transporte ----------------------------------------------

  Future<http.Response> _get(String path, {bool auth = true}) async {
    try {
      return await _client
          .get(config.restUri(path), headers: auth ? _authHeaders : null)
          .timeout(const Duration(seconds: 15));
    } catch (e) {
      throw ApiException(0, e.toString());
    }
  }

  Future<http.Response> _post(String path, Object? body) async {
    try {
      return await _client
          .post(
            config.restUri(path),
            headers: _jsonHeaders,
            body: jsonEncode(body ?? const {}),
          )
          .timeout(const Duration(seconds: 15));
    } catch (e) {
      throw ApiException(0, e.toString());
    }
  }

  Future<http.Response> _delete(String path) async {
    try {
      return await _client
          .delete(config.restUri(path), headers: _authHeaders)
          .timeout(const Duration(seconds: 15));
    } catch (e) {
      throw ApiException(0, e.toString());
    }
  }

  /// Devuelve el cuerpo decodificado o lanza ApiException con el detalle.
  dynamic _body(http.Response r) {
    if (r.statusCode >= 200 && r.statusCode < 300) {
      if (r.body.isEmpty) return null;
      return jsonDecode(r.body);
    }
    String detail = 'Error ${r.statusCode}';
    try {
      final j = jsonDecode(r.body);
      if (j is Map && j['detail'] != null) detail = j['detail'].toString();
    } catch (_) {
      if (r.body.isNotEmpty) detail = r.body;
    }
    throw ApiException(r.statusCode, detail);
  }

  /// Extrae una Session de una respuesta que puede venir envuelta ({session:{}})
  /// o plana.
  Session _session(dynamic body) {
    final m = asMap(body);
    if (m == null) throw ApiException(0, 'Respuesta vacía');
    final inner = asMap(m['session']);
    return Session.fromJson(inner ?? m);
  }

  // --- endpoints (§6) ------------------------------------------------------

  Future<Health> getHealth() async {
    final r = await _get('/health', auth: false);
    return Health.fromJson(asMap(_body(r)) ?? const {});
  }

  /// [sonda] dice a que device aplica el servidor el perfil, el gate de clase,
  /// los pings y la captura (D-65).
  Future<Session> startSession(String scenario, String cls,
      {String sonda = 'tbeam'}) async {
    final r = await _post('/session/start',
        {'scenario': scenario, 'class': cls, 'sonda': sonda});
    return _session(_body(r));
  }

  /// Un fix del GPS del telefono para la sesion [id] (D-65).
  Future<void> postPosicion(int id, Map<String, dynamic> fix) async {
    _body(await _post('/session/$id/posicion', fix));
  }

  Future<Session> abortSession(int id) async {
    final r = await _post('/session/$id/abort', const {});
    return _session(_body(r));
  }

  Future<Session> finishSession(int id) async {
    final r = await _post('/session/$id/finish', const {});
    return _session(_body(r));
  }

  Future<CurrentState> getCurrent() async {
    final r = await _get('/session/current');
    return CurrentState.fromJson(asMap(_body(r)) ?? const {});
  }

  Future<List<SessionListItem>> getSessions() async {
    final r = await _get('/sessions');
    final body = _body(r);
    if (body is! List) return const [];
    return body
        .map((e) => SessionListItem.fromJson(asMap(e) ?? const {}))
        .toList();
  }

  Future<SessionDetail> getSession(int id) async {
    final r = await _get('/sessions/$id');
    return SessionDetail.fromJson(asMap(_body(r)) ?? const {});
  }

  Future<List<Uplink>> getUplinks(int id) async {
    final r = await _get('/sessions/$id/uplinks');
    final body = _body(r);
    if (body is! List) return const [];
    return body.map((e) => Uplink.fromJson(asMap(e) ?? const {})).toList();
  }

  /// Descarga el CSV (text/csv). Extrae el nombre del Content-Disposition.
  Future<CsvFile> downloadCsv(int id, {String fallbackName = 'sesion.csv'}) async {
    http.Response r;
    try {
      r = await _client
          .get(config.restUri('/sessions/$id/csv'), headers: _authHeaders)
          .timeout(const Duration(seconds: 30));
    } catch (e) {
      throw ApiException(0, e.toString());
    }
    if (r.statusCode < 200 || r.statusCode >= 300) {
      // Reutiliza el parseo de error de _body.
      _body(r);
    }
    final name = _filenameFromDisposition(r.headers['content-disposition']) ??
        fallbackName;
    return CsvFile(r.bodyBytes, name);
  }

  /// Borra una sesion y sus datos en el servidor (irreversible, §6). Lanza
  /// ApiException 409 si la sesion esta capturando, 404 si no existe.
  Future<void> deleteSession(int id) async {
    final r = await _delete('/sessions/$id');
    _body(r); // valida el codigo; lanza ApiException con el detalle si falla
  }

  Future<int> ping() async {
    final r = await _post('/ping', const {});
    final m = asMap(_body(r));
    return asInt(m?['seq']) ?? 0;
  }

  Future<String> setProfile(String profile) async {
    final r = await _post('/profile', {'profile': profile});
    final m = asMap(_body(r));
    return asString(m?['profile']) ?? profile;
  }

  void close() => _client.close();

  // --- utilidades privadas -------------------------------------------------

  String? _filenameFromDisposition(String? header) {
    if (header == null) return null;
    // Content-Disposition: attachment; filename="20260814-CERRO16-C.csv"
    // (o filename*=UTF-8''...). Parseo simple, sin regex fragil.
    final idx = header.toLowerCase().indexOf('filename=');
    if (idx < 0) return null;
    var name = header.substring(idx + 'filename='.length).trim();
    final tick = name.indexOf("''"); // prefijo de filename*=UTF-8''
    if (tick >= 0) name = name.substring(tick + 2);
    name = name.replaceAll('"', '').split(';').first.trim();
    if (name.isEmpty) return null;
    return name.toLowerCase().endsWith('.csv') ? name : '$name.csv';
  }
}
