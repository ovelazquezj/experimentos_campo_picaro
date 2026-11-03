import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../app_state.dart';
import '../api/campo_api.dart';
import '../config.dart';
import '../theme.dart';

/// Pantalla de configuracion (§10): URL base + token (obligatorios) y, opcional,
/// la posicion del gateway para su marcador en el mapa. Se guarda con
/// shared_preferences. Sirve de primera pantalla si no hay config valida y
/// tambien es accesible luego desde el menu.
class ConfigScreen extends StatefulWidget {
  final bool firstRun;
  const ConfigScreen({super.key, this.firstRun = false});

  @override
  State<ConfigScreen> createState() => _ConfigScreenState();
}

class _ConfigScreenState extends State<ConfigScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _url;
  late final TextEditingController _token;
  late final TextEditingController _gwLat;
  late final TextEditingController _gwLon;
  bool _obscure = true;
  bool _testing = false;

  @override
  void initState() {
    super.initState();
    final c = context.read<AppState>().config;
    _url = TextEditingController(
        text: c.baseUrl.isEmpty ? 'https://campo.pi-caro.org' : c.baseUrl);
    _token = TextEditingController(text: c.token);
    _gwLat = TextEditingController(text: c.gwLat?.toString() ?? '');
    _gwLon = TextEditingController(text: c.gwLon?.toString() ?? '');
  }

  @override
  void dispose() {
    _url.dispose();
    _token.dispose();
    _gwLat.dispose();
    _gwLon.dispose();
    super.dispose();
  }

  AppConfig _buildConfig() {
    return AppConfig(
      baseUrl: _url.text.trim(),
      token: _token.text.trim(),
      gwLat: double.tryParse(_gwLat.text.trim()),
      gwLon: double.tryParse(_gwLon.text.trim()),
    );
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    await context.read<AppState>().saveConfig(_buildConfig());
    if (!mounted) return;
    // Si se abrio desde el menu, vuelve atras. Si es primera vez, _Root
    // reconstruye solo al detectar config valida.
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    }
  }

  Future<void> _test() async {
    final cfg = _buildConfig();
    if (!cfg.isValid) {
      _snack('Introduce una URL http(s) válida y un token.');
      return;
    }
    setState(() => _testing = true);
    final api = CampoApi(cfg);
    try {
      final h = await api.getHealth();
      _snack(h.ok
          ? 'OK · MQTT ${h.mqttConnected ? "conectado" : "caído"} · v${h.version}'
          : 'Respuesta: ${h.status}');
    } on ApiException catch (e) {
      _snack(e.toString());
    } catch (e) {
      _snack('Error: $e');
    } finally {
      api.close();
      if (mounted) setState(() => _testing = false);
    }
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.firstRun ? 'Configuración inicial' : 'Configuración'),
        automaticallyImplyLeading: !widget.firstRun,
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (widget.firstRun)
              const Padding(
                padding: EdgeInsets.only(bottom: 12),
                child: Text(
                  'Introduce la dirección del microservicio de campo y el token '
                  'de acceso. Se guardan en el dispositivo.',
                  style: TextStyle(color: AppColors.textDim),
                ),
              ),
            TextFormField(
              controller: _url,
              keyboardType: TextInputType.url,
              autocorrect: false,
              decoration: const InputDecoration(
                labelText: 'URL base',
                hintText: 'https://campo.pi-caro.org',
                prefixIcon: Icon(Icons.link),
              ),
              validator: (v) {
                final u = Uri.tryParse((v ?? '').trim());
                if (u == null ||
                    (u.scheme != 'http' && u.scheme != 'https') ||
                    u.host.isEmpty) {
                  return 'URL http(s) con host, p. ej. https://campo.pi-caro.org';
                }
                return null;
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _token,
              obscureText: _obscure,
              autocorrect: false,
              enableSuggestions: false,
              decoration: InputDecoration(
                labelText: 'Token (Bearer)',
                prefixIcon: const Icon(Icons.key),
                suffixIcon: IconButton(
                  icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                  onPressed: () => setState(() => _obscure = !_obscure),
                ),
              ),
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'El token es obligatorio' : null,
            ),
            const SizedBox(height: 24),
            const Text('Gateway (opcional, para el marcador del mapa)',
                style: TextStyle(color: AppColors.gold, fontSize: 12)),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _gwLat,
                    keyboardType: const TextInputType.numberWithOptions(
                        signed: true, decimal: true),
                    decoration: const InputDecoration(labelText: 'GW lat'),
                    validator: (v) => _optNum(v),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _gwLon,
                    keyboardType: const TextInputType.numberWithOptions(
                        signed: true, decimal: true),
                    decoration: const InputDecoration(labelText: 'GW lon'),
                    validator: (v) => _optNum(v),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: _testing
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.network_check),
                    label: const Text('Probar'),
                    onPressed: _testing ? null : _test,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    icon: const Icon(Icons.save),
                    label: const Text('Guardar'),
                    onPressed: _save,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // Latitud/longitud opcionales: validas solo si el otro tambien esta y son num.
  String? _optNum(String? v) {
    final s = (v ?? '').trim();
    if (s.isEmpty) return null;
    return double.tryParse(s) == null ? 'Número inválido' : null;
  }
}
