import 'package:shared_preferences/shared_preferences.dart';

/// Version de la app que se muestra en "Acerca de".
/// Mantener sincronizada con `version:` de pubspec.yaml.
const String kAppVersion = '2.3.0';

/// Objetivo de uplinks por corrida (§5). El servidor manda el real por sesion,
/// pero este valor sirve de fallback para el "n/300" cuando aun no hay metrica.
const int kDefaultTargetUplinks = 300;

/// Configuracion persistida por el usuario en la primera pantalla (§10):
/// URL base del microservicio y token Bearer. Ademas, de forma opcional, la
/// posicion del gateway para dibujar su marcador en el mapa (el contrato no
/// expone GW_LAT/GW_LON por la API, asi que se introduce aqui una vez).
class AppConfig {
  final String baseUrl;
  final String token;
  final double? gwLat;
  final double? gwLon;

  const AppConfig({
    this.baseUrl = '',
    this.token = '',
    this.gwLat,
    this.gwLon,
  });

  /// Config valida = URL http(s) con host y un token no vacio.
  bool get isValid {
    if (token.trim().isEmpty) return false;
    final u = Uri.tryParse(baseUrl.trim());
    if (u == null) return false;
    return (u.scheme == 'http' || u.scheme == 'https') && u.host.isNotEmpty;
  }

  bool get hasGateway => gwLat != null && gwLon != null;

  /// Base sin barras finales.
  String get _base => baseUrl.trim().replaceAll(RegExp(r'/+$'), '');

  /// URL REST absoluta para un path del contrato (p. ej. "/session/start").
  Uri restUri(String path) {
    final p = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$_base$p');
  }

  /// URL del WebSocket: mismo host, esquema ws/wss y token por query param (§7).
  Uri wsUri() {
    final u = Uri.parse(_base);
    final scheme = u.scheme == 'https' ? 'wss' : 'ws';
    return u.replace(
      scheme: scheme,
      path: '/ws',
      queryParameters: {'token': token},
    );
  }

  AppConfig copyWith({
    String? baseUrl,
    String? token,
    double? gwLat,
    double? gwLon,
    bool clearGateway = false,
  }) {
    return AppConfig(
      baseUrl: baseUrl ?? this.baseUrl,
      token: token ?? this.token,
      gwLat: clearGateway ? null : (gwLat ?? this.gwLat),
      gwLon: clearGateway ? null : (gwLon ?? this.gwLon),
    );
  }

  // --- Persistencia --------------------------------------------------------
  static const _kBase = 'campo_base_url';
  static const _kToken = 'campo_token';
  static const _kGwLat = 'campo_gw_lat';
  static const _kGwLon = 'campo_gw_lon';

  static Future<AppConfig> load() async {
    final p = await SharedPreferences.getInstance();
    return AppConfig(
      baseUrl: p.getString(_kBase) ?? '',
      token: p.getString(_kToken) ?? '',
      gwLat: p.getDouble(_kGwLat),
      gwLon: p.getDouble(_kGwLon),
    );
  }

  Future<void> save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kBase, baseUrl.trim());
    await p.setString(_kToken, token.trim());
    if (gwLat != null) {
      await p.setDouble(_kGwLat, gwLat!);
    } else {
      await p.remove(_kGwLat);
    }
    if (gwLon != null) {
      await p.setDouble(_kGwLon, gwLon!);
    } else {
      await p.remove(_kGwLon);
    }
  }
}
