// Helpers de parseo tolerante: el JSON de ChirpStack/microservicio puede traer
// numeros como int o double, booleanos como 1/0, o nulls. Estas funciones
// normalizan sin lanzar excepciones (devuelven null si no se puede convertir).

int? asInt(dynamic v) {
  if (v == null) return null;
  if (v is int) return v;
  if (v is double) return v.toInt();
  if (v is num) return v.toInt();
  if (v is bool) return v ? 1 : 0;
  if (v is String) return int.tryParse(v);
  return null;
}

double? asDouble(dynamic v) {
  if (v == null) return null;
  if (v is double) return v;
  if (v is int) return v.toDouble();
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v);
  return null;
}

/// El decoder guarda 1/0/null en SQLite para los booleanos; el JSON puede
/// venir como bool o como int. Devuelve null cuando el dato es desconocido.
bool? asBool(dynamic v) {
  if (v == null) return null;
  if (v is bool) return v;
  if (v is num) return v != 0;
  if (v is String) {
    final s = v.toLowerCase().trim();
    if (s == 'true' || s == '1') return true;
    if (s == 'false' || s == '0') return false;
  }
  return null;
}

String? asString(dynamic v) => v?.toString();

/// Extrae un sub-mapa con seguridad (para respuestas envueltas {session:{...}}).
Map<String, dynamic>? asMap(dynamic v) {
  if (v is Map<String, dynamic>) return v;
  if (v is Map) return v.map((k, val) => MapEntry(k.toString(), val));
  return null;
}
